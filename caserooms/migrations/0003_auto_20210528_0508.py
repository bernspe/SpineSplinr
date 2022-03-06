# Generated by Django 3.1.7 on 2021-05-28 05:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('caserooms', '0002_auto_20210401_1223'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='caseroom',
            index=models.Index(fields=['owner'], name='caserooms_c_owner_i_310d1c_idx'),
        ),
        migrations.AddIndex(
            model_name='caseroomentry',
            index=models.Index(fields=['sender'], name='caserooms_c_sender__51c276_idx'),
        ),
        migrations.AddIndex(
            model_name='caseroomentry',
            index=models.Index(fields=['caseroom'], name='caserooms_c_caseroo_c5b1d8_idx'),
        ),
    ]
