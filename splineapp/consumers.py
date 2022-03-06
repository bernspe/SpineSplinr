import json

import channels
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from guardian.shortcuts import get_users_with_perms

from splineapp.models import SpineSplineModel
from splineapp.serializers import SpineSplineSerializer
from users.models import User


class UserConsumer(WebsocketConsumer):
    def connect(self):
        # uuid = self.scope['url_route']['kwargs']['uuid']
        async_to_sync(self.channel_layer.group_add)('splineapp', self.channel_name)
        urlinfo = self.scope['url_route']['kwargs']
        self.owner = urlinfo['username']
        #check if owner is staff
        u=User.objects.get(username=self.owner)
        self.is_staff=u.is_staff
        # async_to_sync(self.channel_layer.group_add)(uuid, self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        # uuid = self.scope['url_route']['kwargs']['uuid']
        # async_to_sync(self.channel_layer.group_discard(uuid,self.channel_name))
        async_to_sync(self.channel_layer.group_discard('splineapp', self.channel_name))

    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        self.send(text_data=json.dumps({'message': message}))

    def ssm_message(self, event):
        message = event['text']
        if ('ssm_owner' in message.keys()):
            ssm=SpineSplineModel.objects.get(id=message['ssm_id'])
            assoc_users=get_users_with_perms(ssm,only_with_perms_in=['view_spinesplinemodel'])
            if ((self.owner in [u.username for u in assoc_users]) | (message['ssm_owner'] == self.owner) | self.is_staff):
                self.send(text_data=json.dumps({'message': message, 'action': 'SOCKET_ONSSMMESSAGE'}))


        else:
            print('Message %s did not fit')
            print(message)

    def ssm_deleted(self, event):
        message = event['text']
        if ('ssm_owner' in message.keys()):
            assoc_users=message['assoc_users']
            if ((self.owner in assoc_users) | (message['ssm_owner'] == self.owner) | self.is_staff):
                self.send(text_data=json.dumps({'message': message, 'action': 'SOCKET_ONSSMMESSAGE'}))
        else:
            print('Message %s did not fit')
            print(message)

    def caseroom_changed(self, event):
        urlinfo = self.scope['url_route']['kwargs']
        adressee = urlinfo['username']
        message = event['text']
        status = message['status']
        if ('caseroom_members' in message.keys()):
            if ((status=='created') | (status=='deleted')):
                if (adressee in message['caseroom_members']):
                    self.send(text_data=json.dumps({'message': message, 'action': 'SOCKET_ONCASEROOM_CHANGED'}))
            else:
                if ((adressee in message['caseroom_members']) | (adressee in message['caseroom_owner'])):
                    self.send(text_data=json.dumps({'message': message, 'action': 'SOCKET_ONCASEROOM_CHANGED'}))
        else:
            print('Message %s did not fit')
            print(message)


    def caseroom_message(self, event):
        urlinfo = self.scope['url_route']['kwargs']
        adressee = urlinfo['username']
        message = event['text']
        if ('caseroom_participants' in message.keys()):
            if (adressee in message['caseroom_participants']):
                self.send(text_data=json.dumps({'message': message, 'action': 'SOCKET_ONCASEROOM_MSG'}))
        else:
            print('Message %s did not fit')
            print(message)

    def caseroom_watched(self, event):
        urlinfo = self.scope['url_route']['kwargs']
        adressee = urlinfo['username']
        message = event['text']
        if ('caseroom_participants' in message.keys()):
            if (adressee in message['caseroom_participants']):
                self.send(text_data=json.dumps({'message': message, 'action': 'SOCKET_ONCASEROOM_WATCHED'}))
        else:
            print('Message %s did not fit')
            print(message)


    def user_loggedin(self, event):
        urlinfo = self.scope['url_route']['kwargs']
        adressee = urlinfo['username']
        message = event['text']
        if ('adressee' in message.keys()):
            self.send(text_data=json.dumps({'message': message, 'action': 'SOCKET_ONUSERQR_LOGGED_IN'}))
        else:
            print('Message %s did not fit')
            print(message)

    def user_deniedlogin(self, event):
        urlinfo = self.scope['url_route']['kwargs']
        adressee = urlinfo['username']
        message = event['text']
        if ('adressee' in message.keys()):
            self.send(text_data=json.dumps({'message': message, 'action': 'SOCKET_ONUSERQR_DENIED_LOGIN'}))
        else:
            print('Message %s did not fit')
            print(message)

class SsmConsumer(WebsocketConsumer):
    def connect(self):
        #uuid = self.scope['url_route']['kwargs']['uuid']
        async_to_sync(self.channel_layer.group_add)('splineapp',self.channel_name)
        #async_to_sync(self.channel_layer.group_add)(uuid, self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        #uuid = self.scope['url_route']['kwargs']['uuid']
        #async_to_sync(self.channel_layer.group_discard(uuid,self.channel_name))
        async_to_sync(self.channel_layer.group_discard('splineapp', self.channel_name))

    def receive(self, text_data):
        text_data_json=json.loads(text_data)
        message = text_data_json['message']
        self.send(text_data=json.dumps({'message':message}))

    def ssm_message_old(self,event):
        urlinfo=self.scope['url_route']['kwargs']
        if 'uuid' in urlinfo.keys():
            uuid = urlinfo['uuid']
        message = event['text']
        if (message['ssm_id']==uuid):
            print('Message %s sent.' % message['status'])
            self.send(text_data=json.dumps({'message': message}))
        else:
            print('Message %s did not fit')
            print(message)

