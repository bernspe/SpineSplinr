# Create your tasks here
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from celery import shared_task
from celery.utils.log import get_task_logger
from django.db.models import Q
from django.template.loader import get_template
from oauth2_provider.oauth2_validators import AccessToken, RefreshToken

from users.models import User

logger = get_task_logger(__name__)

@shared_task
def clean_outdated_tokens():
    present = datetime.now().replace(tzinfo=timezone.utc)
    t=AccessToken.objects.filter(expires__lte=present)
    logger.info('Found %i outdated AccessTokens'%len(t))
    t.delete()
    t=RefreshToken.objects.filter(access_token__exact=None)
    logger.info('Found %i outdated RefreshTokens'%len(t))
    t.delete()

@shared_task
def remove_deactivated_users():
    present = datetime.now().replace(tzinfo=timezone.utc)
    rem_users=User.objects.filter(Q(is_active=False) & Q(expires__lte=present))
    rem_users.delete()

@shared_task
def inform_user_about_news():
    user_w_outstanding_news=User.objects.filter(caserooms_news__isnull=False).distinct()
    t = get_template('user/email-user-caseroom-news.html')
    for u in user_w_outstanding_news.all():
        u.email_user('Offene Nachrichten',t.render(context={'user':u}))

@shared_task
def inform_deactivated_users():
    deactivated_users=User.objects.filter(is_active=False)
    t = get_template('user/email-user-will-be-deleted.html')
    for u in deactivated_users.all():
        u.email_user('Account-Löschung',t.render(context={'user':u}))
        # if the user is still a child, notify the caregivers
        roles = [r.isChild() for r in u.roles.all()]
        if any(roles):
            cg=u.caregiver.all()
            t2 = get_template('user/email-user-will-be-deleted-caregiver.html')
            for c in cg:
                c.email_user('Account-Löschung', t2.render(context={'user': u}))
        tomorrow=datetime.now().replace(tzinfo=timezone.utc)+timedelta(days=1)
        u.expires=tomorrow
        u.save()

@shared_task
def inform_staff_about_user_status():
    user_list_status=[x.proofstatus for x in User.objects.all()]
    user_active_status=[x.is_active for x in User.objects.all()]
    user_staff=User.objects.filter(is_staff=True)
    t = get_template('user/email-staff-user-status.html')
    for u in user_staff:
        u.email_user('skoliosekinder: User Status',
                     t.render(context={
                         'status_dict': {**dict(Counter(user_list_status)),
                                         **dict(Counter(user_active_status))}}))


