import json
import os
import shutil
import uuid
from datetime import datetime, timedelta, timezone, date

import channels
import channels.layers
from asgiref.sync import async_to_sync
from django.contrib.auth.models import Group
from django.core.files.storage import FileSystemStorage
from django.db import models as dm, utils
from django.db.models.signals import post_delete, post_save, pre_delete, m2m_changed, pre_save
from django.dispatch import receiver
#from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from guardian.shortcuts import assign_perm, get_users_with_perms

import logging
# Get an instance of a logger
import users
from SpineSplinr import settings

#Just put any kind of celery app instance
from SpineSplinr.settings import MEDIA_ROOT, SPLINEAPP_ROOT
from splineapp.dummyworker.celery import app
from users.models import User, Userrole

logger = logging.getLogger(__name__)

protected_fs = FileSystemStorage(location=settings.MEDIA_ROOT_PROTECTED)


class OverwriteStorage(FileSystemStorage):

    def get_available_name(self, name, max_length=None):
        # If the filename already exists, remove it as if it was a true file system
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name

class ProtectedOverwriteStorage(FileSystemStorage):
    def __init__(self, option=None):
        super().__init__()
        self.location = settings.MEDIA_ROOT_PROTECTED
        self.base_url = settings.MEDIA_URL_PROTECTED

    def get_available_name(self, name, max_length=None):
        # If the filename already exists, remove it as if it was a true file system
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT_PROTECTED, name))
        return name

### Image Media Model
def img_directory_path(instance, filename):
    return 'splineapp/{0}/{1}'.format(instance.id, filename)

def get_default_expiry():
    return datetime.now(timezone.utc)+timedelta(days=1)

class SpineSplineModel(dm.Model):
    TYPES = (
        ('dummy', 'dummy'),
        ('process_xray_cobb', 'process_xray_cobb'),
        ('process_upright','process_upright'),
        ('process_bendforward', 'process_bendforward'),
        ('discarded','discarded')
    )


    STATUSES = (
        ('pending', 'pending'),
        ('started', 'started'), # worker started
        ('UPLOADED','UPLOADED'),
        ('CROP_LEVEL1','CROP_LEVEL1'),
        ('CLASSIFY_LEVEL1','CLASSIFY_LEVEL1'),
        ('CLASSIFY_LEVEL2', 'CLASSIFY_LEVEL2'),
        ('MEASURE_LEVEL1','MEASURE_LEVEL1'),
        ('MEASURE_LEVEL2', 'MEASURE_LEVEL2'),
        ('MEASURE_LEVEL3', 'MEASURE_LEVEL3'),
        ('PROTECTING','PROTECTING'),
        ('PROTECTED','PROTECTED')
    )

    type = dm.CharField(choices=TYPES, max_length=20, default='dummy')
    status = dm.CharField(choices=STATUSES, max_length=50, null=True, blank=True)
    status_dict = dm.JSONField(null=True, blank=True)
    locked = dm.BooleanField(default=False) # if someone is working the model
    id = dm.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = dm.DateTimeField(default=datetime.now, blank=True)
    title = dm.CharField(max_length=100, blank=True, default='')
    formatted_data = dm.JSONField(null=True, blank=True)
    errors_dict=dm.JSONField(null=True, blank=True)
    owner = dm.ForeignKey(settings.AUTH_USER_MODEL, related_name='splineapp', on_delete=dm.CASCADE, null=True, blank=True)
    img = dm.ImageField(upload_to=img_directory_path,default='defaultimg.jpg', max_length=255)
    man_labeled_img = dm.ImageField(upload_to=img_directory_path,default='defaultimg.jpg',storage=OverwriteStorage, max_length=255)
    modified_img = dm.ImageField(upload_to=img_directory_path,default='defaultimg.jpg',storage=OverwriteStorage, max_length=255)
    resized_img = dm.ImageField(upload_to=img_directory_path,default='defaultimg.jpg',storage=OverwriteStorage, max_length=255)
    thumb_img = dm.ImageField(upload_to=img_directory_path, default='defaultimg.jpg', storage=OverwriteStorage,
                                max_length=255)
    protected_resized_img=dm.ImageField(upload_to=img_directory_path,default='defaultimg.jpg',storage=ProtectedOverwriteStorage, max_length=255)
    protected_modified_img=dm.ImageField(upload_to=img_directory_path,default='defaultimg.jpg',storage=ProtectedOverwriteStorage, max_length=255)
    protected_man_labeled_img=dm.ImageField(upload_to=img_directory_path,default='defaultimg.jpg',storage=ProtectedOverwriteStorage, max_length=255)

    class Meta:
        indexes = [dm.Index(fields=['id', ]),
                   dm.Index(fields=['owner', ]),
                   dm.Index(fields=['status','locked' ]),
                   ]
        ordering = ['created']

    def protect_imgs(self):
        oldstatus=self.status
        try:
            resname=self.resized_img.name.rpartition('/')[-1]
            modname=self.modified_img.name.rpartition('/')[-1]
            self.status='PROTECTING'
            self.protected_resized_img.save(resname,self.resized_img.file)
            self.protected_modified_img.save(modname,self.modified_img.file)
            self.status='PROTECTED'
            imgpath = self.img.path
            pathdir = imgpath.rpartition('/')[0] + '/'
            if pathdir != SPLINEAPP_ROOT:
                shutil.rmtree(pathdir)
        except Exception as e:
            self.status=oldstatus
            print(e)

    def add_to_collection(self):
        # find a collection in the timeframe of 45 +/- self.created
        startdate = self.created - timedelta(days=45)
        enddate = self.created + timedelta(days=45)
        suiting_collection=SpineSplineCollection.objects.filter(created__range=[startdate,enddate]).first()
        if suiting_collection!=None:
            suiting_collection.items.add(self)
            transcribeResults(ssm=self, collection=suiting_collection)
            return suiting_collection
        else:
            scol=SpineSplineCollection.objects.create(owner=self.owner, created=self.created)
            scol.items.add(self)
            transcribeResults(ssm=self, collection=scol)
            # add permissions of ssm to collection
            assoc_users = get_users_with_perms(self, only_with_perms_in=['view_spinesplinemodel'])
            assign_perm('view_spinesplinecollection', assoc_users, scol)
            return scol

    def broadcast_ssm_message(self, status):
        # dispatch status to browser
        group_name = 'splineapp'
        message = {
            'ssm_id': str(self.id),
            'ssm_owner': str(self.owner),
            'status': status,
            'status_dict': json.dumps(self.status_dict),
            'locked': self.locked,
            'type': self.type,
            'created': str(self.created.isoformat()),
            'formatted_data': json.dumps(self.formatted_data)
        }
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'ssm.message',
                'text': message,
            }
        )


@receiver(pre_delete)
def notify_associate_users(sender, instance, **kwargs):
    if sender == SpineSplineModel:
        assoc_users = get_users_with_perms(instance, only_with_perms_in=['view_spinesplinemodel'])
        #
        # dispatch status to browser
        group_name = 'splineapp'
        # group_name=str(instance.id)
        message = {
            'ssm_id': str(instance.id),
            'ssm_owner': str(instance.owner),
            'assoc_users':str(assoc_users),
            'status': 'deleted',
        }

        channel_layer = channels.layers.get_channel_layer()
        print('Preparing message for %s' % str(instance.id))
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'ssm.deleted',
                'text': message
            }
        )


@receiver(pre_delete)
def delete_repo(sender, instance, **kwargs):
    if sender == SpineSplineModel:
        try:
            imgpath = instance.img.path
            pathdir = imgpath.rpartition('/')[0] + '/'
            if ((pathdir != SPLINEAPP_ROOT) & (pathdir != MEDIA_ROOT) & (~('defaultimg.jpg' in imgpath))):
                shutil.rmtree(pathdir)
        except:
            print('error while trying to delete %s'%instance.img.path)

@receiver(pre_save, sender=SpineSplineModel)
def ssm_status_manipulation(sender, instance, **kwargs):
    status=str(instance.get_status_display())

    if instance.status_dict:
        task_status=None
        if instance.formatted_data:
            if (status + '_result') in instance.formatted_data.keys():
                task_status = 'result'
        if instance.errors_dict:
            if (status + '_errors') in instance.errors_dict.keys():
                task_status = 'error'
        if task_status:
            instance.status_dict={**instance.status_dict,status:task_status}
    else:
        instance.status_dict = {status: 'pending'}

    try:
        previous = SpineSplineModel.objects.get(id=instance.id)
        instance._status_changed = (previous.status_dict != instance.status_dict) | (previous.locked != instance.locked)
    except:
        instance._status_changed = True

@receiver(post_save, sender=SpineSplineModel)
def allocate_computation(sender, instance, **kwargs):
    created = kwargs["created"]
    if created:
        owner=instance.owner #this is the child or the adult
        owner_qs=User.objects.filter(username=owner.username)
        owners_caregiver=owner.caregiver #parent of child
        cr_members=User.objects.none()
        try:
            from caserooms.models import CaseRoom
            crs=CaseRoom.objects.none()
            for caregiver in owners_caregiver.all():
                crs|=caregiver.caseroom.all() # caserooms owned by parent
            for c in crs:
                ms=c.members.all()
                if owner in ms: # if this is the caseroom the child belongs to
                     cr_members|=ms
            ocrs = owner.caseroom.all()  # caserooms owned by patient
            for c in ocrs:
                ms=c.members.all()
                cr_members |= ms
            permitted_users=(owners_caregiver.all() | cr_members | owner_qs).distinct() # assign perm to caregiver and owner and cr members
            assign_perm('view_spinesplinemodel',permitted_users , instance)
        except:
            pass

    status=str(instance.get_status_display())

    if (status=='PROTECTING'):
        return

    if instance._status_changed:
        instance.broadcast_ssm_message(status)

    if status == 'pending':
        logger.debug('Model save part before startup of worker  %s for %s.' % (instance.type,str(instance.id)))
        app.send_task('MLModelManager.tasks.invokeprocessing', args=[instance.id])

    if ((status=='CLASSIFY_LEVEL2') & (~instance.locked)):
        app.send_task('MLModelManager.tasks.measure_img', args=[instance.id])

def default_formatted_data():
    return {'id':[],
            'type':[],
            'description':[],
            'result':[]}


class SpineSplineCollection(dm.Model):
    id = dm.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = dm.DateTimeField(default=datetime.now, blank=True)
    owner = dm.ForeignKey(settings.AUTH_USER_MODEL, related_name='spinesplinecollection', on_delete=dm.CASCADE, null=True, blank=True)
    diagnoses = dm.ManyToManyField("SpineSplineDiagnosis", related_name='collection')
    therapy = dm.ManyToManyField("SpineSplineTherapy", related_name='collection')
    therapy_compliance = dm.ManyToManyField("ComplianceApproval", related_name='collection')
    items = dm.ManyToManyField("SpineSplineModel", related_name='collection')
    formatted_data = dm.JSONField(default=default_formatted_data)

    class Meta:
        indexes = [dm.Index(fields=['id', ]),
                   dm.Index(fields=['owner', ]),
                   ]
        ordering = ['created']


def transcribeResults(ssm=None, collection=None):
    type = ssm.type
    data = ssm.formatted_data["MEASURE_LEVEL2_result"]
    result={}
    description=''
    if type=='process_xray_cobb':
        description='COBB_MATRIX'
        result={"COBB_vertebrae":data["COBB_vertebrae"],
                "COBB_angles": data["COBB_angles"],
                "val_COBB_vertebrae": data["val_COBB_vertebrae"],
                "val_COBB_angles": data["val_COBB_angles"]}
    if type=='process_upright':
        description="SquaredDistances"
        result=data['SquaredDistances']
    if type=='process_bendforward':
        description="Humpangle"
        result=data['Humpangle']
    collection.formatted_data['id'].append(str(ssm.id))
    collection.formatted_data['type'].append(type)
    collection.formatted_data['description'].append(description)
    collection.formatted_data['result'].append(result)

def checkMedical():
    r = Userrole.objects.filter(category='Med')
    return {'roles__in': r}

class SpineSplineDiagnosis(dm.Model):
    DIAGNOSISTYPES = (
        ('NC','No Scoliosis from clinical point of view'),
        ('NR', 'No Scoliosis, radiologically proven'),
        ('SC','Scoliosis from clinical point of view'),
        ('SR', 'Scoliosis, radiologically proven'),
        ('U','Not sure'),
        ('P','Scoliosis postop'),
        ('B','Scoliosis inbrace')
    )

    diagnosis = dm.CharField(choices=DIAGNOSISTYPES, max_length=2, default='U')
    recommendation = dm.CharField(max_length=100, blank=True, default='')
    created = dm.DateTimeField(auto_now_add=True)
    responsible_physician = dm.ForeignKey(settings.AUTH_USER_MODEL, related_name='diagnoses', on_delete=dm.CASCADE, limit_choices_to=checkMedical)

class SpineSplineTherapy(dm.Model):
    THERAPYTYPES = (
        ('NO','No Therapy nor follow-up'),
        ('RE','Wait and Re-Evaluation'),
        ('P','Physiotherapy'),
        ('NB','Night-time brace'),
        ('DB','Full-time brace'),
        ('S','Sugery')
    )

    therapy = dm.CharField(choices=THERAPYTYPES,max_length=2,default='NO')
    created = dm.DateTimeField(auto_now_add=True)

class ComplianceApproval(dm.Model):
    approval_date= dm.DateTimeField(auto_now_add=True)
    compliance_witness = dm.ForeignKey(settings.AUTH_USER_MODEL, related_name='compliance_witness', on_delete=dm.CASCADE, null=True, blank=True)
