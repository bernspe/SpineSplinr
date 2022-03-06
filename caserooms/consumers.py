import json

import channels
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

class CaseRoomConsumer(WebsocketConsumer):
    def connect(self):
        async_to_sync(self.channel_layer.group_add)('caseroom', self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard('caseroom', self.channel_name))

    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        self.send(text_data=json.dumps({'message': message}))

    def caseroom_message(self, event):
        urlinfo = self.scope['url_route']['kwargs']
        caseroom = urlinfo['caseroom']
        message = event['text']
        if ('caseroom' in message.keys()):
            if (str(message['caseroom']) == caseroom):
                self.send(text_data=json.dumps({'message': message, 'namespace': 'caseroom'}))
        else:
            print('Message %s did not fit')
            print(message)