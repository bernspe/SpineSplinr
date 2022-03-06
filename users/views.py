import re
import uuid
from datetime import datetime, timezone, date, timedelta
from distutils.util import strtobool
from random import randint
import io

import requests
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files import File
from django.core.files.base import ContentFile
from django.http import HttpResponse, FileResponse
from oauth2_provider.oauth2_validators import Application
from oauthlib import common

from django.db.models import Q
from django.template.loader import get_template
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from oauth2_provider.models import AccessToken, RefreshToken
from oauth2_provider.views import TokenView as TV
from rest_framework import viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from unidecode import unidecode

from SpineSplinr import settings
from SpineSplinr.settings import DEFAULT_USER_PASSWORD, VERSION, BUILD_DATE, GEN_STAFF_USER, INVITED_USER_URL, \
    AUTH0_DOMAIN
from auth0authorization.utils import get_token_auth_header
from caserooms.models import CaseRoom
from users.models import User, get_specific_role_group, CONSENTTYPES, ConsentContent, consent, Userrole, UserProof, \
    Device, get_default_expiry

# Create your views here.
# Create the API views
from users.pdf_utils import PdfFile
from users.permissions import IsOwner, IsStaff, IsMed
from users.serializers import UserSerializer, RegisterSerializer, ForgotPasswordSerializer, UserNameEmailSerializer, \
    ConsentContentSerializer, MedicalStaffSerializer, ConsentSerializer, ConsentWithContentSerializer, \
    UserroleSerializer, ProofSerializer, StaffUserSerializer, DeviceSerializer
from rest_framework import status, permissions
from oauth2_provider.settings import oauth2_settings
#from braces.views import CsrfExemptMixin
from oauth2_provider.views.mixins import OAuthLibMixin
from django.db import transaction
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from rest_framework.decorators import api_view, action, permission_classes, authentication_classes
from django.contrib.auth import get_user_model
#import rest_framework_social_oauth2.views

import json

def hasExpired(expiry):
    present = datetime.now().replace(tzinfo=timezone.utc)
    return present > expiry

def calculate_age(born):
    today = date.today()
    if born:
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    else:
        return 400

@api_view(['GET'])
@permission_classes([AllowAny])
def get_version(request):
    return Response(data={'version':VERSION,'date':BUILD_DATE})

class UserroleViewSet(viewsets.ModelViewSet):
    """
    Retrieves the possible userroles
    """
    queryset = Userrole.objects.all()
    serializer_class = UserroleSerializer
    permission_classes = [IsAuthenticated]

    @action(methods=['post'], detail=False)
    def list2(self, request):
        """
        Returns a specifically formatted list
        if data in the body provides
        language = de or en
        format = list
        otherwise, dict is returned
        :return:
        """
        ignore_age=request.data.get('ignoreage')
        if ignore_age:
            if type(ignore_age)==bool:
                pass
            else:
                ignore_age=bool(strtobool(ignore_age))
        if ignore_age:
            queryset = Userrole.objects.all()
        else:
            userage=calculate_age(request.user.date_of_birth)
            if userage<16:
                queryset=Userrole.objects.filter(Q(role='Child')|Q(role='Patient')|Q(role='Volunteer'))
            elif ((userage>15) & (userage<18)):
                queryset = Userrole.objects.filter(Q(role='Child16') | Q(role='Patient') | Q(role='Volunteer'))
            else:
                queryset =Userrole.objects.exclude(category='Child')
        serializer = self.get_serializer(queryset, many=True)
        lang=request.data.get('language')
        if not (lang):
            lang='en'
        form=request.data.get('format')
        if not form:
            u=request.user
            if u.is_staff:
                form='list-all'
            else:
                form='list-users'
        l_role=[]
        l_trans=[]
        l_cat=[]
        l_combined=[]
        for item in serializer.data:
            appender=False
            r=item['role']
            t=item['translations'][lang]
            if ((len(r)>0) & (len(t)>0)):
                cat=item['category']
                if (form=='list-all'):
                    appender=True
                elif ((form=='list-users') & (cat!='Staff')):
                    appender=True
                elif ((form=='list-staff') & (cat=='Staff')):
                    appender=True
                if appender:
                    l_role.append(r)
                    l_trans.append(t)
                    l_cat.append(cat)
                    if type(item['proof'])==list:
                        p=item['proof']
                    else:
                        p=[item['proof']]
                    l_combined.append({'key':r,'text':t,'category':cat, 'proof': p})
        return Response(data=l_combined,status=status.HTTP_200_OK)
        #return Response(serializer.data)

class ConsentTypesList(APIView):
    """
    Gets a list of the currently available consent types.
    """
    permission_classes = [AllowAny]
    def get(self,request):
        d=[{'value':r[0], 'text': r[0]+': '+r[1]} for r in CONSENTTYPES]
        return Response(data=d)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_medical_users(request):
    """
    This endpoint lists possible CaseRoom members from the medical faculty
    """
    lang=request.GET.get('language')
    if lang:
        pass
    else:
        lang='en'
    a=[]
    i=0
    meduser = Userrole.objects.filter(Q(category='Med'))
    for u in meduser:
        i+=1
        ca=[{'username': p.username, 'name':p.get_full_name(), 'email':p.email} for p in u.userrole.all()]
        if len(ca)>0:
            a.append({'username': u.role ,'name': u.translations[lang],'children': ca})
    return Response(a)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_dependent_children(request):
    """
    This endpoint lists dependent children of the authenticated user
    """
    User = request.user
    queryset = User.dependent_children.all()
    serializer = UserNameEmailSerializer(queryset, many = True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_caregiver(request):
    """
    This endpoint lists the caregivers of the authenticated user
    """
    User = request.user
    queryset = User.caregiver.all()
    serializer = UserNameEmailSerializer(queryset, many = True)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([AllowAny])
def get_minprofile_from_currently_invited_user(request):
    """
    This endpoint allows for the check of Usernames of a recently (1 day) added user
    this is useful for QR Code login
    """
    username = request.data.get('username')
    try:
        yesterday=datetime.now().replace(tzinfo=timezone.utc)-timedelta(days=1)
        user = get_user_model().objects.filter(Q(username=username) & Q(date_joined__gte=yesterday)).first()
        serializer = UserNameEmailSerializer(user)
        return Response(serializer.data)
    except Exception as e:
        return Response(data={"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def deny_qrcode_login(request):
    try:
        username=request.data.get('username')
        notify=request.data.get('notify')
        inviting_user=User.objects.get(username=notify)
        invited_user=User.objects.get(username=username)
        inviting_user.msg_when_invited_user_denied_login(invited_user=invited_user)
        invited_user.delete()
        return Response(data={"info":"User denied access"}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(data={"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_minprofile_from_users(request):
    """
    This endpoint lists minimal profiles from requested usernames
    :param request: usernames: ['Username1','Username2',...]
    :return: Minimal profile containing First and Last Name, email and role
    """
    usernames = request.data.get('usernames')
    try:
        queryset = get_user_model().objects.filter(pk__in=usernames)
        #get the caregivers
        #for u in queryset.all():
            #roles = [r.isChild() for r in u.roles.all()]
            #if any(roles):
            #    queryset |= u.caregiver.all()
        #queryset=queryset.all().distinct()
        serializer = UserNameEmailSerializer(queryset, many = True)
        return Response(serializer.data)
    except Exception as e:
        return Response(data={"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_names(request):
    """
    This endpoint validates full names and returns usernames
    """
    User = get_user_model()
    names = request.data.get('names')
    result={'matched':[], 'ambiguous':[], 'unknown':[]}
    if names:
        for name in names:
            ns=name.split(' ')
            ln=ns[-1] # = last name
            ns.remove(ln) # = the remainders will be the first name
            fn=''.join(ns) # convert from list to string
            queryset = User.objects.filter(Q(first_name=fn) & Q(last_name=ln))
            res=queryset.all()
            serializer = MedicalStaffSerializer(res, many=True)
            if len(res)==1:
                result['matched'].append(serializer.data)
            if len(res)>1:
                result['ambiguous'].append(serializer.data)
            if len(res)==0:
                result['unknown'].append({'name':name})
    return Response(result)



class UserViewSet(viewsets.ModelViewSet):
    """
    A viewset for viewing and editing user instances.
    """
    queryset = User.objects.all()
    authentication_classes = [OAuth2Authentication]

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action == 'list':
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [IsAuthenticated, IsOwner | IsStaff]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if (self.request.user.is_staff | self.request.user.is_admin):
            return StaffUserSerializer
        return UserSerializer

    def partial_update(self, request, pk=None):
        user=User.objects.get(username=pk)
        serializer = self.get_serializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    ps=request.data.get('proofstatus')
                    if (ps=='VALIDATED'):
                        children=user.dependent_children.all()
                        for child in children:
                            child_object=User.objects.get(username=child)
                            child_object.proofstatus='VALIDATED'
                            child_object.save()
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_200_OK)
            except Exception as e:
                return Response(data={"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, pk=None):
        queryset = User.objects.all()
        user = get_object_or_404(queryset, pk=pk)
        if (request.user == user):
            serializer = UserSerializer(user)
        elif (request.user.is_staff | request.user.is_admin):
            serializer = StaffUserSerializer(user)
        else:
            serializer = UserNameEmailSerializer(user)
        return Response(serializer.data)

    @action(methods=['post'], detail=True)
    def toggleUserActivation(self, request, pk=None):
        try:
            user=User.objects.get(username=pk)
            user.toggleActivation()
        except Exception as e:
            return Response(data={"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data={"user-activation":str(user.is_active)}, status=status.HTTP_200_OK)

    @action(methods=['post'], detail=True)
    def updateAvatar(self, request, pk=None):
        try:
            user=User.objects.get(username=pk)
            avatarFile = request.FILES.get('avatar')
            im = Image.open(avatarFile)  # Catch original
            source_image = im.convert('RGB')
            source_image.thumbnail((250, 250), Image.ANTIALIAS)  # Resize to size
            output = io.BytesIO()
            source_image.save(output, format='JPEG')  # Save resize image to bytes
            output.seek(0)
            content_file = ContentFile(output.read())  # Read output and create ContentFile in memory
            file = File(content_file)
            random_name = pk+'_avatar.jpeg'
            user.avatar.save(random_name, file, save=True)
        except Exception as e:
            return Response(data={"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data={"avatar":str(user.avatar)}, status=status.HTTP_200_OK)

    @action(methods=['post'],detail=True)
    def addchild(self,request,pk=None):
        user = request.user
        data=request.data
        if len(data['email'])>0:
            child=User.objects.filter(email=data['email']).first()
        else:
            child=User.objects.filter(first_name=data['first_name'],last_name=data['last_name'], date_of_birth=data['date_of_birth']).first()
            data['email'] = data['first_name'].lower() + str(randint(10, 90)) + '@skoliosekinder.de'
        data['password']=DEFAULT_USER_PASSWORD
        if child:
            if child in user.dependent_children.all():
                return Response(data={"exists": "User "+str(child.username)+" is already dep. child of "+str(user.username)}, status=status.HTTP_400_BAD_REQUEST)
            else:
                user.dependent_children.add(child)
                user.save()
            serializer = UserSerializer(child)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            serializer = RegisterSerializer(data=data)
            if serializer.is_valid():
                try:
                    with transaction.atomic():
                        child = serializer.save(proofstatus='INVITED')
                        if child.isTeenagerFromAge():
                            childrole = 'Child16'
                        else:
                            childrole='Child'
                        child.roles.add(childrole)
                        child.save()
                        user.dependent_children.add(child)
                        user.save()
                    return Response(serializer.data, status=status.HTTP_200_OK)
                except Exception as e:
                    return Response(data={"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['post'],detail=True)
    def deletechild(self,request, pk=None):
        try:
            user=request.user
            data = request.data
            childusername = data['username']
            childuser=User.objects.get(username=childusername)
            if childuser in user.dependent_children.all():
                childuser.toggleActivation()
                return Response(data={'delete': childusername}, status=status.HTTP_200_OK)
            else:
                return Response(data={"error": "child does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(data={"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['post'],detail=False, permission_classes = [IsMed, IsStaff])
    def add_caregivers_to_specific_child(self,request):
        """
        Adds caregivers to a specified child user
        :param request:
        :return: the newly added caregiver of the child and the child
        """

        try:
            data = request.data
            childusername = data['child_username']
            childuser = User.objects.get(username=childusername)
            roles = [r.isChild() for r in childuser.roles.all()]
            if any(roles):
                users=[childuser]
                caregiverusernames = data['caregiver_usernames']
                for c in caregiverusernames:
                    if c:
                        caregiveruser=User.objects.get(username=c)
                        croles=[r.isCaregiver() for r in caregiveruser.roles.all()]
                        if any(croles):
                            pass
                        else:
                            r=Userrole.objects.get(role='Caregiver')
                            caregiveruser.roles.add(r)
                        childuser.caregiver.add(caregiveruser)
                        users.append(caregiveruser)
                serializer = UserNameEmailSerializer(users, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(data={"error": childusername+" has no child role"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(data={"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['post'],detail=True, permission_classes = [IsAuthenticated, IsStaff])
    def email(self,request,pk=None):
        """
        Sends email from System to pk-specified User
        """
        try:
            user=User.objects.get(username=pk)
            subject=request.data.get('subject')
            message=request.data.get('message')
            user.email_user(subject,message)
            return Response(data={'email':'sent'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(data={"email error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['post'],detail=True, permission_classes = [IsAuthenticated, IsStaff])
    def msg_to_user(self,request,pk=None):
        """
        Sends msg via Helpdesk caseroom from staff user to pk-specified User
        """
        try:
            user=User.objects.get(username=pk)
            message=request.data.get('message')
            user.msg_user(message=message, from_user=request.user)
            return Response(data={'msg':'sent'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(data={"msg error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['get'], detail=True, permission_classes=[IsAuthenticated, IsStaff | IsOwner])
    def getmissingconsents(self, request, pk=None):
        """
        Gets the missing consents for the user with specific role
        :param request:
        :param pk:
        :return: a list with missing consent types
        """
        try:
            user=User.objects.get(username=pk)
            mc=user.needs_role_specific_consents()[0]
            return Response(data=mc, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(data={"consent request error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['get'], detail=True, permission_classes=[IsAuthenticated, IsStaff | IsOwner])
    def getmissingproofs(self, request, pk=None):
        """
        Gets the missing proofs for the user with specific role
        :param request:
        :param pk:
        :return: a list with missing proof types
        """
        try:
            user=User.objects.get(username=pk)
            mc=user.needs_role_specific_proofs()
            return Response(data=mc, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(data={"proof request error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['get'], detail=False)
    def getmypatients(self, request):
        """
        Gets a list of the user's patients, registered in caserooms who have SSMs
        :param request:
        :return:
        """
        try:
            request_user_crs=request.user.caserooms.all()
            patienttype=['Child','Child16','Adult','Patient']
            users=User.objects.filter(Q(splineapp__isnull=False) & (Q(caserooms__in=request_user_crs)|Q(caseroom__in=request_user_crs)) & (Q(roles__role__in=patienttype))).distinct()
            serializer=UserNameEmailSerializer(users,many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(data={"getmypatients request error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['get'], detail=False)
    def getmedusers(self, request):
        """
        Gets a list of currently registered users of the category MED
        :param request:
        :return:
        """
        try:
            r = Userrole.objects.filter(category='Med')
            users=User.objects.filter(roles__in=r.all()).distinct()
            serializer=UserNameEmailSerializer(users,many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(data={"getmedusers request error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['post'], detail=False)
    def searchuser(self,request):
        """
        Searches a user with Name+Birthday or email
        :param request:
        :return:
        """
        data = request.data
        try:
            if 'email' in data.keys():
                user=User.objects.get(email=data['email'])
                serializer = UserNameEmailSerializer(user)
                return Response(serializer.data, status=status.HTTP_200_OK)
            if (('first_name' in data.keys()) & ('last_name' in data.keys()) & ('birthday_date' in data.keys())):
                fname=data['first_name'].rstrip()
                lname=data['last_name'].rstrip()
                users = User.objects.filter(first_name=fname,last_name=lname,date_of_birth=data['birthday_date'])
                serializer = UserNameEmailSerializer(users, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
        except:
            return Response(data=[], status=status.HTTP_200_OK)
        return Response(data=[], status=status.HTTP_200_OK)

class UserRegister(OAuthLibMixin, APIView): ##CsrfExemptMixin,
    """
    Registering Users at OAuth Server
    """
    permission_classes = (permissions.AllowAny,)
    server_class = oauth2_settings.OAUTH2_SERVER_CLASS
    validator_class = oauth2_settings.OAUTH2_VALIDATOR_CLASS
    oauthlib_backend_class = oauth2_settings.OAUTH2_BACKEND_CLASS

    def post(self, request):
      #  if request.auth is None:
        data = request.data
        data = data.dict()
        serializer = RegisterSerializer(data=data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    user = serializer.save(proofstatus ='NONPROVEN')
                    url, headers, body, token_status = self.create_token_response(request)
                    jbody=json.loads(body)
                    if token_status != 200:
                       raise Exception(jbody.get("error_description", ""))
                  #  t = get_template('user/email-confirm.html')
                  #  user.email_user('Registration',t.render(context={
                  #      'Firstname':user.first_name,
                  #      'Link': settings.FRONT_END_URL+'activate/'+user.username+'/?token='+str(jbody['access_token'])}))
                    return Response(jbody, status=token_status)
            except Exception as e:
                return Response(data={"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)
   #     return Response(status=status.HTTP_403_FORBIDDEN)



@csrf_exempt
@api_view(['GET'])
def check_token(request, format=None):
    """
    Retrieves User Profile from registered token
    :param Bearer token in Header is sufficient
    :param format:
    :return: User object
    """
    app_tk = request.META["HTTP_AUTHORIZATION"]
    m = re.search('(Bearer)(\s)(.*)', app_tk)

    app_tk = m.group(3)
    try:
        # search oauth2 token db to find user
        acc_tk = AccessToken.objects.get(token=app_tk)
        if hasExpired(acc_tk.expires):
            return Response({'error': 'Token has expired. Please log in again.'}, status=status.HTTP_400_BAD_REQUEST)
    except:
        return Response({'error': 'User not found.'}, status=status.HTTP_400_BAD_REQUEST)
    user = acc_tk.user
    user.last_login=datetime.now(timezone.utc)
    user.save()
    serializer = UserSerializer(user)
    # check if service helpdesk caseroom existx, if not, create it
    try:
        cr,created=CaseRoom.objects.get_or_create(owner=user,title=settings.HELPDESK_NAME+': '+user.get_full_name())
        su = User.objects.get(username=GEN_STAFF_USER['username'])
        if created:
            su=User.objects.get(username=GEN_STAFF_USER['username'])
            cr.members.add(su)
            cr.save()
        else:
            if su in cr.members.all():
                pass
            else:
                cr.members.add(su)
                cr.save()
    except Exception as e:
        print('Helpdesk Caseroom Creation failed. Exception: %s'%str(e))
    return Response(serializer.data, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['GET'])
def check_emailexists(request, pk=None):
    try:
        email=request.GET.get('email')
        user = get_user_model().objects.get(email=email)
    except:
        return Response(data={'email': 'not found'}, status=status.HTTP_200_OK)
    return Response(data={'email':'OK'}, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_defaultpassword(request, pk=None):
    """
    Checks if a user has still the default password set
    :return: True if default
    """
    user = request.user
    return Response(data={'defaultpassword':user.check_password(DEFAULT_USER_PASSWORD), 'expired':hasExpired(user.expires)}, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['GET'])
def confirm_email(request, pk=None):
    """
    Receives register/activate/<username>/ request and sets the isEmailactivated flag to true
    :param
    :param pk: = username
    :return:
    """
    try:
        user = get_user_model().objects.get(pk=pk)
        if not (user.is_active):
            user.toggleActivation()
            t2 = get_template('user/email-user-undo-deactivation.html')
            user.email_user('Account ist reaktiviert', t2.render(context={'user': user}))
        serializer = UserSerializer(user, data=request.data, partial=True)  # set partial=True to update a data partially
        if serializer.is_valid():
            serializer.save(is_emailvalidated=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
    except:
        return Response({'error':'Error during Email Confirmation'},status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invite_new_user_via_email(request, pk=None):
    """
    Invite a new user via email
    """
    data = request.data
    data['password'] = DEFAULT_USER_PASSWORD
    user=None
    try:
        user = get_user_model().objects.get(email=data['email'])
        serializer = UserSerializer(user,data={'proofstatus':'INVITED'},partial=True)
    except:
        serializer = RegisterSerializer(data={**data,'proofstatus':'INVITED'})
    if serializer.is_valid():
        try:
            with transaction.atomic():
                if not user:
                    user = serializer.save()
                serializer.save()
                t = get_template('user/email-invite.html')
                login_link=INVITED_USER_URL + '?username='+str(user.username)
                user.email_user('Registration',t.render(context={'Firstname':user.first_name, 'Inviter':request.user.get_full_name(), 'login_link':login_link}))
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(data={"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invite_new_user_via_qrcode(request, pk=None):
    """
    Invite a new user via qrcode
    """
    data = request.data
    issuing_user=request.user.username
    user = None
    data['password'] = DEFAULT_USER_PASSWORD
    if (('email' not in data) | (data['email']=='')):
        data['email'] = unidecode(data['first_name'].lower()) + str(randint(10, 90)) + '@skoliosekinder.de'
    try:
        user = get_user_model().objects.get(email=data['email'])
        serializer = UserSerializer(user,data={'proofstatus': 'INVITED'}, partial=True)
    except:
        serializer = RegisterSerializer(data={**data,'proofstatus':'INVITED'})
    if serializer.is_valid():
        try:
            with transaction.atomic():
                if not user:
                    user = serializer.save()
                user.create_login_qrcode(notify=issuing_user)
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(data={"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invite_new_user_via_pdf(request, pk=None):
    data = request.data
    user = None
    data['password'] = DEFAULT_USER_PASSWORD
    if ('email' in data):
        if ((data['email']=='') | (data['email']==None)):
            data['email']=unidecode(data['first_name'].lower()) + str(randint(10, 90)) + '@skoliosekinder.de'
    else:
        data['email'] = unidecode(data['first_name'].lower()) + str(randint(10, 90)) + '@skoliosekinder.de'
    try:
        user = get_user_model().objects.get(email=data['email'])
        serializer = UserSerializer(user,data={'proofstatus':'INVITED'},partial=True)
    except:
        serializer = RegisterSerializer(data={**data,'proofstatus':'INVITED'})
    if serializer.is_valid():
        try:
            with transaction.atomic():
                if not user:
                    user = serializer.save()
                # Create a file-like buffer to receive PDF data.
                buffer = io.BytesIO()
                response = HttpResponse(content_type='application/pdf')
                response.headers['Invited-Username']=str(user.username)
                response.headers['Access-Control-Expose-Headers']='Invited-Username'
                response['Content-Disposition'] = 'attachment; invited=%s; filename="file.pdf"'%str(user.username)
                p=PdfFile(recipient=user.postal_address,
                          recipient_name=user.get_full_name(),
                          recipient_email=user.email,
                          recipient_password=DEFAULT_USER_PASSWORD,
                          recipient_username=str(user.username),
                          sender=request.user.get_full_name(),
                          buffer=response)
                success,result=p.build()
                if success:
                    # FileResponse sets the Content-Disposition header so that browsers
                    # present the option to save the file.
                    buffer.seek(0)
                    pdffilecontent=ContentFile(buffer.getvalue())
                    pdffile=InMemoryUploadedFile(pdffilecontent,  # file
                        None,  # field_name
                        result,  # file name
                        'application/pdf',  # content_type
                        pdffilecontent.size,  # size
                        None)
                    return response
                    #return FileResponse(pdffile)
                else:
                    return Response(data={"error": str(result)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(data={"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TokenView(TV):
    """
    Get OAuth Access Token from Login with email or refreshToken or username
    """
    def create_token_response(self, request):
        request.POST._mutable = True
        email = request.POST.pop('email', None)
        username = request.POST.pop('username',None)
        print('Requesting user: %s'%username)
        refresh_token = request.POST.pop('refresh_token',None)
        notify = request.POST.pop('notify',None)  # just in case a ws notification needs to be sent, when user is logging in
        if type(notify)==list:
            notify=notify[0]
        if type(refresh_token)==list:
            refresh_token=refresh_token[0]
        if username:
            user=get_user_model().objects.get(username=username[0])
            request.POST['username'] = username[0]
        if email:
            username = get_user_model().objects.filter(email=email[0]).values_list('username', flat=True).last()
            request.POST['username'] = username
        if refresh_token:
            try:
                rt=RefreshToken.objects.get(token__exact=refresh_token)
                user=rt.user
                device_id=request.POST.pop('uuid',None)
                if type(device_id)==list:
                    device_id=device_id[0]
                device = Device.objects.get(Q(uuid=device_id)&Q(referring_User=user))
                if device:
                    rt.revoke()
                    request.POST['username'] = user.username
                    client_id=request.POST.get('client_id')
                    application = Application.objects.get(client_id=client_id)
                    scope=request.POST.get('scope')
                    present = datetime.now().replace(tzinfo=timezone.utc)
                    expires = present + timedelta(seconds=oauth2_settings.ACCESS_TOKEN_EXPIRE_SECONDS)
                    acc_token=AccessToken.objects.create(user=user, application=application, expires=expires, token=common.generate_token(), scope=scope )
                    r_token=RefreshToken.objects.create(user=user, application=application,access_token=acc_token,token=common.generate_token())
                    request.POST['refresh_token']=str(r_token)
                    #rt.access_token=acc_token
                    #rt.save()
                    #acc_token.save()
            except Exception as e:
                print(e)
        if notify: # notify inviting user
            try:
                inviting_user=get_user_model().objects.get(username=notify)
                if user:
                    invited_user = user
                else:
                    invited_user=get_user_model().objects.get(username=username)
                inviting_user.msg_when_invited_user_logged_in(invited_user=invited_user)
            except Exception as e:
                print(e)
        return super(TokenView, self).create_token_response(request)

@csrf_exempt
@api_view(['POST'])
def exchange_auth0_token(request):
    try:
        # get the auth0 generated JWT Token
        token = request.POST.get('token')
        if len(token) < 20:
            return Response({'error': 'Auth0 error'}, status=status.HTTP_400_BAD_REQUEST)
        # get userinfo from auth0 with that token
        resp = requests.get('https://'+AUTH0_DOMAIN+'/userinfo', headers={'authorization': 'Bearer ' + token})
        if resp.status_code == 200:
            au = json.loads(resp.content)
            # find user in db
            userdata={}
            add_params= {'given_name': 'first_name',
                         'family_name': 'last_name',
                         'birthdate':'date_of_birth',
                         'gender':'sex',
                         'address':'postal_address',
                         'phone_number':'phone_number',
                         'expires':  get_default_expiry()}
            for k,v in add_params.items():
                if k in au:
                    userdata[v]=au[k]
            try:
                user= User.objects.get(email=au['email'])
                for key, value in userdata.items():
                    setattr(user, key, value)
                user.save()
            except User.DoesNotExist:
                userdata['username']=uuid.uuid4()
                userdata['password']=uuid.uuid4()
                userdata['email']=au['email']
                user = User(**userdata)
                user.save()
            client_id = request.POST.get('client_id')
            application = Application.objects.get(client_id=client_id)
            scope = request.POST.get('scope')
            present = datetime.now().replace(tzinfo=timezone.utc)
            expires = present + timedelta(seconds=oauth2_settings.ACCESS_TOKEN_EXPIRE_SECONDS)
            acc_token = AccessToken.objects.create(user=user, application=application, expires=expires,
                                                   token=common.generate_token(), scope=scope)
            r_token = RefreshToken.objects.create(user=user, application=application, access_token=acc_token,
                                                  token=common.generate_token())
            return Response({'access_token': str(acc_token), 'refresh_token': str(r_token)}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Auth0 error'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['GET'])
def forgot_password(request):
    """
    Send 6-char token via email to user upon request
    :param
    :return: username
    """
    try:
        email = request.GET.get('email')
        user = get_user_model().objects.get(email=email)
        serializer = UserSerializer(user, data=request.data, partial=True)  # set partial=True to update a data partially
        if serializer.is_valid():
            with transaction.atomic():
                token = user.create_email_token()
                serializer.save(emailtoken=token,is_emailvalidated=False)
                t = get_template('user/email-forgotpassword.html')
                ts=str(datetime.now(timezone.utc))
                user.email_user('Passwort vergessen. '+ts, t.render(context={
                    'Firstname': user.first_name,
                    'token': token}))
                return Response({'username':user.username}, status=status.HTTP_200_OK)
        else:
            Response({'error': 'User not found'}, status=status.HTTP_400_BAD_REQUEST)
    except:
        return Response({'error':'User not found'},status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['POST'])
def set_new_password(request):
    """
    Set new Password and Refreshes Expiry
    :param
    :return: username
    """
    data=request.data
    username = data['username']
    emailtoken=data['emailtoken']
    if ((len(username)>0) & (len(emailtoken)>0)):
        try:
            user = User.objects.get(username=username, emailtoken=emailtoken)
            serializer=ForgotPasswordSerializer(user, data=data, partial=True)
            if serializer.is_valid():
                with transaction.atomic():
                    serializer.save()
                    return Response(data={'new_password':'OK'},status=status.HTTP_200_OK)
            else:
                return Response({'error': 'User not found or Emailtoken not valid'}, status=status.HTTP_400_BAD_REQUEST)
        except:
            return Response({'error': 'User not found or Emailtoken not valid'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response({'error': 'No Username or emailtoken provided'}, status=status.HTTP_400_BAD_REQUEST)



class DeviceViewSet(viewsets.ModelViewSet):
    """
    A viewset for viewing and editing individual Device instances.
    """
    queryset = Device.objects.all()
    authentication_classes = [OAuth2Authentication]
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.action == 'list':
            user = self.request.user
            return self.queryset.filter(referring_User=user)
        else:
            return self.queryset

    def perform_create(self, serializer):
        serializer.save(referring_User=self.request.user)



class ProofViewSet(viewsets.ModelViewSet):
    """
    A viewset for viewing and editing individual Proof instances.
    """
    queryset = UserProof.objects.all()
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ProofSerializer

    def get_queryset(self):
        if self.action == 'list':
            user = self.request.user
            return self.queryset.filter(referring_User=user)
        else:
            return self.queryset

    def list(self, request, *args, **kwargs):
        """
        Lists the proofs of a given user
        :param args:
        :param kwargs:
        :return: existing proofs as serialized objects and missing proof types as list
        """
        serializer =self.get_serializer(self.get_queryset(), many=True)
        missingproofs=request.user.needs_role_specific_proofs()
        return Response(data={'existing':serializer.data, 'missing':missingproofs}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        serializer.save(referring_User=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated & IsStaff])
    def validate_proof(self, request,pk=None):
        proof=self.get_object()
        ser=ProofSerializer(proof,data={'checkedby':request.user}, partial=True)
        if ser.is_valid():
            ser.save()
            return Response({'status': 'proof validated'})
        else:
            return Response(ser.errors,
                            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated & IsStaff])
    def reject_proof(self, request,pk=None):
        try:
            proof=self.get_object()
            data=request.data
            u=proof.referring_User
            t = get_template('user/email-proof-rejected.html')
            u.email_user('Nachweis nicht akzeptiert', t.render(context={'first_name': u.first_name,'message':data['message']}))
            proof.delete()
        except Exception as e:
            return Response({'error': str(e)},status=status.HTTP_400_BAD_REQUEST)
        return Response({'Validation rejected':'ok'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated & IsStaff])
    def retrieve_user_proof(self, request):
        try:
            username=request.data.get('user')
            user=User.objects.get(username=username)
            proof=user.userproof_set.all()
            ser=ProofSerializer(proof,many=True)
            return Response(ser.data)
        except:
            return Response({'error': 'UserProof Error'}, status=status.HTTP_400_BAD_REQUEST)


class ConsentContentViewSet(viewsets.ModelViewSet):
    """
    A viewset for viewing and editing Consent Document instances.
    """
    queryset = ConsentContent.objects.all()
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ConsentContentSerializer

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    @action(detail=False, permission_classes=[AllowAny])
    def recent_consent_doc(self, request):
        """
        Retrieves the most current consent entry of a given type
        :param request: consent_type needs to be specified as P0, P1 or else
        :return:
        """
        try:
            subset=request.GET.get('consent_type')
            condocs=ConsentContent.objects.filter(consent_type=subset).latest('created')
            serializer = self.get_serializer(condocs, many=False)
            return Response(serializer.data)
        except:
            return Response({'error': 'Consent Doc not found'}, status=status.HTTP_400_BAD_REQUEST)

class ConsentViewSet(viewsets.ModelViewSet):
    """
    A viewset for viewing and editing individual Consent instances.
    """
    queryset = consent.objects.all()
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ConsentSerializer

    def list(self, request, *args, **kwargs):
        """
        Lists the consents of a given user
        :param request: if 'scope' is set to 'all' - also withdrawn consents will be shown, otherwise only valid ones
        :param args:
        :param kwargs:
        :return:
        """
        subset = request.GET.get('scope')
        if subset=='all':
            # retrieve all consents, withdrawn ones as well
            queryset = consent.objects.filter(referring_User=self.request.user)
        else:
            # get only valid consents
            queryset = consent.objects.filter(referring_User=self.request.user, withdraw_date=None)
        serializer = ConsentWithContentSerializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        consentcontent=ConsentContent.objects.get(id=self.request.data['consent_content'])
        serializer.save(referring_User=self.request.user, consent_content=consentcontent)
        self.request.user.removeHelpdeskNotification()

    @action(detail=True,methods=['get'])
    def withdraw(self, request, pk=None):
        con=self.get_object()
        ser=ConsentSerializer(con,data={'withdraw_date':datetime.now().replace(tzinfo=timezone.utc)}, partial=True)
        if ser.is_valid():
            ser.save()
            return Response({'status': 'consent withdrawn'})
        else:
            return Response(ser.errors,
                            status=status.HTTP_400_BAD_REQUEST)