import channels
from asgiref.sync import async_to_sync
from django.db.models import Q
from guardian.shortcuts import remove_perm
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework import viewsets, status
from rest_framework.decorators import action, permission_classes
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from SpineSplinr.settings import HELPDESK_NAME, GEN_STAFF_USER
from caserooms.models import CaseRoom, CaseRoomEntry
from caserooms.permissions import IsOwner, IsPatient
from caserooms.serializers import CaseRoomSerializer, CaseRoomEntrySerializer
from splineapp.serializers import SpineSplineSerializer
from users.models import User, Userrole
from users.permissions import IsStaff
from users.serializers import UserNameEmailSerializer


class CaseRoomViewSet(viewsets.ModelViewSet):
    """
    A viewset for viewing and editing Caseroom instances.
    """
    serializer_class = CaseRoomSerializer
    queryset = CaseRoom.objects.all()
    authentication_classes = [OAuth2Authentication]

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        permission_classes = [IsAuthenticated]
        if self.action == 'list':
            permission_classes+= [IsAdminUser]
        if self.action == 'create':
            permission_classes += [IsPatient]
        return [permission() for permission in permission_classes]

  #  def perform_create(self, serializer):
  #      serializer.save(context={'request': self.request})

    def list(self, request):
        queryset = CaseRoom.objects.all()
        serializer = CaseRoomSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def listbyowner(self,request):
        """
        List the caseroom instances per owner
        """
        queryset = CaseRoom.objects.filter(owner=request.user)
        serializer = CaseRoomSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def listbymember(self,request):
        """
        List the caseroom instances per member
        """
        queryset = CaseRoom.objects.filter(members=request.user)
        serializer = CaseRoomSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def listbyparticipant(self,request):
        """
        List the caseroom instances per caseroom participant (owner or member)
        """
        queryset = CaseRoom.objects.filter(Q(members=request.user) | Q(owner=request.user)).distinct()
        serializer = CaseRoomSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    @permission_classes([IsStaff])
    def listonlyhelpdesk(self,request):
        """
        List only the caseroom helpdesk instances
        """
        queryset = CaseRoom.objects.filter(title__contains=HELPDESK_NAME)
        serializer = CaseRoomSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def list_cr_users_w_ssm(self,request, pk=None):
        """
        List the caseroom users with ssm instances
        """
        cr=CaseRoom.objects.get(id=pk)
        users = cr.get_members_and_owners_with_active_SSM()
        serializer = UserNameEmailSerializer(users, many=True)
        return Response(serializer.data)


    def retrieve(self, request, pk=None):
        queryset = CaseRoom.objects.all()
        cr = get_object_or_404(queryset, pk=pk)
        serializer = CaseRoomSerializer(cr)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def what_are_the_news(self, request):
        """
        get the caseroom with news-tag
        """
        user=request.user
        cr = get_object_or_404(user.caserooms_news.all())
        serializer = CaseRoomSerializer(cr)
        return Response(serializer.data, status=status.HTTP_200_OK)


    @action(detail=True, methods=['patch'])
    def eliminate_news_tag(self, request, pk=None):
        """
        Eliminate the news tag and the email reminder tag from the requesting user
        """
        cr = CaseRoom.objects.get(pk=pk)
        try:
            r_users=[request.user]
            if (request.user.is_staff):
                gen_user=User.objects.get(username=GEN_STAFF_USER['username'])
                r_users.append(gen_user)
            for r in r_users:
                cr.news_for_participants.remove(r)
                cr.email_reminder_for_participants.remove(r)
                cr.msg_caseroom_watched(r)
        except:
            pass
        serializer = CaseRoomSerializer(cr, partial=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def add_user(self, request, pk=None):
        """
        A Caseroom member is added
        """
        cr = CaseRoom.objects.get(pk=pk)
        data = request.data
        try:
            if 'user' in data.keys():
                data = data['user']
                if type(data)!=list:
                    data=[data]
                for d in data:
                    user=User.objects.get(username=d['username'])
                    if user:
                        cr.add_user_to_cr(user)
            serializer = CaseRoomSerializer(cr, partial=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            print('Exception: '+str(e))
        return Response(status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def leave(self, request, pk=None):
        """
        The CaseRoom is left by the current user
        """
        cr = CaseRoom.objects.get(pk=pk)
        try:
            cr.delete_user_from_cr(request.user)
        except:
            pass
        serializer = CaseRoomSerializer(cr, partial=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def delete_user(self, request, pk=None):
        """
        A Caseroom member is removed from the current caseroom
        """
        cr = CaseRoom.objects.get(pk=pk)
        data = request.data
        try:
            if 'user' in data.keys():
                user=User.objects.get(username=data['user'])
                if user:
                    cr.delete_user_from_cr(user)
                    children = user.dependent_children.all()
                    for c in children:
                        if c in cr.members.all():
                            cr.delete_user_from_cr(c)
                    serializer = CaseRoomSerializer(cr, partial=True)
                    return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            print('Exception: '+str(e))
        return Response(status=status.HTTP_400_BAD_REQUEST)

class CaseRoomEntryViewSet(viewsets.ModelViewSet):
    """
    A viewset for viewing and editing Caseroom Entry instances.
    """
    serializer_class = CaseRoomEntrySerializer
    queryset = CaseRoomEntry.objects.all()
    authentication_classes = [OAuth2Authentication]

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user) #, caseroom=self.request.data['caseroom'], text=self.request.data['text']

    def list(self, request):
        caseroom=request.GET.get('caseroom')
        caseroom_object=CaseRoom.objects.get(id=caseroom)
        sufficiently_consented,missing_users=caseroom_object.is_sufficiently_consented()
        if sufficiently_consented | (HELPDESK_NAME in caseroom_object.title):
            queryset = CaseRoomEntry.objects.filter(caseroom=caseroom)
            serializer = CaseRoomEntrySerializer(queryset, many=True)
            return Response(serializer.data)
        else:
            missing_usernames=[str(u.username) for u in missing_users]
            missing_user_fullnames=[u.get_full_name() for u in missing_users]
            if caseroom_object.owner == request.user:
                pass
            else:
                caseroom_object.msg_to_caseroom_owner_if_consent_is_needed()
            return Response(data={'caseroom_error':'not sufficiently consented',
                                  'missing_usernames':missing_usernames,
                                  'missing_user_fullnames':missing_user_fullnames,
                                  'caseroom_owner':str(caseroom_object.owner.username)}, status=status.HTTP_400_BAD_REQUEST)