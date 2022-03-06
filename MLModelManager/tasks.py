# Create your tasks here
import importlib
import io
import json
import os
import sys
import time
import traceback
from contextlib import redirect_stdout

from PIL import Image
from numpy import float32
from pandas.core.common import flatten

import channels
from celery import shared_task, chain
from celery.utils.log import get_task_logger
from asgiref.sync import async_to_sync
from django.db.models import Q
from django.core.files.uploadedfile import InMemoryUploadedFile
from MLModelManager.models import MLModel
from SpineSplinr.settings import MLMODEL_DIR, MLMODEL_URL, BASE_URL, MEDIA_ROOT, SPLINEAPP_ROOT
from splineapp.label_utils import label_upright, label_bendforward
from splineapp.label_utils import label_xray_spline
from splineapp.spline_calculators import WaistCalculator
from splineapp.models import SpineSplineModel

logger = get_task_logger(__name__)

@shared_task
def pushToRemoteConsoleAsync(id):
    global remote_stdout

    group_name = 'mlmodel'
    channel_layer = channels.layers.get_channel_layer()
    i = 0
    sys.stdout = remote_stdout
    while True:
        time.sleep(2)
        print('Firing messages %i' % i)
        i += 1
        message = {
            'id': str(id),
            'msg_console': remote_stdout.getvalue()
        }
        remote_stdout.seek(0)
        remote_stdout.truncate(0)
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'mlmodel.message',
                'text': message,
            }
         )

def pushToRemoteConsole(id, remote_stdout):
    group_name = 'mlmodel'
    channel_layer = channels.layers.get_channel_layer()
    message = {
        'id': str(id),
        'msg_console': remote_stdout.getvalue()
    }
    remote_stdout.seek(0)
    remote_stdout.truncate(0)
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'mlmodel.message',
            'text': message,
        }
     )

def pushToRemoteResult(id, prediction, performance, img):
    group_name = 'mlmodel'
    channel_layer = channels.layers.get_channel_layer()
    message = {
        'id': str(id),
        'msg_prediction': str(prediction),
        'msg_performance': str(performance),
        'msg_image': MLMODEL_URL+id+'/results/'+ img,
    }
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'mlmodel.result',
            'text': message,
        }
     )


def _runModelProcess(dataset, pk=None, ssm=None, number_imgs=None, testrun=True):
    if testrun:
        remote_stdout = io.StringIO()
    else:
        remote_stdout = sys.stdout

    mdir = MLMODEL_DIR + '/' + pk + '/'

    with redirect_stdout(remote_stdout):
        print('Starting Model process')
        if testrun:
            pushToRemoteConsole(pk, remote_stdout)
        data = None
        try:
            if testrun:
                if dataset:
                    ddir = MLMODEL_DIR + '/' + dataset + '/'
                    dataset_mlmodel = MLModel.objects.get(id=dataset)
                    spec = importlib.util.spec_from_file_location("ml_data", ddir + 'ml_data.py')
                    dataprovider = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(dataprovider)
                    data = dataprovider.MLDataset(name=dataset_mlmodel.title, mlmodeldir=ddir)

            mlmodel = MLModel.objects.get(id=pk)
            mltype = mlmodel.type

            spec = importlib.util.spec_from_file_location("ml_code", mdir + 'ml_code.py')
            code = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(code)

            process = code.MLProcessModel(type=mltype, mlmodeldir=mdir, ssm=ssm)
            if testrun:
                pushToRemoteConsole(pk, remote_stdout)

            predictions = []
            performances = []
            images = []
            if data:
                imgs = data.img_generator(int(number_imgs))
            else:
                if testrun:
                    process.inference()
                    pushToRemoteConsole(pk, remote_stdout)
                    return
                else:
                    imgs = [dataset.path]

            for img in imgs:
                print('Processing Image %s' % str(img))
                result = process.inference(img)
                if testrun:
                    pushToRemoteConsole(pk, remote_stdout)
                if result:
                    pred, perf, i2 = result
                    if testrun:
                        pushToRemoteResult(pk, pred, perf, i2)
                    predictions.append(pred)
                    performances.append(perf)
                    if testrun:
                        images.append((i2))
                    else:
                        images.append(MLMODEL_URL+pk+'/results/'+i2)
                    # combine old and new performance data

                    if (perf != None):
                        p = {}
                        print('Type of Performance metrics: %s'%str(type(perf)))
                        if (type(perf)== float32):
                            perf={pred:str(perf)}
                        if ((mlmodel.performance=='{}') | (mlmodel.performance=='[]') | (mlmodel.performance == None)):
                            p = perf
                        else:
                            d1 = json.loads(mlmodel.performance)
                            d2 = perf
                            if (type(d1) == list):
                                if (type(d2) == list):
                                    p = d1 + d2
                                else:
                                    p.append(d2)
                            if (type(d1) == dict):
                                p = {**d1, **d2,**{k: list(flatten([d1[k], d2[k]])) for k in d1.keys() & d2}}


                        mlmodel.performance = json.dumps(p)
                        mlmodel.save()
                else:
                    print('No result')
                if testrun:
                    pushToRemoteConsole(pk, remote_stdout)

        except Exception as e:
            print('-- Exception occured --')
            print(str(e))
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exc(file=remote_stdout)
            print('-----------------------')
            if testrun:
                pushToRemoteConsole(pk, remote_stdout)
            return

    return predictions, performances, images

@shared_task
def runModelProcess(dataset, pk=None, ssm=None, number_imgs=None, testrun=True):
    _runModelProcess(dataset, pk=pk, ssm=ssm, number_imgs=number_imgs, testrun=testrun)

@shared_task
def invokeprocessing(id):
    ssm=SpineSplineModel.objects.get(id=id)
    ssm.status='UPLOADED'
    ssm.save()

    res = chain(cropresize.s(id),categorize_img.s())()

@shared_task
def cropresize(id):
    print('REceived Splineapp id %s'%str(id))
    ssm=SpineSplineModel.objects.get(id=id)
    ssm.status='CROP_LEVEL1'
    ssm.locked=True
    ssm.save()
    # Now do the model processing

    # Evaluate model processing
    performance = 0
    payload = {ssm.status+'_performance':performance, 'id':id}
    return payload

@shared_task
def categorize_img(payload):
    id=payload['id']
    ssm=SpineSplineModel.objects.get(id=id)
    ssm.status='CLASSIFY_LEVEL1'
    ssm.locked=True
    ssm.save()
    # Now do the model processing

    # Evaluate model processing
    performance = 0
    result = {'type':'dummy'}
    payload[ssm.status+'_performance']=performance
    payload[ssm.status+'_result']= result
    ssm.formatted_data=payload
    ssm.locked=False
    ssm.save()
    return payload


@shared_task
def measure_img(id=None):
    ssm=SpineSplineModel.objects.get(id=id)
    ssm.status = 'MEASURE_LEVEL1'
    ssm.locked=True
    ssm.save()
    #Bildvermessung
    try:
        # get the current model for the specified task
        m = MLModel.objects.filter(type=ssm.type, is_active=True).last()
        # run the process
        if m:
            result=_runModelProcess(ssm.resized_img, pk=str(m.id), ssm=ssm.id, number_imgs=1, testrun=False)
            if result:
                predictions, performances, images=result
                payload={}
                payload[ssm.status+'_performance']=performances
                payload[ssm.status+'_result']= predictions
                ssm.modified_img.name=images[0].replace('media/','')  # delete doubled 'media' from URL
                if (ssm.formatted_data):
                    ssm = SpineSplineModel.objects.get(id=id) # reload ssm to avoid race conditions with concurrent Level1/2-Processes
                    ssm.formatted_data = {**ssm.formatted_data,**json.loads(json.dumps(payload))}
                else:
                    ssm.formatted_data=json.loads(json.dumps(payload))   # en & decode to eliminate numpy formatting
            else:
                e='No Model Process result'
                print(e)
                if ssm.errors_dict:
                    ssm.errors_dict = {**ssm.errors_dict, ssm.status + '_errors': str(e)}
                else:
                    ssm.errors_dict = {ssm.status + '_errors': str(e)}

        else:
            e='No Model found for '+ssm.type
            if ssm.errors_dict:
                ssm.errors_dict = {**ssm.errors_dict, ssm.status + '_errors': str(e)}
            else:
                ssm.errors_dict = {ssm.status + '_errors': str(e)}

    except Exception as e:
        print('-- Exception occured --')
        print(str(e))
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exc()
        if ssm.errors_dict:
            ssm.errors_dict={**ssm.errors_dict,ssm.status+'_errors':str(e)}
        else:
            ssm.errors_dict = {ssm.status + '_errors': str(e)}
    print('Formatted Data: %s'%str(ssm.formatted_data))
    print('Mod Image name: %s'%ssm.modified_img.name)
    ssm.locked=False
    ssm.save()

@shared_task
def measure_img_l2(pk,params, analyzer):
    ssm = SpineSplineModel.objects.get(id=pk)
    ssm.status = 'MEASURE_LEVEL2'
    ssm.locked = True
    ssm.save()
    img = Image.open(ssm.resized_img)
    try:
        img_io = io.BytesIO()
        mod_img = None
        result = {}
        if (ssm.type == 'process_upright'):
            mod_img, result = label_upright(img, params['coords'])
            calc = WaistCalculator(waistlines=result['waistline'], targetImg=mod_img, annotate=True)
            calc.getLabeledImage()
            result = calc.result
            mod_img = calc.annotatedImg

        if (ssm.type == 'process_bendforward'):
            mod_img, result = label_bendforward(img, params['coords'])

        if (ssm.type == 'process_xray_cobb'):
            uv = params['vertebrae']['upper']
            lv = params['vertebrae']['lower']
            pts = params['coords']
            manual_cobb = params['manual_cobb']
            mod_img, result = label_xray_spline(img, uv, lv, pts, manual_cobb)

        ssm = SpineSplineModel.objects.get(id=pk) # reload to avoid race conditions
        ssm.formatted_data = {**ssm.formatted_data, ssm.status + '_result': result,
                              ssm.status + '_analyzer': analyzer}

        if mod_img:
            mod_img.save(img_io, format='JPEG')
            modimg_file = InMemoryUploadedFile(img_io, None, 'labeled.jpg', 'image/jpeg',
                                               img_io.getbuffer().nbytes,
                                               None)
            ssm.man_labeled_img.save('labeled.jpg', modimg_file)

    except Exception as e:
        print('-- Exception occured --')
        print(str(e))
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exc()
        if ssm.errors_dict:
            ssm.errors_dict = {**ssm.errors_dict, ssm.status + '_errors': str(e)}
        else:
            ssm.errors_dict = {ssm.status + '_errors': str(e)}

    ssm.locked = False
    ssm.save()
