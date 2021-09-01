from django.contrib import admin
from .models import Predict

@admin.register(Predict)
class PredictAdmin(admin.ModelAdmin):
    pass
