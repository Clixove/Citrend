from io import BytesIO
import matplotlib.pyplot as plt
from django.contrib.auth.decorators import permission_required
from django.http.response import HttpResponse, FileResponse
from django.shortcuts import render, redirect
from django.core.validators import FileExtensionValidator
from task_manager.views import PublicFactory
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import *
from django import forms


@permission_required(
    'task_manager.view_factory',
    login_url='/main?message=Do not have permission to view factory.&color=danger'
)
def view_train(req, idx):
    # ---------- Busy checking view version START ----------
    try:
        factory = Factory.objects.get(user=req.user, id=idx)
    except Factory.DoesNotExist:
        return redirect('/main?message=The factory does not exist.&color=warning')
    # ---------- Busy checking view version END   ----------
    context = {'factory': factory}
    return render(req, 'task_runtime/train.html', context)


@permission_required(
    'task_manager.change_factory',
    login_url='/main?message=Do not have permission to config factory.&color=danger'
)
def train(req, idx, processed):
    # ---------- Busy checking view version START ----------
    try:
        factory = Factory.objects.get(user=req.user, id=idx, busy=False)
    except Factory.DoesNotExist:
        return HttpResponse('The factory is busy or does not exist.')
    # ---------- Busy checking view version END   ----------
    factory.busy = True
    factory.save()
    try:
        # ---------- Asynchronous Algorithm START ----------
        if not processed:
            pre_processing_xy(factory)
        train_log = nn_train(factory)
        plt.figure()
        plt.plot(train_log['val_loss'])
        plt.legend(['Validation Loss'], loc='upper right')
        plt.xlabel('Epochs')
        plt.ylabel('MAE')
        plt.title('Validation Loss')
        img_text = BytesIO()
        plt.savefig(img_text, format="svg")
        plt.close()
        img_text.seek(0)
        factory.validation_loss = img_text.read().decode('utf-8')
        # ---------- Asynchronous Algorithm END   ----------
    except Exception as e:
        factory.busy = False
        factory.save()
        return HttpResponse(str(e))
    factory.busy = False
    factory.save()
    return HttpResponse('Successfully trained.')


class SelectPredictData(PublicFactory):
    predicting_set = forms.FileField(widget=forms.FileInput({'class': 'form-control', 'accept': '.xlsx'}),
                                     validators=[FileExtensionValidator(allowed_extensions=['xlsx'])])

class ConfigPredict(PublicFactory):
    prediction = forms.ModelChoiceField(Predict.objects.none(), widget=forms.HiddenInput())
    end_datetime = forms.DateTimeField(
        widget=forms.DateTimeInput({'class': 'form-control', 'format-value': 'YYYY-MM-DD HH:mm:ss'}),
        help_text="Input the end time point of analysis period as the format like '2020-01-01 00:00:00'."
    )
    transaction_sheet = forms.CharField(widget=forms.Select({'class': 'form-select'}))

    def load_prediction(self, user, prediction):
        self.fields['prediction'].queryset = Predict.objects.filter(factory__user=user)
        self.fields['prediction'].initial = prediction

    def load_sheets(self, sheet_names):
        self.fields['transaction_sheet'].widget.choices = [(name, name) for name in sheet_names]


@permission_required(
    'task_manager.view_factory',
    login_url='/main?message=Do not have permission to view factory.&color=danger'
)
def view_predict(req, idx, second_step=None):
    # ---------- Busy checking view version START ----------
    try:
        factory = Factory.objects.get(user=req.user, id=idx, busy=False)
    except Factory.DoesNotExist:
        return redirect('/main?message=The factory is busy or does not exist.&color=danger')
    # ---------- Busy checking view version END   ----------
    spd = SelectPredictData()
    spd.load_factory(user=req.user, factory=factory)
    context = {
        'load_predict_data': second_step if second_step else spd,
        'purpose': '/runtime/predict' if second_step else '/runtime/add_predict',
        'prediction_history': Predict.objects.filter(factory=factory).order_by('-predicted_time'),
    }
    return render(req, "task_runtime/predict.html", context)


@csrf_exempt
@require_POST
@permission_required(
    'task_runtime.add_predict',
    login_url='/main?message=Do not have permission to add prediction.&color=danger'
)
def add_predict(req):
    spd = SelectPredictData(req.POST, req.FILES)
    spd.load_factory(user=req.user, factory=None)
    if not spd.is_valid():
        return redirect('/main?message=\'Select predicting data\' submission is not valid.&color=danger')
    # ---------- Busy checking handle version START ----------
    factory = spd.cleaned_data['factory']
    if factory.busy:
        return redirect(f'/runtime/view_predict/{factory.id}?message=This factory is busy.&color=warning')
    # ---------- Busy checking handle version END   ----------
    new_prediction = Predict(
        factory=factory, predicting_set=spd.cleaned_data['predicting_set']
    )
    new_prediction.save()
    cp = ConfigPredict()
    cp.load_factory(user=req.user, factory=factory)
    cp.load_prediction(user=req.user, prediction=new_prediction)
    try:
        # ---------- Asynchronous Algorithm START ----------
        xl = pd.ExcelFile(new_prediction.predicting_set.path)
        cp.load_sheets(xl.sheet_names)
        # ---------- Asynchronous Algorithm END   ----------
    except Exception as e:
        factory.delete()
        return redirect(f'/runtime/view_predict/{factory.id}?message=Parsing error, {e}&color=danger')
    return view_predict(req, factory.id, cp)


@permission_required(
    'task_runtime.view_predict',
    login_url='/main?message=Do not have permission to view prediction.&color=danger'
)
def view_prediction_results(req, idx):
    try:
        prediction = Predict.objects.get(id=idx, factory__user=req.user)
    except Predict.DoesNotExist:
        return HttpResponse('Prediction does not exist.')
    return FileResponse(prediction.prediction)


@csrf_exempt
@require_POST
@permission_required(
    'task_runtime.change_predict',
    login_url='/main?message=Do not have permission to change prediction.&color=danger'
)
def predict(req):
    cp = ConfigPredict(req.POST)
    cp.load_factory(user=req.user, factory=None)
    cp.load_prediction(user=req.user, prediction=None)
    if not cp.is_valid():
        return redirect(f'/main?\'Set prediction requirements\' submission is not valid.&color=danger')
    # ---------- Busy checking handle version START ----------
    factory = cp.cleaned_data['factory']
    prediction = cp.cleaned_data['prediction']
    if factory.busy:
        return redirect(f'/runtime/view_predict/{factory.id}?message=This factory is busy.&color=warning')
    # ---------- Busy checking handle version END   ----------
    factory.busy = True
    factory.save()
    try:
        # ---------- Asynchronous Algorithm START ----------
        transaction_sheet = pd.read_excel(prediction.predicting_set.path, sheet_name=cp.cleaned_data['transaction_sheet'])
        pre_processing_x(transaction_sheet, cp.cleaned_data['end_datetime'], prediction)
        nn_predict(prediction)
        # ---------- Asynchronous Algorithm END   ----------
    except Exception as e:
        factory.busy = False
        factory.save()
        prediction.error_message = str(e)
        prediction.save()
        return redirect(f'/runtime/view_predict/{factory.id}?message=Parsing error, {e}&color=danger')
    factory.busy = False
    factory.save()
    prediction.save()
    return redirect(f'/runtime/view_predict/{factory.id}?message=Predict successfully.&color=success')
