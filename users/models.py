from __future__ import unicode_literals

import os
import string
import random
import uuid
from functools import reduce
from datetime import date

import htmlmin
import yagmail as yagmail
from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import InMemoryUploadedFile

from django.db import models
from django.contrib.auth.models import PermissionsMixin, AbstractUser, Group
from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_save, m2m_changed
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from datetime import datetime, timedelta, timezone
import channels
import channels.layers
from asgiref.sync import async_to_sync

from SpineSplinr import settings
from SpineSplinr.messages import MSG_WHEN_CR_OWNER_CONSENT_IS_NEEDED, MSG_DONE
from SpineSplinr.settings import DEFAULT_EXPIRY, MEDIA_ROOT
from users.pdf_utils import UserQRCode

protected_fs = FileSystemStorage(location=settings.MEDIA_ROOT_PROTECTED, base_url=settings.MEDIA_URL_PROTECTED)

def get_sentinel_user():
    return get_user_model().objects.get_or_create(username='deletedUser',email='bernspe+deleted@gmail.com')[0]


class Userrole(models.Model):
    role=models.CharField(max_length=30, primary_key=True, unique=True)
    translations=models.JSONField(blank=True, null=True)
    category=models.CharField(max_length=30, blank=True, null=True)
    proof=models.CharField(max_length=30, blank=True, null=True)
    consents = models.CharField(max_length=20, blank=True, null=True)

    def isUserType(self):
        if self.category=='Staff':
            return False
        else:
            return True

    def isStaffType(self):
        if self.category=='Staff':
            return True
        else:
            return False

    def isCaregiver(self):
        return (self.category=='Caregiver')

    def isChild(self):
        return (self.category=='Child')

    def isAdult(self):
        return (self.category=='Adult')

    def isPatient(self):
        return (self.category=='Patient')

    def isMed(self):
        return (self.category=='Med')


USERROLES=(
    ('MedPhysician','Physician'),
    ('MedPediatric','Pediatric Physician'),
    ('MedOrthopaedic','Orthopaedic Physician'),
    ('MedSpecialist','Scoliosis Specialist'),
    ('MedOrthoTechnician', 'Orthopaedic Technician'),
    ('ChildNoScoliosis','Child without Scoliosis'),
    ('ChildScoliosis','Child with Scoliosis'),
    ('AdultPatient','Adult Patient'),
    ('Caregiver','Caregiver'),
    ('CaregiverNPatient', 'Caregiver and Patient'),
    ('Volunteer', 'Volunteer'),
    ('Analyzer', 'Analyzer'),
    ('AnalyzerSupervisor', 'Analyzer Supervisor'),
    ('DevResearcher','Researcher'),
    ('Developer','Developer'),
    ('Patron','Patron'),
    ('Guest','Guest')
)

PROOFSTATUS = (
    ('INVITED','INVITED'),
    ('NONPROVEN','NONPROVEN'),
    ('VALIDATED','VALIDATED'),
)

def get_specific_role_group(group):
    return tuple(n for n in USERROLES if group in n[0])

def get_default_expiry():
    return datetime.now(timezone.utc)+timedelta(days=DEFAULT_EXPIRY)

def id_jpgname(instance,filename):
    return 'userproofs/{0}.jpg'.format(instance.id)

def username_qrcode(instance,filename):
    return 'userqrcodes/{0}.png'.format(instance.username)

def get_user_document_path(instance, filename):
    return 'user_docs/{0}.md'.format(instance.username)

class OverwriteStorage(FileSystemStorage):
    def get_available_name(self, name, max_length=None):
        # If the filename already exists, remove it as if it was a true file system
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name

class User(AbstractUser, PermissionsMixin):
    email = models.EmailField(_('email address'), unique=True)

    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=30, blank=True)
    date_of_birth = models.DateField(_('date of birth'), null=True, blank=True)
    sex = models.CharField(_('sex'), max_length=10, null=True, blank=True)
    username = models.CharField(_('username'), max_length=100, unique=True, primary_key=True) # will be UUID in case of self register
    dependent_children = models.ManyToManyField("self",related_name='caregiver',symmetrical=False, blank=True)
    postal_address=models.CharField(_('address'), max_length=100, blank=True)
    phone_number=models.CharField(_('phone number'), max_length=20, blank=True)
    login_qrcode=models.ImageField(upload_to=username_qrcode, null=True, blank=True,storage=protected_fs)

    date_joined = models.DateTimeField(_('date joined'), auto_now_add=True)
    last_login = models.DateTimeField(_('last login'), null=True, blank=True)
    next_scheduled_visit = models.DateTimeField(_('next scheduled visit'), null=True, blank=True)

    expires = models.DateTimeField(default=get_default_expiry)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, storage=OverwriteStorage)

    is_staff = models.BooleanField(default=False)
    is_admin=models.BooleanField(default=False)
    is_superuser=models.BooleanField(default=False)
    is_emailvalidated=models.BooleanField(default=False)
    roles = models.ManyToManyField('Userrole', related_name='userrole', blank=True)
    proofstatus = models.CharField(choices=PROOFSTATUS, max_length=20, null=True, blank=True)
    instruction_level = models.CharField(_('instruction level'), max_length=30, blank=True)
    component_trace = models.JSONField(null=True,blank=True)
    document = models.FileField(upload_to=get_user_document_path, default='default_user.md', storage=OverwriteStorage)

    emailtoken = models.CharField(_('email token'), max_length=6, blank=True)

    class Meta:
        indexes = [models.Index(fields=['username', ]),
                   models.Index(fields=['email', ]),]

    def __str__(self):
        return f'{self.username}'

    def save(self, *args, **kwargs):
        self.full_clean() # performs regular validation then clean()
        super(User, self).save(*args, **kwargs)


    def clean(self):
        if self.first_name:
            self.first_name = self.first_name.strip()
        if self.last_name:
            self.last_name = self.last_name.strip()

    def toggleActivation(self):
        self.is_active=not self.is_active
        self.save()

    def get_full_name(self):
        '''
        Returns the first_name plus the last_name, with a space in between.
        '''
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def isChildFromAge(self):
        today = date.today()
        born=self.date_of_birth
        if born:
            return (today.year - born.year - ((today.month, today.day) < (born.month, born.day))) < 16
        return False

    def isTeenagerFromAge(self):
        today = date.today()
        born=self.date_of_birth
        if born:
            age = (today.year - born.year - ((today.month, today.day) < (born.month, born.day)))
            return (age < 18) & (age > 15)
        return False

    def create_login_qrcode(self, notify=None):
        image_field = self.login_qrcode
        img_name = str(self.username)+'.png'
        #qr = UserQRCode(useremail=self.email, notify=notify)
        qr = UserQRCode(username=self.username, notify=notify)
        qrimg = qr.getQRCodeAsContentFile()
        image_field.save(img_name, InMemoryUploadedFile(
            qrimg,  # file
            None,  # field_name
            img_name,  # file name
            'image/png',  # content_type
            qrimg.tell,  # size
            None)  # content_type_extra
        )

    def msg_when_invited_user_logged_in(self, invited_user=None):
        """
        Sends a WS message to self when invited_user logged in
        """
        group_name = 'splineapp'
        message = {
            'adressee': str(self.username),
            'logged_in_user': str(invited_user.username),
            'logged_in_user_fullname': invited_user.get_full_name()
        }
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'user.loggedin',
                'text': message,
            }
        )

    def msg_when_invited_user_denied_login(self, invited_user=None):
        """
        Sends a WS message to self when invited_user logged in
        """
        group_name = 'splineapp'
        message = {
            'adressee': str(self.username),
            'invited_user': str(invited_user.username),
            'invited_user_fullname': invited_user.get_full_name()
        }
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'user.deniedlogin',
                'text': message,
            }
        )


    def create_email_token(self):
        """
        Creates a 6digit Token to be sent via email
        :return:
        """
        #letters = string.ascii_letters
        letters=string.digits
        result_str = ''.join(random.choice(letters) for i in range(6))
        return result_str

    def email_user(self, subject, message, from_email=None, **kwargs):
        '''
        Sends an email via Gmail Account to this User.
        '''
        msg_minified=htmlmin.minify(message)
        yagmail.SMTP(settings.EMAIL_ACCOUNT_NAME, settings.EMAIL_ACCOUNT_KEY).send(self.email, subject, msg_minified)
        #official Django alternative
        #msg = EmailMessage(subject, message, from_email, [self.email])
        #msg.content_subtype = "html"  # Main content is now text/html
        #msg.send()

    def msg_user(self,message,from_user=None):
        from caserooms.models import CaseRoomEntry
        '''
        Sends a msg to the helpdesk caseroom of the user
        :param message:
        :param from_user:
        :return:
        '''
        cr = self.caseroom.get(title__contains=settings.HELPDESK_NAME)
        # create a new cr-entry and add sender, if not present in cr members
        if from_user in cr.members.all():
            pass
        else:
            cr.members.add(from_user)
            cr.save()
        cre,_=CaseRoomEntry.objects.get_or_create(caseroom=cr, sender=from_user,text=message)
        cre.save()


    def removeHelpdeskNotification(self):
        from caserooms.models import CaseRoomEntry
        try:
            cr = self.caseroom.get(title__contains=settings.HELPDESK_NAME)
            cre = CaseRoomEntry.objects.filter(Q(caseroom=cr) & Q(text__contains=MSG_WHEN_CR_OWNER_CONSENT_IS_NEEDED) & ~Q(text__contains=MSG_WHEN_CR_OWNER_CONSENT_IS_NEEDED+MSG_DONE))
            if len(cre)>0:
                target_cre=cre.last()
                target_cre.text=MSG_WHEN_CR_OWNER_CONSENT_IS_NEEDED+MSG_DONE
                target_cre.save()
        except:
            pass

    def has_expired(self):
        present = datetime.now().replace(tzinfo=timezone.utc)
        return present > self.expires

    def is_validated(self):
        return self.proofstatus=='VALIDATED'

    def needs_role_specific_consents(self):
        #this function will return roles-specific consent types not yet given by the user
        #it returns an empty list, if all necessary consents have been given
        #get necessary consent types
        s=set()
        for r in self.roles.all():
            try:
                for c in r.consents.split(','):
                    s.add(c.strip())
            except:
                pass
        #now check users valid consents and subtract them from necessary ones and see if anything remains
        hasP0 = False
        for c in self.consent_set.all():
            if c.withdraw_date:
                pass #ignore the withdrawn consents
            else:
                try:
                    if (c.consent_content.consent_type=='P0'):
                        hasP0=True
                    s.remove(c.consent_content.consent_type)
                except:
                    continue
        return list(s),hasP0

    def needs_role_specific_proofs(self):
        #this function will return roles-specific proof types not yet given by the user

        s=set()
        for r in self.roles.all():
            for c in r.proof.split(','):
                if ((c=='nan') | (c=='')):
                    pass
                else:
                    s.add(c.strip())
        #now check users valid proofs and subtract them from necessary ones and see if anything remains
        for c in self.userproof_set.all():
            try:
                s.remove(c.proof_type)
            except:
                pass
        return list(s)

    def set_user_group(self):
        #This function set's the user group to valid user or staff if requirements are met.
        #returns true if valid user or staff member or
        #false and missing requirements as second parameter
        self.groups.clear()
        #Checks if a user fulfills all requirements to be a valid user
        roles = [r.isUserType() for r in self.roles.all()]
        if any(roles):
            UserType = reduce(lambda a,b: a|b, roles)
        else:
            UserType = False
        roles = [r.isStaffType() for r in self.roles.all()]
        if len(roles)>0:
            StaffType = reduce(lambda a,b: a|b, roles)
        else:
            StaffType = False
        if (self.is_staff | self.is_admin | self.is_superuser):
            StaffType=True
        missing_role_specific_consents,hasP0consent=self.needs_role_specific_consents()
        consentscomplete = (len(missing_role_specific_consents)==0)
        #check if dependent teenagers have given their consent and are validated
        roles = [r.isCaregiver() for r in self.roles.all()]
        if any(roles):
            CaregiverType = reduce(lambda a,b: a|b, roles)
        else:
            CaregiverType = False
        childrenconsentscomplete=True
        if (CaregiverType & (len(self.dependent_children.all())>0)):
            missingchildrenconsents = [len(c.needs_role_specific_consents()[0]) for c in self.dependent_children.all()]
            # allchildrenvalidated = all([c.is_validated() for c in self.dependent_children.all()])
            # children need not be validated
            childrenconsentscomplete=(sum(missingchildrenconsents)==0)
            #if (sum(missingchildrenconsents)>0) | (not allchildrenvalidated):
            #    childrenconsentscomplete=False

        # Check if every child has an assigned caregiver
        caregivercomplete = True
        roles = [r.isChild() for r in self.roles.all()]
        if any(roles):
            ChildType = reduce(lambda a,b: a|b, roles)
        else:
            ChildType = False
        if ChildType:
            CaregiverType=False
            if len(self.caregiver.all())==0:
                caregivercomplete=False
        #now put the whole thing together
        validityArray = [(not self.has_expired()) ,
                   self.is_active ,
                   (self.proofstatus=='VALIDATED') ,
                   self.is_emailvalidated ,
                   (self.instruction_level == 'BASIC') ,
                   (UserType | StaffType) , consentscomplete , childrenconsentscomplete, caregivercomplete,hasP0consent]
        validityLabels=['has_expired' ,
                   'is_active' ,
                   'proofstatus' ,
                   'is_emailvalidated' ,
                   'instruction_level'  ,
                   'UserType OR StaffType' , 'consentscomplete' , 'childrenconsentscomplete','caregivercomplete','hasP0consent']
        noneValidItems=[label for item,label in zip(validityArray,validityLabels) if (not item)]
        validity = reduce(lambda a,b: a&b, validityArray)
        #make a proposition for group
        if UserType & validity:
            self.groups.add(Group.objects.get(name='Validated User'))
        if StaffType & validity & (self.is_staff | self.is_admin | self.is_superuser):
            self.groups.add(Group.objects.get(name='Staff'))
        if (not validity):
            self.groups.add(Group.objects.get(name='Non validated User'))
        return validity, noneValidItems

@receiver(post_delete)
def delete_userdocument(sender, instance, **kwargs):
    if sender == User:
        try:
            docpath = instance.document.path
            pathdir = docpath.rpartition('/')[0]
            if pathdir != MEDIA_ROOT:
                os.remove(docpath)
        except:
            print('error while trying to delete %s'%instance.document.path)

@receiver(post_delete)
def delete_userqrcode(sender, instance, **kwargs):
    if sender == User:
        try:
            if instance.login_qrcode:
                qrpath = instance.login_qrcode.path
                os.remove(qrpath)
        except:
            print('error while trying to delete %s'%instance.login_qrcode.path)

class Device(models.Model):
    referring_User = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    uuid=models.CharField(max_length=50, null=True, blank=True)
    type=models.CharField(max_length=255, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['uuid', ]),]


class UserProof(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referring_User = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    proof_type = models.CharField(max_length=30, null=True, blank=True)
    img = models.ImageField(upload_to=id_jpgname, null=True, blank=True,storage=protected_fs)
    created = models.DateTimeField(auto_now_add=True)
    checkedby = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='userproofchecked', null=True, blank=True)

@receiver(post_delete)
def delete_proofdocument(sender, instance, **kwargs):
    if sender == UserProof:
        try:
            docpath = instance.img.path
            os.remove(docpath)
        except:
            print('error while trying to delete %s'%instance.img.path)

#@receiver(post_save, sender=User)
#def create_default_user_permissions(sender, instance, created, **kwargs):
#    if created:
#        instance.user_permissions.set(['users.user.view_user', 'users.user.change_user'])

CONTRIBUTIONTYPES=(
    ('MONEY_DONATION','MONEY_DONATION'),
    ('MONEY_PAYMENT','MONEY_PAYMENT'),
    ('TIME','TIME'),
    ('DATA','DATA'),
    ('CONTACTS','CONTACTS'),
    ('MISC','MISC')
)

class contribution(models.Model):
    referring_User = models.ForeignKey(User, on_delete=models.CASCADE)
    contribution_date = models.DateTimeField(_('contribution date'), auto_now_add=True)
    contribution_type=models.CharField(choices=CONTRIBUTIONTYPES, max_length=30)
    quantity=models.DecimalField(max_digits=7, decimal_places=2)
    add_info=models.CharField(_('additional information'), max_length=100, blank=True)
    validated = models.BooleanField(default=False)


COSTTYPES=(
    ('CALCULATION','CALCULATION'),
    ('MANUAL CORRECTION','MANUAL CORRECTION'),
    ('MISC','MISC')
)

class cost(models.Model):
    referring_User = models.ForeignKey(User, on_delete=models.CASCADE)
    cost_date = models.DateTimeField(_('cost date'), auto_now_add=True)
    cost_type=models.CharField(choices=COSTTYPES, max_length=30)
    quantity=models.DecimalField(max_digits=7, decimal_places=2)
    add_info=models.CharField(_('additional information'), max_length=100, blank=True)


def get_consent_document_path(instance, filename):
    return 'consent_docs/{0}/{1}.md'.format(instance.consent_type,instance.id)

CONSENTTYPES=(
    ('P0', 'DGSVO AND GENERAL CONSENT'),
    ('P1A','IDENTITY CONSENT ADULT'),
    ('P1B','CONSENT CAREGIVER'),
    ('P1C', 'INFORMATION CHILD'),
    ('P1D', 'CONSENT TEENAGER'),
    ('P2', 'IMAGE PROCESSING CONSENT'),
    ('P2A', 'IMAGE PROCESSING CONSENT ADULT'),
    ('P2B', 'IMAGE PROCESSING CONSENT CAREGIVER'),
    ('P2C', 'IMAGE PROCESSING INFORMATION CHILD'),
    ('P2D', 'IMAGE PROCESSING CONSENT TEENAGER'),
    ('P2E', 'IMAGE PROCESSING CONSENT PHYSICIAN'),
    ('P3', 'DATA TRANSFER CONSENT'),
    ('P4', 'OPEN DATA SHARE CONSENT'),
    ('P5', 'CONFIDENTIALITY STATEMENT')
)

class ConsentContent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consent_type=models.CharField(max_length=30)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    document = models.FileField(upload_to=get_consent_document_path, default='default.md')
    add_info=models.CharField(_('additional information'), max_length=100, blank=True)

@receiver(post_delete)
def delete_consentdocument(sender, instance, **kwargs):
    if sender == ConsentContent:
        try:
            docpath = instance.document.path
            os.remove(docpath)
        except:
            print('error while trying to delete %s'%instance.document.path)

class consent(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referring_User = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    referring_Caseroom = models.ForeignKey('caserooms.CaseRoom', on_delete=models.CASCADE, null=True, blank=True)
    consent_date = models.DateTimeField(_('consent date'), auto_now_add=True)
    withdraw_date = models.DateTimeField(_('withdraw date'), null=True, blank=True)
    consent_content = models.ForeignKey(ConsentContent, on_delete=models.PROTECT, null=True, blank=True)
    involved_users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='consenttarget', blank=True)

# Auditlog

#auditlog.register(User, exclude_fields=['date_joined'])