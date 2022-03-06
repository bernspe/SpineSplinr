# Create your views here.
# import the logging library
import json
import logging
# Get an instance of a logger
import os
import sys
import traceback
from statistics import mean

import gviz_api
import pandas as pd
import numpy as np

from django.db.models import Q
from rest_framework.permissions import IsAuthenticated, AllowAny

from SpineSplinr.celery import app
from SpineSplinr.settings import MLWORKFLOW, MLMODEL_IMG_SIZE, BASE_DIR

from users.models import User
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework.decorators import action
from rest_framework.response import Response

logger = logging.getLogger(__name__)

from rest_framework import permissions, status
from rest_framework import viewsets


from splineapp.models import SpineSplineModel, SpineSplineCollection, SpineSplineDiagnosis
from splineapp.serializers import SpineSplineSerializer, SpineSplineCollectionSerializer

from guardian.shortcuts import get_objects_for_user, remove_perm
from django.core.files.uploadedfile import InMemoryUploadedFile

from PIL import Image
from io import BytesIO

def flip_horizontal(im): return im.transpose(Image.FLIP_LEFT_RIGHT)
def flip_vertical(im): return im.transpose(Image.FLIP_TOP_BOTTOM)
def rotate_180(im): return im.transpose(Image.ROTATE_180)
def rotate_90(im): return im.transpose(Image.ROTATE_90)
def rotate_270(im): return im.transpose(Image.ROTATE_270)
def transpose(im): return rotate_90(flip_horizontal(im))
def transverse(im): return rotate_90(flip_vertical(im))
orientation_funcs = [None,
                 lambda x: x,
                 flip_horizontal,
                 rotate_180,
                 flip_vertical,
                 transpose,
                 rotate_270,
                 transverse,
                 rotate_90
                ]
def apply_orientation(im):
    """
    Extract the oritentation EXIF tag from the image, which should be a PIL Image instance,
    and if there is an orientation tag that would rotate the image, apply that rotation to
    the Image instance given to do an in-place rotation.

    :param Image im: Image instance to inspect
    :return: A possibly transposed image instance
    """

    try:
        kOrientationEXIFTag = 0x0112
        if hasattr(im, '_getexif'): # only present in JPEGs
            e = im._getexif()       # returns None if no EXIF data
            if e is not None:
                #log.info('EXIF data found: %r', e)
                orientation = e[kOrientationEXIFTag]
                f = orientation_funcs[orientation]
                return f(im)
    except:
        # We'd be here with an invalid orientation value or some random error?
        pass # log.exception("Error applying EXIF Orientation tag")
    return im

def _get_ssm_schemas():
    fn = os.path.join(BASE_DIR, 'splineapp', 'ssm_schemas.json')
    f = open(fn)
    d = json.load(f)
    return d




class SpineSplineViewSet(viewsets.ModelViewSet):
    """
    create: The SpineSpline Endpoint is an abstract class to receive Image (jpeg) input from the user and to return measured Data.\n
    This Model needs Title and Img specified in order to return measurement data. The default image type of the abstract calss is xray.\n
    Data will be deleted after 1 day.

    parameter: Entry Title and Image

    retrieve: The SpineSpline Endpoint is an abstract class to receive Image (jpeg) input from the user and to return measured Data.\n
    This endpoint returns a complete dataset.\n
    Data will contain the URL of a pkl-File, which can be unpacked and computed further, whereas formatted Data will come as json-string.\n
    Modified image field will contain a URL of the original image with overlayed model-generated measurements.\n
    Errors will be reported in string format

    list: The SpineSpline Endpoint is an abstract class to receive Image (jpeg) input from the user and to return measured Data.\n
    This endpoint returns a list of all entries.
    """

    serializer_class = SpineSplineSerializer
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]
    #parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return SpineSplineModel.objects.all()
        else:
            ssm_list = SpineSplineModel.objects.none()
            roles = [r.isMed() | r.isCaregiver() for r in user.roles.all()]
            if any(roles):
                crs = (user.caserooms.all() | user.caseroom.all()).distinct()  # caserooms owned by the user
                for c in crs:
                    ms = c.members.all()
                    for m in ms:  # get the ssm objects of each member
                        sa = m.splineapp.all()  # get possible ssms of the cr member
                        if len(sa)>0:
                            ssm_list = sa | ssm_list  # concatenate querysets
                ssm_list |= get_objects_for_user(user, 'splineapp.view_spinesplinemodel', accept_global_perms=False)

            roles=[r.isChild() | r.isAdult() | r.isPatient() for r in user.roles.all()]
            if any(roles):
                pat_list=SpineSplineModel.objects.filter(owner=user)
                ssm_list |= pat_list

            return ssm_list

    def list(self, request):
        queryset = self.get_queryset().filter(collection__isnull=True) # , but exclude the ones already in collections
        serializer = SpineSplineSerializer(queryset, context={'request': request}, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        logging.debug('Starting post serializer for user %s'%str(self.request.user))
        owner= self.request.POST.get('owner')
        if owner:
            u_owner=User.objects.get(username=owner)
            serializer.save(owner=u_owner, status='pending')
        else:
            serializer.save(owner=self.request.user, status='pending')

    @action(detail=False)
    def get_ssm_schemas(self,request):
        try:
            d=_get_ssm_schemas()
            return Response(data=d,status=status.HTTP_200_OK)
        except Exception as e:
            return Response(data={'error':str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False)
    def get_ssm_jsondata(self,request):
        VERTEBRAE = ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8', 'T9', 'T10', 'T11', 'T12', 'L1', 'L2', 'L3', 'L4',
                      'L5', 'S1']
        try:
            d=_get_ssm_schemas()
            ssm_types=d.keys()
            queryset=self.get_queryset()
            user= request.GET.get('username')
            if user:
                involved_owners=[User.objects.get(username=user)]
            else:
                involved_owners = set([el.owner for el in queryset])
            dataset=[]
            for owner in involved_owners:
                type_dependend_data = []
                for t in ssm_types:
                    t_mod=t.split('-')[0]
                    q = queryset.filter(type=t_mod, owner=owner)
                    fields = list(set([i[0].split('_')[0] for i in d[t]['fields'] if i[0]!='created']))
                    data=[]
                    for ssmitem in q:
                        fd=ssmitem.formatted_data
                        if ((fd!= None) & (fd != {})):
                            for param in ['MEASURE_LEVEL1_result', 'MEASURE_LEVEL2_result']:
                                if param in fd.keys():
                                    di = {}
                                    valuedict=fd[param]
                                    if ((valuedict != None) & (valuedict != {}) & (type(valuedict)==dict)):
                                        ks=valuedict.keys()
                                        di['created'] = ssmitem.created
                                        di['MEASURE_LEVEL'] = param
                                        for f in fields:
                                            if f in ks:
                                                di[f]=valuedict[f]
                                        if t_mod=='process_xray_cobb':
                                            for s in ['SPLINE','COBB']:
                                                di[s + 'AngleTh'] = np.nan
                                                di[s + 'AngleLu'] = np.nan
                                                if s+'_angles' in ks:
                                                    di[s + 'AngleTh'] = []
                                                    di[s + 'AngleLu'] = []
                                                    ca=valuedict[s+'_angles']
                                                    cv=valuedict[s+'_vertebrae']
                                                    cv=[max([VERTEBRAE.index(el[0]),VERTEBRAE.index(el[1])]) for el in cv] # get the lowest vertebrae
                                                    for a,v in zip(ca,cv):
                                                        if v<14: # for all lowest vertebrae above L3
                                                            di[s+'AngleTh'].append(a)
                                                        else:
                                                            di[s+'AngleLu'].append(a)
                                                    for s2 in [s+'AngleTh',s+'AngleLu']:
                                                        if len(di[s2])==0:
                                                            di.pop(s2)
                                                        else:
                                                            di[s2]=max(di[s2])
                                    data.append(di)

                    if len(data)>0:
                        df=pd.DataFrame(data)
                        wanted_cols = [x for x in df.columns if x in fields]
                        df.dropna(how='all',subset=wanted_cols,inplace=True)
                    else:
                        continue
                    if len(df)>0:
                        df['created']=df['created'].dt.date
                        df=df.applymap(lambda x: mean(x) if type(x)==list else x)
                        # get the mean and max
                        cols=df.drop(columns=['created', 'MEASURE_LEVEL']).columns
                        grouped = df.groupby(['created'])
                        df_a=[]
                        for c in cols:
                            df2=grouped.agg({c:['mean','min','max']})
                            df2.columns=[c+'_mean',c+'_min',c+'_max']
                            df_a.append(df2)
                        field_order = [i[0] for i in d[t]['fields']]
                        df=pd.concat(df_a, axis=1).reset_index()
                        df=df.reindex(columns=field_order)
                        #df=df.fillna(value=0)
                        df = df.replace({np.nan: None})
                        data_prepared = df.values.tolist()
                        #now reformat it to gviz datatable format
                        data_table = gviz_api.DataTable([tuple(el) for el in d[t]['fields']])
                        data_table.LoadData(data_prepared)
                        type_dependend_data.append(
                            {'type': t, 'data': json.loads(data_table.ToJSon()), 'chartoptions': d[t]['chartoptions']})

                        #response as an array matrix which will be processed inside Vue GChart
                        #type_dependend_data.append({'type': t, 'data':[field_order]+data_prepared, 'chartoptions': d[t]['chartoptions']})
                if len(type_dependend_data)>0:
                    dataset.append({'owner':owner.username, 'data':type_dependend_data})
            return Response(data=dataset, status=status.HTTP_200_OK)
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            sexc=traceback.format_exc()
            return Response(data={'error': str(e), 'traceback':sexc}, status=status.HTTP_400_BAD_REQUEST)



    @action(detail=True)
    def startml(self, request, pk=None):
        df=MLWORKFLOW
        t='upright'
        step='init'
        flowing=True
        a=[]
        while flowing:
            nxt=eval(df.loc[step,'on_success'])
            stat=df.loc[step,'status']
            if type(nxt)==str:
                step=nxt.rsplit('.')[-1]
            elif type(nxt)==dict:
                step=nxt[t].rsplit('.')[-1]
            a.append(step)
            if stat=='MEASURE_LEVEL2':
                flowing=False
        return Response(data=a, status=status.HTTP_200_OK)

    @action(detail=True, permission_classes=[AllowAny])
    def startml2(self, request, pk=None):
        app.send_task('MLModelManager.tasks.invokeprocessing', args=[pk])
        return Response(data={'started':'ok'}, status=status.HTTP_200_OK)


    @action(methods=['post'],detail=False, permission_classes=[IsAuthenticated])
    def get_ssm_by_status(self,request):
        """
        possible requests
        status = CLASSIFY_LEVEL1, MEASURE_LEVEL1, MEASURE_LEVEL2
        :param request:
        :return:
        """
        data = request.data
        queryset=SpineSplineModel.objects.filter(status=data['status'])
        serializer=SpineSplineSerializer(queryset,context={'request': request},many=True)
        return Response(serializer.data)

    @action(methods=['post'],detail=False, permission_classes=[IsAuthenticated])
    def get_ssm_by_idlist(self,request):
        """
        returns a list of ssm through a list request of ssm ids
        :param request:
        :return:
        """
        data = request.data
        queryset=SpineSplineModel.objects.filter(id__in=data)
        serializer=SpineSplineSerializer(queryset,context={'request': request},many=True)
        return Response(serializer.data)

    @action(methods=['post'],detail=True,permission_classes=[IsAuthenticated])
    def classify_level2(self,request,pk=None):
        """
        expects type = dummy, process_xray_cobb, process_upright, process_bendforward
        :param request:
        :param pk:
        :return:
        """
        ssm = SpineSplineModel.objects.get(id=pk)
        ssm.type=request.data['type']
        ssm.status = 'CLASSIFY_LEVEL2'

        try:
            if 'params' in request.data.keys():
                params = request.data['params']
                if (ssm.formatted_data):
                    ssm.formatted_data = {**ssm.formatted_data, ssm.status + '_result': params}
                else:
                    ssm.formatted_data = {ssm.status + '_result': params}

                if (params['target_width'] != params['target_height']):
                    return Response(data={'error': 'target image is not square'}, status=status.HTTP_400_BAD_REQUEST)

                img_io = BytesIO()
                img = Image.open(ssm.img)

                img=apply_orientation(img)
                rot_img = img.rotate(params.get('target_rotation',0))
                cropped_img = rot_img.crop(
                    (params['target_x'], params['target_y'], params['target_x'] + params['target_width'],
                     params['target_y'] + params['target_height'])).resize((MLMODEL_IMG_SIZE,MLMODEL_IMG_SIZE), Image.ANTIALIAS)
                if ((img.mode=='RGBA') | (img.format=='PNG')):
                    cropped_img=cropped_img.convert('RGB')
                cropped_img.save(img_io, format='JPEG')
                cropped_file = InMemoryUploadedFile(img_io, None, 'resized.jpg', 'image/jpeg', img_io.getbuffer().nbytes,
                                                    None)
                ssm.resized_img.save('resized.jpg', cropped_file)
                thumb_img = cropped_img.resize((15,150), Image.ANTIALIAS)
                thumb_img.save(img_io, format='JPEG')
                thumb_file = InMemoryUploadedFile(img_io, None, 'thumb.jpg', 'image/jpeg', img_io.getbuffer().nbytes,
                                                    None)
                ssm.thumb_img.save('thumb.jpg', thumb_file)
                ssm.locked = False

        except Exception as e:
            return Response(data={'error':str(e)}, status=status.HTTP_400_BAD_REQUEST)
        ssm.save()
        app.send_task('MLModelManager.tasks.measure_img', args=[pk])
        serializer = SpineSplineSerializer(ssm, context={'request': request})
        return Response(data=serializer.data, status=status.HTTP_200_OK)


    @action(methods=['post'],detail=True,permission_classes=[IsAuthenticated])
    def measure_level2(self,request,pk=None):
        if 'params' in request.data.keys():
            params = request.data['params']
            analyzer = str(request.user.username)
            app.send_task('MLModelManager.tasks.measure_img_l2', args=[pk,params,analyzer])
            return Response(data={'started': 'ok'}, status=status.HTTP_200_OK)
        return Response(data={'error':'Missing parameters'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True,permission_classes=[IsAuthenticated])
    def measure_level3(self,request,pk=None):
        ssm = SpineSplineModel.objects.get(id=pk)
        ssm.status = 'MEASURE_LEVEL3'
        ssm.save()
        return Response(data={'started': 'ok'}, status=status.HTTP_200_OK)

    @action(detail=True,permission_classes=[IsAuthenticated])
    def add_to_collection(self,request,pk=None):
        ssm = SpineSplineModel.objects.get(id=pk)
        collection=ssm.add_to_collection()
        collection.save()
        return Response(data={'collection': collection.id}, status=status.HTTP_200_OK)

    @action(detail=True, permission_classes=[IsAuthenticated])
    def protect(self, request, pk=None):
        ssm = SpineSplineModel.objects.get(id=pk)
        # move images to protected area
        ssm.protect_imgs()
        ssm.save()
        return Response(data={'started': 'ok'}, status=status.HTTP_200_OK)

    @action(detail=True, name='Approve SSM')
    def approve(self, request, *args, **kwargs):
        """
        This endpoint approves the model-generated data. It can only be fulfilled by the SSM-Supervisor
        """
        return self.change_approval(request)

    @action(detail=True, name='Reject SSM')
    def reject(self, request, *args, **kwargs):
        """
        This endpoint rejects the model-generated data. It can only be fulfilled by the SSM-Supervisor
        """
        return self.change_approval(request,approval='rejected')

    @action(detail=False,permission_classes=[AllowAny])
    def getsampletimeline(self,request):
        if request.GET.get('freq')=='M':
            with open('samples/timeseries_monthly.json') as json_file:
                data = json.load(json_file)
                return Response(data=data, status=status.HTTP_200_OK)
        if request.GET.get('freq')=='Y':
            with open('samples/timeseries_yearly.json') as json_file:
                data = json.load(json_file)
                return Response(data=data, status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class SpineSplineCollectionViewSet(viewsets.ModelViewSet):
    serializer_class = SpineSplineCollectionSerializer
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return SpineSplineCollection.objects.all()
        else:
            scol_list=SpineSplineCollection.objects.none()
            crs = user.caserooms.all()  # caserooms owned by the user
            for c in crs:
                ms = c.members.all()
                for m in ms:  # get the collection objects of each member
                    sa=m.spinesplinecollection.all() #get possible collection of the cr member
                    scol_list=sa | scol_list #concatenate querysets
            return scol_list | get_objects_for_user(user,'splineapp.view_spinesplinecollection',accept_global_perms=False)

    @action(methods=['get'],detail=True, name='Add Diagnosis')
    def adddiagnosis(self, request, pk=None):
        d=request.GET.get('diagnosis')
        if d:
            c=SpineSplineCollection.objects.get(pk=pk)
            u=request.user
            col_diag=SpineSplineDiagnosis.objects.filter(Q(responsible_physician=u) & Q(collection=c))
            if len(col_diag)==0:
                col_diag=SpineSplineDiagnosis.objects.create(responsible_physician=u, diagnosis=d)
                c.diagnoses.add(col_diag)
                c.save()
            else:
                col_diag=col_diag[0]
                col_diag.diagnosis=d
                col_diag.save()
            serializer = SpineSplineCollectionSerializer(c)
            return Response(data=serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)
