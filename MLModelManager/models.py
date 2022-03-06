import json
import os
import shutil
import uuid
import pandas as pd

from django.core.files.storage import FileSystemStorage
from django.db import models

# Create your models here.
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from SpineSplinr import settings
from SpineSplinr.settings import MLMODEL_DIR


vertebrae=['T1','T2','T3','T4','T5','T6','T7','T8','T9','T10','T11','T12','L1','L2','L3','L4','L5']


class OverwriteStorage(FileSystemStorage):
    def get_available_name(self, name, max_length=None):
        # If the filename already exists, remove it as if it was a true file system
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name

class MLModel(models.Model):
    TYPES = (
        ('dummy', 'dummy'),
        ('dataset','dataset'),
        ('cropresize_img','cropresize_img'),
        ('categorize_img','categorize_img'),
        ('process_xray_cobb', 'process_xray_cobb'),
        ('process_upright','process_upright'),
        ('process_bendforward', 'process_bendforward')
    )
    STATUSES = (
        ('created','created'),
        ('tested','tested'),
        ('standby','standby'),
        ('busy','busy')
    )
    type = models.CharField(choices=TYPES, max_length=20, default='dummy')
    status = models.CharField(choices=STATUSES, max_length=20, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=100, blank=True, default='')
    performance = models.JSONField(null=True, blank=True)
    version =models.CharField(max_length=10, blank=True, default='')
    is_active = models.BooleanField(default=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='mlmodel', on_delete=models.SET_NULL, null=True, blank=True)

    def getPerformance(self):
        if self.type=='process_xray_cobb':
            return pd.DataFrame(json.loads(self.performance), columns=vertebrae)
        d=json.loads(self.performance)
        df=pd.DataFrame.from_dict(d, orient='index').T.astype(float)
        return df

@receiver(post_save, sender=MLModel)
def make_results_dir(sender, instance, **kwargs):
    created = kwargs["created"]
    if ((created) & (instance.type!='dataset')):
        try:
            path=MLMODEL_DIR+'/'+str(instance.id)+'/results/'
            os.umask(0)
            os.makedirs(path, 0o777)
        except Exception as e:
            print('Exception while trying to make Results Folder: %s'%str(e))


@receiver(post_delete)
def delete_mlmodel(sender, instance, **kwargs):
    if sender == MLModel:
        try:
            pathdir = MLMODEL_DIR+'/'+str(instance.id)+'/'
            shutil.rmtree(pathdir)
        except:
            print('error while trying to delete %s' % pathdir)

def model_directory_path(instance, filename):
    return 'mlmodels/{0}/{1}'.format(instance.mlmodel.id, filename)

class MLFile(models.Model):
    mlmodel = models.ForeignKey(MLModel, on_delete=models.CASCADE)
    file = models.FileField(upload_to=model_directory_path, blank=True, storage=OverwriteStorage, max_length=255)

