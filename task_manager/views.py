from django.shortcuts import render, redirect
from .models import *
from django.contrib.auth.decorators import permission_required
from django import forms
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
import pandas as pd
from django.core.files.base import ContentFile
import pickle
import json
from datetime import datetime
from payment.models import max_existed_factory
from math import ceil


class PublicFactory(forms.Form):
    factory = forms.ModelChoiceField(Factory.objects.none(), widget=forms.HiddenInput())

    def load_factory(self, user, factory):
        self.fields['factory'].queryset = Factory.objects.filter(user=user)
        self.fields['factory'].initial = factory


def view_main(req):
    context = dict()
    if req.user.is_authenticated:
        context['factories'] = Factory.objects.filter(user=req.user)
    return render(req, 'main.html', context)


@permission_required(
    'task_manager.delete_factory',
    login_url='/main?message=Do not have permission to delete factory.&color=danger'
)
def delete_factory(req, idx):
    try:
        factory = Factory.objects.get(user=req.user, id=idx, busy=False)
    except Factory.DoesNotExist:
        return redirect('/main?message=The factory is busy or does not exist.&color=warning')
    factory.delete()
    return redirect('/main?message=Deletion succeed.&color=success')


class CreateFactory(forms.Form):
    name = forms.CharField(
        max_length=64,
        widget=forms.TextInput({"class": "form-control"}),
    )
    training_set = forms.FileField(
        widget=forms.FileInput({"class": "form-control", "accept": ".xlsx"}),
        validators=[FileExtensionValidator(allowed_extensions=['xlsx'])],
    )


@permission_required(
    'task_manager.view_factory',
    login_url='/main?message=Do not have permission to view factory.&color=danger'
)
def view_create_factory(req):
    context = {'new_factory_sheet': CreateFactory()}
    return render(req, 'task_manager/create_factory.html', context)


@csrf_exempt
@require_POST
@permission_required(
    'task_manager.add_factory',
    login_url='/main?message=Do not have permission to add factory.&color=danger'
)
def create_factory(req):
    nf = CreateFactory(req.POST, req.FILES)
    if not nf.is_valid():
        return redirect('/main?message=\'Create factory\' submission is not valid.&color=danger')
    if Factory.objects.filter(user=req.user).count() >= max_existed_factory(req.user):
        return redirect('/main?message=Your factories reach the maximum number.&color=danger')
    new_factory = Factory(
        name=nf.cleaned_data['name'], user=req.user,
        training_set=nf.cleaned_data['training_set'], busy=False
    )
    new_factory.save()
    return redirect(f'/factory/{new_factory.id}/view-add-2')


class AssignSheet(PublicFactory):
    transaction_sheet = forms.CharField(
        widget=forms.Select({"class": "form-select"}),
        help_text="The sheet containing transactions (independent variables) as squeezed time series records.",
    )
    score_sheet = forms.CharField(
        widget=forms.Select({"class": "form-select"}),
        help_text="The sheet containing SMEs' scores.",
    )
    def load_choices(self, sheet_names):
        self.fields['transaction_sheet'].widget.choices = [(x, x) for x in sheet_names]
        self.fields['score_sheet'].widget.choices = [(x, x) for x in sheet_names]


@permission_required(
    'task_manager.view_factory',
    login_url='/main?message=Do not have permission to view factory.&color=danger'
)
def view_assign_sheet(req, idx):
    # ---------- Busy checking view version START ----------
    try:
        factory = Factory.objects.get(user=req.user, id=idx, busy=False)
    except Factory.DoesNotExist:
        return redirect('/main?message=The factory is busy or does not exist.&color=warning')
    # ---------- Busy checking view version END   ----------
    factory.busy = True
    factory.save()
    try:
        # ---------- Asynchronous Algorithm START ----------
        xl = pd.ExcelFile(factory.training_set.path)
        select_sheet = AssignSheet(initial={'transaction_sheet': factory.transaction_sheet,
                                            'score_sheet': factory.score_sheet})
        select_sheet.load_choices(xl.sheet_names)
        select_sheet.load_factory(user=req.user, factory=factory)
        # ---------- Asynchronous Algorithm END   ----------
    except Exception as e:
        factory.delete()
        return redirect(f'/main?message=Parsing error, {e}&color=danger')
    factory.busy = False
    factory.save()
    context = {'select_sheet': select_sheet}
    return render(req, 'task_manager/assign_sheet.html', context)


@csrf_exempt
@require_POST
@permission_required(
    'task_manager.change_factory',
    login_url='/main?message=Do not have permission to config factory.&color=danger'
)
def assign_sheet(req):
    ss = AssignSheet(req.POST)
    ss.load_factory(user=req.user, factory=None)
    if not ss.is_valid():
        return redirect('/main?message=\'Assign sheet\' submission is not valid.&color=danger')
    # ---------- Busy checking handle version START ----------
    factory = ss.cleaned_data['factory']
    if factory.busy:
        return redirect('/main?message=This factory is busy.&color=warning')
    # ---------- Busy checking handle version END   ----------
    factory.busy = True
    factory.save()
    try:
        # ---------- Asynchronous Algorithm START ----------
        transaction_sheet = pd.read_excel(factory.training_set.path, sheet_name=ss.cleaned_data['transaction_sheet'])
        score_sheet = pd.read_excel(factory.training_set.path, sheet_name=ss.cleaned_data['score_sheet'])
        intermediate_paper_handle = ContentFile(pickle.dumps({'transaction': transaction_sheet, 'score': score_sheet}))
        factory.parsed_training_set.delete()
        factory.parsed_training_set.save(f'factory_{factory.id}_table.pkl', intermediate_paper_handle)
        [c.delete() for c in Column.objects.filter(factory=factory)]
        for column in transaction_sheet.columns:
            new_column = Column(factory=factory, name=column)
            new_column.save()
        for column in score_sheet.columns:
            new_column = Column(factory=factory, name=column, belong_transaction=False)
            new_column.save()
        factory.transaction_sheet = ss.cleaned_data['transaction_sheet']
        factory.score_sheet = ss.cleaned_data['score_sheet']
        # ---------- Asynchronous Algorithm END   ----------
    except Exception as e:
        factory.busy = False
        factory.save()
        return redirect(f'/main?message=Parsing error, {e}&color=danger')
    factory.busy = False
    factory.save()
    return redirect(f'/factory/{factory.id}/view-add-3')


class AssignColumn(PublicFactory):
    from_datetime = forms.DateTimeField(widget=forms.DateTimeInput({'class': 'form-control', 'format-value': 'YYYY-MM-DD HH:mm:ss'}))
    to_datetime = forms.DateTimeField(widget=forms.DateTimeInput({'class': 'form-control', 'format-value': 'YYYY-MM-DD HH:mm:ss'}))
    periods = forms.IntegerField(widget=forms.NumberInput({'class': 'form-control'}), validators=[MinValueValidator(1)])
    date = forms.ModelChoiceField(Column.objects.all())
    company_trans = forms.ModelChoiceField(Column.objects.all())
    use = forms.ModelMultipleChoiceField(Column.objects.all())
    log = forms.ModelMultipleChoiceField(Column.objects.all(), required=False)
    diff = forms.ModelMultipleChoiceField(Column.objects.all(), required=False)
    fill_na_avg = forms.ModelMultipleChoiceField(Column.objects.all(), required=False)
    company_score = forms.ModelChoiceField(Column.objects.all())
    score = forms.ModelChoiceField(Column.objects.all())

    def load_customized_part(self, factory):
        self.fields['date'].queryset = Column.objects.filter(factory=factory, belong_transaction=True)
        self.fields['company_trans'].queryset = Column.objects.filter(factory=factory, belong_transaction=True)
        self.fields['use'].queryset = Column.objects.filter(factory=factory, belong_transaction=True)
        self.fields['log'].queryset = Column.objects.filter(factory=factory, belong_transaction=True)
        self.fields['diff'].queryset = Column.objects.filter(factory=factory, belong_transaction=True)
        self.fields['fill_na_avg'].queryset = Column.objects.filter(factory=factory, belong_transaction=True)
        self.fields['company_score'].queryset = Column.objects.filter(factory=factory, belong_transaction=False)
        self.fields['score'].queryset = Column.objects.filter(factory=factory, belong_transaction=False)


@permission_required(
    'task_manager.view_factory',
    login_url='/main?message=Do not have permission to view factory.&color=danger'
)
def view_assign_column(req, idx):
    # ---------- Busy checking view version START ----------
    try:
        factory = Factory.objects.get(user=req.user, id=idx, busy=False)
    except Factory.DoesNotExist:
        return redirect('/main?message=The factory is busy or does not exist.&color=warning')
    # ---------- Busy checking view version END   ----------
    ac = AssignColumn()
    ac.load_factory(user=req.user, factory=factory)
    try:
        config = json.loads(factory.config)
        if 'from_datetime' in config.keys():
            try:
                ac.fields['from_datetime'].initial = datetime.strptime(config['from_datetime'], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                del config['from_datetime']
        if 'to_datetime' in config.keys():
            try:
                ac.fields['to_datetime'].initial = datetime.strptime(config['to_datetime'], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                del config['to_datetime']
        if 'periods' in config.keys():
            ac.fields['periods'].initial = config['periods']
    except ValueError:
        return redirect('/main?message=Configuration dictionary is not valid.&color=danger')
    context = {
        "assign_column": ac,
        "transaction_columns": Column.objects.filter(factory=factory, belong_transaction=True),
        "score_columns": Column.objects.filter(factory=factory, belong_transaction=False),
    }
    return render(req, 'task_manager/assign_column.html', context)


@csrf_exempt
@require_POST
@permission_required(
    'task_manager.change_factory',
    login_url='/main?message=Do not have permission to config factory.&color=danger'
)
def assign_column(req):
    ac = AssignColumn(req.POST)
    ac.load_factory(user=req.user, factory=None)
    if not ac.is_valid():
        return redirect('/main?message=\'Assign column\' submission is not valid.&color=danger')
    # ---------- Busy checking handle version START ----------
    factory = ac.cleaned_data['factory']
    if factory.busy:
        return redirect('/main?message=This factory is busy.&color=warning')
    # ---------- Busy checking handle version END   ----------
    factory.busy = True
    factory.save()

    # ---------- Asynchronous Algorithm START ----------
    ac.load_customized_part(factory=factory)
    if not ac.is_valid():
        return redirect('/main?message=\'Assign column\' submission is not valid.&color=danger')
    for column in Column.objects.filter(factory=factory):
        column.is_date = column == ac.cleaned_data['date']
        column.is_company = (column == ac.cleaned_data['company_trans']) or (column == ac.cleaned_data['company_score'])
        column.is_score = column == ac.cleaned_data['score']
        column.use = column in ac.cleaned_data['use']
        column.log = column in ac.cleaned_data['log']
        column.diff = column in ac.cleaned_data['diff']
        column.fill_na_avg = column in ac.cleaned_data['fill_na_avg']
        column.save()
    try:
        config = json.loads(factory.config)
    except ValueError:
        config = {}
    config = config | {
        'from_datetime': ac.cleaned_data['from_datetime'].strftime('%Y-%m-%d %H:%M:%S'),
        'to_datetime': ac.cleaned_data['to_datetime'].strftime('%Y-%m-%d %H:%M:%S'),
        'periods': ac.cleaned_data['periods'],
    }
    factory.config = json.dumps(config)
    # ---------- Asynchronous Algorithm END   ----------

    factory.busy = False
    factory.save()
    return redirect(f'/factory/{factory.id}/view-add-4')


class ConfigModel(PublicFactory):
    neuron_number_in_LSTM_layer = forms.IntegerField(
        widget=forms.NumberInput({'class': 'form-control'}), initial=32,
        validators=[MinValueValidator(8), MaxValueValidator(128)],
        help_text='Ranging from 8 to 128.'
    )
    max_neuron_number_in_dense_layer = forms.IntegerField(
        widget=forms.NumberInput({'class': 'form-control'}), initial=64,
        validators=[MinValueValidator(8), MaxValueValidator(512)],
        help_text='Ranging from 32 to 512.'
    )
    ratio_of_neuron_number_in_adjacent_layer = forms.ChoiceField(
        widget=forms.Select({'class': 'form-select'}), initial=8,
        choices=[(8, 'x0.125'), (4, 'x0.25'), (2, 'x0.5')]
    )
    patient = forms.IntegerField(
        widget=forms.NumberInput({'class': 'form-control'}), initial=60,
        validators=[MinValueValidator(5), MaxValueValidator(200)],
        help_text="Model will stop training and save best weights when MAE in validation set doesn't reach historical"
                  "minimum in 'patient' steps."
    )
    max_iteration = forms.IntegerField(
        widget=forms.NumberInput({'class': 'form-control'}), initial=1000,
        validators=[MinValueValidator(10), MaxValueValidator(2000)],
        help_text="Model will stop training when reaching max iteration steps."
    )


@permission_required(
    'task_manager.view_factory',
    login_url='/main?message=Do not have permission to view factory.&color=danger'
)
def view_config_model(req, idx):
    # ---------- Busy checking view version START ----------
    try:
        factory = Factory.objects.get(user=req.user, id=idx, busy=False)
    except Factory.DoesNotExist:
        return redirect('/main?message=The factory is busy or does not exist.&color=warning')
    # ---------- Busy checking view version END   ----------
    config_model_sheet = ConfigModel()
    config_model_sheet.load_factory(user=req.user, factory=factory)
    context = {"config_model": config_model_sheet}
    return render(req, "task_manager/config_model.html", context)


@csrf_exempt
@require_POST
@permission_required(
    'task_manager.change_factory',
    login_url='/main?message=Do not have permission to config factory.&color=danger'
)
def config_model(req):
    cm = ConfigModel(req.POST)
    cm.load_factory(user=req.user, factory=None)
    if not cm.is_valid():
        return redirect('/main?message=\'Config model\' submission is not valid.&color=danger')
    # ---------- Busy checking handle version START ----------
    factory = cm.cleaned_data['factory']
    if factory.busy:
        return redirect('/main?message=This factory is busy.&color=warning')
    # ---------- Busy checking handle version END   ----------
    factory.busy = True
    factory.save()

    # ---------- Asynchronous Algorithm START   ----------
    dense = [cm.cleaned_data['max_neuron_number_in_dense_layer']]
    ratio = int(cm.cleaned_data['ratio_of_neuron_number_in_adjacent_layer'])
    while dense[-1] > 1:
        dense.append(ceil(dense[-1] / ratio))
    try:
        config = json.loads(factory.config)
    except ValueError:
        config = {}
    config = config | {
        'lstm_units': cm.cleaned_data['neuron_number_in_LSTM_layer'],
        'dense_units': dense,
        'patient': cm.cleaned_data['patient'],
        'steps': cm.cleaned_data['max_iteration']
    }
    factory.config = json.dumps(config)
    # ---------- Asynchronous Algorithm END   ----------

    factory.busy = False
    factory.save()
    return redirect(f'/runtime/view_train/{factory.id}?message=Config successfully finished.&color=success')
