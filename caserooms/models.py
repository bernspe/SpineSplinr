import uuid
from datetime import datetime, timedelta, timezone

import channels
import channels.layers
from asgiref.sync import async_to_sync
from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.db import models
from guardian.shortcuts import assign_perm, remove_perm

from SpineSplinr import settings
from SpineSplinr.messages import MSG_WHEN_CR_OWNER_CONSENT_IS_NEEDED
from SpineSplinr.settings import DEFAULT_EXPIRY, GEN_STAFF_USER
from splineapp.models import SpineSplineModel, SpineSplineCollection
from users.models import User, consent


def get_default_expiry():
    return datetime.now(timezone.utc)+timedelta(days=DEFAULT_EXPIRY)

# Create your models here.
class CaseRoom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    expires = models.DateTimeField(default=get_default_expiry)
    title = models.CharField(max_length=100, blank=True, default='Caseroom')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='caseroom', on_delete=models.CASCADE, null=True, blank=True)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='caserooms') #, limit_choices_to={'role': [n[0] for n in USERROLES[0:5]]}
    news_for_participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='caserooms_news', blank=True)
    email_reminder_for_participants= models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='caserooms_email', blank=True)

    class Meta:
        indexes = [models.Index(fields=['id', ]),
                   models.Index(fields=['owner', ]),
                   ]

    def __str__(self):
        return str(self.id)

    def get_members_str(self):
        """
        :return: string representation of members
        """
        return ",".join(str(s) for s in self.members.all())

    def get_members_and_owner_str(self):
        s=self.get_members_str()
        if len(s)>0:
            return s+','+str(self.owner)
        else:
            return str(self.owner)

    def get_members_and_owners_with_active_SSM(self):
        user_w_ssm = User.objects.filter(Q(splineapp__isnull=False) & (Q(caseroom=self) | Q(caserooms=self))).distinct()
        return user_w_ssm

    def add_user_to_cr(self,user):
        self.members.add(user)
        self.save()

    def delete_user_from_cr(self,user):
        self.news_for_participants.remove(user)
        self.email_reminder_for_participants.remove(user)
        # make a mark in the cr entries, so that they can be attributed to the leaving user
        cre = CaseRoomEntry.objects.filter(Q(sender=user) & Q(caseroom=self))
        for entry in cre:
            entry.text += '(' + user.get_full_name() + ')'
            entry.save()
        # remove permission from relevant SSM
        cats = [r.category for r in user.roles.all()]
        if ('Med' in cats):  # remove permission only for medicals
            user_w_ssm = User.objects.filter(
                Q(splineapp__isnull=False) & (Q(caseroom=self) | Q(caserooms=self))).distinct()
            all_crs_leaving_user = user.caserooms.all()
            for u in user_w_ssm:
                caserooms_of_interest = all_crs_leaving_user.intersection(u.caserooms.all())
                if (len(caserooms_of_interest) == 1):
                    try:
                        remove_perm('view_spinesplinemodel', user, u.splineapp.all())
                        print('Removed permission m: %s, ssm: %s' % (str(user.email), str(u.splineapp.all())))
                    except:
                        print('Failed to remove permission m: %s, ssm: %s' % (str(user.email), str(u.splineapp.all())))
                    try:
                        remove_perm('view_spinesplinecollection', user, u.spinesplinecollection.all())
                    except:
                        print('Failed to remove permission m: %s, collection: %s' % (str(user.email), str(u.spinesplinecollection.all())))
        # remove user from cr member list
        user.caserooms.remove(self)
        user.save()
        group_name = 'splineapp'
        message = {
            'caseroom': str(self.id),
            'caseroom_owner': str(self.owner),
            'caseroom_members': self.get_members_str(),
            'status': 'left'
        }
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.group_send)(group_name,
                                                {
                                                    'type': 'caseroom.changed',
                                                    'text': message
                                                })



    def is_sufficiently_consented(self):
        """
        check whether all involved members are defined in a valid consented doc
        :return:
        """
        consents = consent.objects.filter(referring_User=self.owner, withdraw_date=None, referring_Caseroom=self).all()
        if len(consents)>0:
            inv_users=User.objects.none()
            for c in consents.all():
                inv_users |= c.involved_users.all()
            inv_users_intersection= inv_users.distinct().intersection(self.members.all())
            if len(self.members.all()) == len(inv_users_intersection):
                return True, None
            else:
                inv_users_difference = self.members.difference(inv_users)
        else:
            inv_users_difference=self.members.all()
        return False, inv_users_difference

    def msg_to_caseroom_owner_if_consent_is_needed(self):
        """
        Dispatch a message to caseroom owner when his consent is needed
        :return:
        """
        msg=self.owner.first_name+', '+MSG_WHEN_CR_OWNER_CONSENT_IS_NEEDED+'$ACTION=caseroom:'+str(self.id)
        su = User.objects.get(username=GEN_STAFF_USER['username'])
        self.owner.msg_user(msg,from_user=su)

    def msg_caseroom_watched(self, sender):
        """
        Dispatch message to caseroom members / owner
        :param sender:
        :param instance:
        :param kwargs:
        :return:
        """
        group_name = 'splineapp'
        message = {
            'caseroom': str(self.id),
            'caseroom_sender': str(sender),
            'caseroom_participants': self.get_members_and_owner_str(),
            'status': 'watched',
        }

        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'caseroom.watched',
                'text': message,
            }
        )

    def get_last_msg(self):
        try:
            msg = self.caseroomentry_set.latest('created')
            return msg
        except:
            return None





class CaseRoomEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='caseroomentry', on_delete=models.CASCADE, null=True, blank=True)
    caseroom = models.ForeignKey(CaseRoom, on_delete=models.CASCADE)
    text = models.CharField(max_length=400, blank=True, default='')

    class Meta:
        indexes = [models.Index(fields=['id', ]),
                   models.Index(fields=['sender', ]),
                   models.Index(fields=['caseroom', ]),]


@receiver(post_save, sender=CaseRoom)
def msg_caseroom_created_or_updated(sender, instance, **kwargs):
    """
    This method creates a websocket message to users (owner + members) via the splineapp websocket announcing a caseroom creation or update
    :param sender:
    :param instance:
    :param kwargs:
    :return:
    """
    if (len(instance.members.all())==0):
        return

    group_name = 'splineapp'
    message = {
        'caseroom':str(instance.id),
        'caseroom_owner': str(instance.owner),
        'caseroom_members': instance.get_members_str(),
        'status': 'created'
    }

    channel_layer=channels.layers.get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'caseroom.changed',
            'text':message
        }
    )
    # adding ssm and collection permissions to all members
    ssms=SpineSplineModel.objects.filter(Q(owner__in=instance.members.all())|Q(owner=instance.owner))
    scols=SpineSplineCollection.objects.filter(Q(owner__in=instance.members.all())|Q(owner=instance.owner))
    for m in instance.members.all():
        try:
            assign_perm('view_spinesplinemodel',m, ssms.all())
            assign_perm('view_spinesplinecollection', m, scols.all())
            print('Add paermission m: %s, ssms: %s' % (str(m.email), str(ssms.all())))
        except:
            print('Failed to add paermission m: %s, ssms: %s'%(str(m.email),str(ssms.all())))

@receiver(pre_delete, sender=CaseRoom)
def msg_caseroom_delete(sender, instance, **kwargs):
    if (len(instance.members.all())==0):
        return
    group_name = 'splineapp'
    message = {
        'caseroom':str(instance.id),
        'caseroom_owner': str(instance.owner),
        'caseroom_members': instance.get_members_str(),
        'status': 'deleted'
    }

    channel_layer=channels.layers.get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'caseroom.changed',
            'text':message
        }
    )
    user_w_ssm = User.objects.filter(
        Q(splineapp__isnull=False) & (Q(caseroom=instance) | Q(caserooms=instance))).distinct()
    for u in user_w_ssm:
        caserooms_of_interest = (u.caserooms.all() | u.caseroom.all()).distinct()  # get the cr by member- and ownership
        try:
            members=instance.members.all().difference(user_w_ssm)
        except:
            members = instance.members.all()
        if len(caserooms_of_interest) == 1:
            for m in members:
                try:
                    remove_perm('view_spinesplinemodel', m, u.splineapp.all())
                    print('Removed paermission m: %s, ssm: %s' % (str(m.email), str(u.splineapp.all())))
                except:
                    print('Failed to Remove paermission m: %s, ssm: %s' % (str(m.email), str(u.splineapp.all())))
                try:
                    remove_perm('view_spinesplinecollection', m, u.spinesplinecollection.all())
                except:
                    print('Failed to Remove paermission m: %s, collection: %s' % (str(m.email), str(u.spinesplinecollection.all())))
        else:   # the user_w_ssm is present in more than one cr
            for m in members:
                m_cr=m.caserooms.all() # get all the crs the member is member in
                cr_diff=caserooms_of_interest.difference(m_cr) # if those are all the same: do nothing
                if len(cr_diff)>0: # if those crs are not the same population as the deleted one
                    try:
                        remove_perm('view_spinesplinemodel', m, u.splineapp.all())  #remove the rights
                        print('Removed paermission m: %s, ssm: %s' % (str(m.email), str(u.splineapp.all())))
                    except:
                        print('Failed to Remove paermission m: %s, ssm: %s' % (str(m.email), str(u.splineapp.all())))
                    try:
                        remove_perm('view_spinesplinecollection', m, u.spinesplinecollection.all())
                    except:
                        print('Failed to Remove paermission m: %s, collection: %s' % (str(m.email), str(u.spinesplinecollection.all())))

@receiver(post_save, sender=CaseRoomEntry)
def msg_caseroomentry_created(sender, instance, **kwargs):
    """
    Dispatch message to caseroom members / owner
    :param sender:
    :param instance:
    :param kwargs:
    :return:
    """
    group_name = 'splineapp'
    message = {
        'id': str(instance.id),
        'caseroom':str(instance.caseroom),
        'caseroom_sender': str(instance.sender),
        'caseroom_participants': instance.caseroom.get_members_and_owner_str(),
        'caseroom_entry_created': str(instance.created),
        'caseroom_entry_text': str(instance.text),
        'status': 'created',
    }

    channel_layer=channels.layers.get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'caseroom.message',
            'text':message,
        }
    )

