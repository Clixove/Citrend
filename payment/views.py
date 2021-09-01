import json
import random
import smtplib
import string
from datetime import timedelta
from email.mime.text import MIMEText
from email.utils import formataddr
from citrend.settings import PRICE_EACH_FACTORY, PRICE_EACH_TRAINING

from django import forms
from django.contrib.auth.decorators import permission_required
from django.http.response import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from ratelimit.decorators import ratelimit

from .models import *

with open('token/smtp.json', "r") as f:
    config = json.load(f)


def send_notification(donation: Transaction, host: str):
    receivers = [x.email for x in WebsiteManager.objects.all()]
    if len(receivers) == 0:
        return
    msg = f"""
    <p style="font-size: large"> New donation </p>
    <p> Host: {host} </p>
    <p> Donation code: {donation.token} </p>
    <p> Payment method: {donation.method} </p>
    <p> Created at: {donation.created_time} </p>
    <p> <strong> If you have received the donation, click: </strong> 
    <a href="{host}/payment/prestige/add/{donation.token}">CONFIRM</a> </p>
    <p> Please check the payment and add prestige points for the user soon. </p>
    <p> You receive this email because you're listed as a manager of website: {host} </p>
    <hr>
    <p>For more information about our organization: <a href="https://blog.clixove.com/"> Clixove </a></p>
    <p>Best wishes! Science will make our life better.</p>
    <p>Cloudy</p>
    <p>Developer of Clixove software</p>
        """
    msg = MIMEText(msg, 'html', 'utf-8')
    msg['From'] = formataddr(('Clixove', config['username']))
    msg['To'] = ', '.join(receivers)
    msg['Subject'] = 'New donation from Clixove website'
    server = smtplib.SMTP_SSL(config['host'], config['port'])
    server.login(config['username'], config['password'])
    server.sendmail(config['username'], receivers, msg.as_string())
    server.quit()


class DonationMethod(forms.Form):
    method = forms.ModelChoiceField(
        PayingMethod.objects.all(), widget=forms.Select({
            'class': 'form-select', 'onchange': 'query_donation_method(this)',
        }),
        label='Paying Method',
    )
    token = forms.CharField(max_length=16, widget=forms.HiddenInput())


class DonationConfirm(forms.Form):
    amount = forms.FloatField(
        widget=forms.NumberInput({'class': 'form-control'}), help_text='Converted to USD amount.'
    )
    token = forms.CharField(max_length=16, widget=forms.HiddenInput())
    conclusion = forms.BooleanField(
        required=False, initial=True, widget=forms.Select(
            {"class": "form-select"},
            choices=[(True, 'Yes, this token has paid.'), (False, 'No, this token is not paid.')]
        )
    )


class BuyPermissionFactory(forms.Form):
    type_ = forms.ChoiceField(choices=[(p, p) for p in PRICE_EACH_FACTORY.keys()],
                              widget=forms.Select({'class': 'form-select'}))
    amount = forms.IntegerField(min_value=1, widget=forms.NumberInput({'class': 'form-control'}))


class BuyPermissionTraining(forms.Form):
    amount = forms.IntegerField(min_value=1, widget=forms.NumberInput({'class': 'form-control'}))


def donate(req):
    donation_code = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=16))
    context = {
        'donation_method': DonationMethod(initial={'token': donation_code}),
        'token': donation_code,
    }
    return render(req, 'payment/donate.html', context)


@permission_required(
    'payment.view_payingmethod',
    login_url='/payment/donate?message=Do not have permission to view paying methods.&color=danger')
def view_method(req, idx):
    try:
        method = PayingMethod.objects.get(id=idx)
    except PayingMethod.DoesNotExist:
        return HttpResponse('#')
    return HttpResponse(method.payment_button_url)


@permission_required(
    'payment.view_transaction',
    login_url='/payment/donate?message=Do not have permission to view transactions.&color=danger')
def view_transaction(req):
    context = {
        'transactions': Transaction.objects.filter(created_user=req.user).order_by('-created_time'),
    }
    return render(req, 'payment/transaction.html', context)


@csrf_exempt
@require_POST
@permission_required(
    'payment.add_transaction',
    login_url='/payment/donate?message=Do not have permission to add transactions.&color=danger')
@ratelimit(key='header:x-real-ip', rate='70/10m', block=True)
@ratelimit(key='post:token', rate='1/1m', block=True)
def add_transaction(req):
    dm = DonationMethod(req.POST)
    if not dm.is_valid():
        return HttpResponse(f'Donation form is not valid: <br> {dm.errors}')
    new_donation = Transaction(created_user=req.user, amount=0, paid=False, method=dm.cleaned_data['method'],
                               token=dm.cleaned_data['token'])
    new_donation.save()
    send_notification(new_donation, host=req.META['HTTP_HOST'])
    return redirect('/payment/transaction?message=Thank you for your donation! The '
                    'website managers will check it in several days.&color=success')


@permission_required(
    'payment.view_prestige',
    login_url='/payment/donate?message=Do not have permission to view prestige.&color=danger')
def view_prestige(req):
    context = {
        'prestige_s': Prestige.objects.filter(created_user=req.user).order_by('-created_time'),
        'my_coins': deposit(req.user), 'my_tickets': training_tickets(req.user),
        'my_factories': max_existed_factory(req.user),
    }
    return render(req, 'payment/prestige.html', context)


@permission_required(
    'payment.add_prestige',
    login_url='/main?message=Please log in as website manager.&color=danger')
def view_add_prestige(req, token):
    context = {
        'donation_confirm_sheet': DonationConfirm(initial={'amount': 0, 'token': token})
    }
    return render(req, 'payment/confirm.html', context)


@csrf_exempt
@require_POST
@permission_required(
    'payment.add_prestige',
    login_url='/main?message=Please log in as website manager.&color=danger')
def add_prestige(req):
    dc = DonationConfirm(req.POST)
    if not dc.is_valid():
        return redirect('/main?message=Confirming request is not valid.&color=danger')
    try:
        donation = Transaction.objects.get(paid=False, token=dc.cleaned_data['token'])
    except Transaction.DoesNotExist:
        return redirect('/main?message=Donation not found.&color=danger')
    if dc.cleaned_data['conclusion']:
        donation.amount = dc.cleaned_data['amount']
        donation.paid = True
        donation.save()
        new_prestige = Prestige(created_user=donation.created_user, amount=dc.cleaned_data['amount'],
                                transaction=donation)
        new_prestige.save()
        return redirect('/main?message=Successfully confirm the donation.&color=success')
    else:
        return redirect('/main?message=Successfully deny the donation.&color=success')


def view_add_subscription(req):
    context = {
        'buy_permission_factory': BuyPermissionFactory(), 'buy_permission_training': BuyPermissionTraining(),
        'factory_price': PRICE_EACH_FACTORY, 'training_price': PRICE_EACH_TRAINING,
    }
    return render(req, 'payment/add_tickets.html', context)


@csrf_exempt
@require_POST
@permission_required(
    'payment.add_subscription',
    login_url='/payment/donate?message=Do not have permission to add subscription.&color=danger')
def add_subscription_1(req):
    bp = BuyPermissionFactory(req.POST)
    if not bp.is_valid():
        return redirect('/payment/subscription?message=Submission is not valid.&color=danger')
    price = bp.cleaned_data['amount'] * PRICE_EACH_FACTORY[bp.cleaned_data['type_']]['price']
    if deposit(req.user) < price:
        return redirect('/payment/subscription?message=Prestige points not enough.&color=danger')
    expired_time = now() + timedelta(days=PRICE_EACH_FACTORY[bp.cleaned_data['type_']]['subscription_days'])
    new_prestige = Prestige(created_user=req.user, amount=-price, max_existed_factory=bp.cleaned_data['amount'],
                            expired_time=expired_time)
    new_prestige.save()
    return redirect('/payment/prestige?message=Added factory seats successfully.&color=success')


@csrf_exempt
@require_POST
@permission_required(
    'payment.add_subscription',
    login_url='/payment/donate?message=Do not have permission to add subscription.&color=danger')
def add_subscription_2(req):
    bp = BuyPermissionTraining(req.POST)
    if not bp.is_valid():
        return redirect('/payment/subscription?message=Submission is not valid.&color=danger')
    price = bp.cleaned_data['amount'] * PRICE_EACH_TRAINING
    if deposit(req.user) < price:
        return redirect('/payment/subscription?message=Prestige points not enough.&color=danger')
    new_prestige = Prestige(created_user=req.user, amount=-price, training_tickets=bp.cleaned_data['amount'])
    new_prestige.save()
    return redirect('/payment/prestige?message=Added training tickets successfully.&color=success')
