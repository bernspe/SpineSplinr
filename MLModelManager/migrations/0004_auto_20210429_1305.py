# Generated by Django 3.1.7 on 2021-04-29 13:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MLModelManager', '0003_auto_20210424_1052'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mlmodel',
            name='type',
            field=models.CharField(choices=[('dummy', 'dummy'), ('dataset', 'dataset'), ('cropresize_img', 'cropresize_img'), ('categorize_img', 'categorize_img'), ('process_xray_cobb', 'process_xray_cobb'), ('process_upright', 'process_upright'), ('process_bendforward', 'process_bendforward')], default='dummy', max_length=20),
        ),
    ]