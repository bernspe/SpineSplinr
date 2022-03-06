# Create your tasks here
from __future__ import absolute_import, unicode_literals
from functools import wraps
from celery.utils.log import get_task_logger

from splineapp.dummyworker.celery import app
from splineapp.models import SpineSplineModel
# Get an instance of a logger

logger = get_task_logger('celery.task3')


## MAIN ###
## Task Area
def update_job(fn):
    @wraps(fn)
    def wrapper(img_id, *args, **kwargs):
        ssm = SpineSplineModel.objects.get(id=img_id)
        ssm.status = 'started'
        ssm.save()
        try:
            result = fn(img_id,ssm,*args, **kwargs)
            if result == 'OK':
                ssm.status = 'finished'
                ssm.save()
            else:
                ssm.status = 'failed'
                ssm.save()
                logger.error('Some errors occured inside wrapped task')
        except Exception as e:
            ssm.status = 'failed'
            logger.error('Some errors occured inside wrapped task, Task raised exception: %s'%str(e))
            ssm.save()
    return wrapper


@app.task
@update_job
def dummytask(img_id,ssm):
    print('Dummy started for ID: %s'%img_id)

    return 'OK'
