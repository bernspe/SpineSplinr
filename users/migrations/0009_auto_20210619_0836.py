# Generated by Django 3.1.7 on 2021-06-19 08:36

import django.core.files.storage
from django.db import migrations, models
import users.models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_auto_20210611_1255'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='type',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='userproof',
            name='img',
            field=models.ImageField(blank=True, null=True, storage=django.core.files.storage.FileSystemStorage(location='/Volumes/1TB/Users/peterbernstein/Django/SpineSplinr/mediaprotected'), upload_to=users.models.id_jpgname),
        ),
    ]