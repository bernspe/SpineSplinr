import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

class MLModelTerminalConsumer(WebsocketConsumer):
    def connect(self):
        async_to_sync(self.channel_layer.group_add)('mlmodel', self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard('mlmodel', self.channel_name))

    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        self.send(text_data=json.dumps({'message': message}))

    def mlmodel_message(self, event):
        urlinfo = self.scope['url_route']['kwargs']
        mlmodel = urlinfo['mlmodel']
        message = event['text']
        if (str(message['id']) == mlmodel):
            self.send(text_data=json.dumps({'message': message, 'action': 'SOCKET_ONMLMODEL_MESSAGE'}))

    def mlmodel_result(self, event):
        urlinfo = self.scope['url_route']['kwargs']
        mlmodel = urlinfo['mlmodel']
        message = event['text']
        if (str(message['id']) == mlmodel):
            self.send(text_data=json.dumps({'message': message, 'action': 'SOCKET_ONMLMODEL_RESULT'}))
