from django.db import models
from django.contrib.auth.models import Group, User
from django.utils.timezone import now


class Transaction(models.Model):
    created_time = models.DateTimeField(auto_now_add=True)
    created_user = models.ForeignKey(User, models.DO_NOTHING, related_name='payment_created_user')

    amount = models.FloatField()
    paid = models.BooleanField()

    method = models.CharField(max_length=64, blank=True)
    token = models.CharField(max_length=16, blank=True)


class PayingMethod(models.Model):
    name = models.CharField(max_length=64)
    payment_button_url = models.TextField()

    def __str__(self):
        return self.name


class Prestige(models.Model):
    created_time = models.DateTimeField(default=now)
    created_user = models.ForeignKey(User, models.DO_NOTHING, related_name='payment_donation_created_user')
    amount = models.FloatField()
    transaction = models.ForeignKey(Transaction, models.DO_NOTHING, blank=True, null=True)

    max_existed_factory = models.IntegerField(default=0)
    training_tickets = models.IntegerField(default=0)
    expired_time = models.DateTimeField(blank=True, null=True)


class WebsiteManager(models.Model):
    user = models.ForeignKey(User, models.CASCADE)
    email = models.EmailField()

    def __str__(self):
        return self.user.username


def deposit(user: User) -> float:
    return sum([x.amount for x in Prestige.objects.filter(created_user=user)])

def max_existed_factory(user: User) -> int:
    return sum([x.max_existed_factory for x in Prestige.objects.filter(created_user=user, expired_time__gt=now())])

def training_tickets(user: User) -> int:
    return sum([x.training_tickets for x in Prestige.objects.filter(created_user=user)])
