# Generated by Django 3.2.4 on 2021-08-24 07:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('task_manager', '0005_alter_factory_config'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='factory',
            name='processed_training_set',
        ),
    ]
