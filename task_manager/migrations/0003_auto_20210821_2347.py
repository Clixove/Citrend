# Generated by Django 3.2.4 on 2021-08-21 15:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('task_manager', '0002_auto_20210821_2253'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='column',
            name='interp',
        ),
        migrations.RemoveField(
            model_name='column',
            name='is_feature',
        ),
        migrations.AlterField(
            model_name='column',
            name='diff',
            field=models.BooleanField(default=False),
        ),
    ]
