# Generated by Django 3.1.7 on 2021-06-11 12:55

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_auto_20210611_1230'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='referring_User',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='device',
            name='uuid',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
