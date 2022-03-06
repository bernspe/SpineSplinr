from __future__ import absolute_import, unicode_literals

import os

from celery import Celery

# set the default Django settings module for the 'celery' program.
from celery.signals import setup_logging
from SpineSplinr import settings
#from splineapp.models import SpineSplineModel

app = Celery('dummy')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SpineSplinr.settings')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS+['splineapp.dummyworker'])
#app.autodiscover_tasks(packages=['splineapp.dummyworker'])

@setup_logging.connect
def config_loggers(*args,**kwargs):
    from logging.config import dictConfig
    dictConfig(settings.LOGGING)

#@app.task(bind=True)
#def debug_task(self):
#    print('Request: {0!r}'.format(self.request))
