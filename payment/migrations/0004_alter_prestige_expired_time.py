# Generated by Django 3.2.4 on 2021-08-23 11:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0003_auto_20210823_1728'),
    ]

    operations = [
        migrations.AlterField(
            model_name='prestige',
            name='expired_time',
            field=models.DateTimeField(null=True),
        ),
    ]