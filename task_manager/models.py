from django.contrib.auth.models import User
from django.db import models
from django.utils.timezone import now


class Factory(models.Model):
    name = models.CharField(max_length=64)
    user = models.ForeignKey(User, models.CASCADE)
    trained_time = models.DateTimeField(default=now)
    busy = models.BooleanField()
    training_set = models.FileField(upload_to='data')

    model_0 = models.FileField(upload_to='models', blank=True, null=True)
    transaction_sheet = models.TextField(blank=True)
    score_sheet = models.TextField(blank=True)
    parsed_training_set = models.FileField(upload_to='intermediate', blank=True, null=True)
    normalizers = models.FileField(upload_to='models', blank=True, null=True)
    matrix = models.FileField(upload_to='intermediate', blank=True, null=True)
    config = models.TextField(default='{}')

    validation_loss = models.TextField(blank=True)  # training history SVG
    mae = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Factories'


class Column(models.Model):
    factory = models.ForeignKey(Factory, models.CASCADE)
    name = models.TextField()
    belong_transaction = models.BooleanField(default=True)
    is_date = models.BooleanField(default=False)
    is_company = models.BooleanField(default=False)
    is_score = models.BooleanField(default=False)
    use = models.BooleanField(default=False)
    log = models.BooleanField(default=False)
    diff = models.BooleanField(default=False)
    fill_na_avg = models.BooleanField(default=False)  # F: cumulative, T: avg

    def __str__(self):
        return self.name
