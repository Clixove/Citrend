# Generated by Django 3.2.4 on 2021-08-21 14:25

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Factory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64)),
                ('trained_time', models.DateTimeField(default=django.utils.timezone.now)),
                ('busy', models.BooleanField()),
                ('training_set', models.FileField(upload_to='data')),
                ('model', models.FileField(blank=True, null=True, upload_to='models')),
                ('transaction_sheet', models.TextField(blank=True)),
                ('score_sheet', models.TextField(blank=True)),
                ('matrix', models.FileField(blank=True, null=True, upload_to='intermediate')),
                ('config', models.TextField(blank=True)),
                ('validation_loss', models.TextField(blank=True)),
                ('mae', models.FloatField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Factories',
            },
        ),
        migrations.CreateModel(
            name='Column',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField()),
                ('belong_transaction', models.BooleanField()),
                ('is_date', models.BooleanField()),
                ('is_company', models.BooleanField()),
                ('is_score', models.BooleanField()),
                ('log', models.BooleanField()),
                ('diff', models.IntegerField()),
                ('interp', models.CharField(blank=True, max_length=64)),
                ('factory', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='task_manager.factory')),
            ],
        ),
    ]