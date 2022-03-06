from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import re_path

from MLModelManager.consumers import MLModelTerminalConsumer
from caserooms.consumers import CaseRoomConsumer
from splineapp.consumers import UserConsumer

#application = ProtocolTypeRouter({'websocket':URLRouter(websocket_urlpatterns)})

application = ProtocolTypeRouter({'websocket':URLRouter([
    re_path(r'ws/splineapp/user/(?P<username>[0-9a-z-]+|\w+)/$', UserConsumer.as_asgi()),
    re_path(r'ws/caseroom/(?P<caseroom>[0-9a-z-]+|\w+)/$', CaseRoomConsumer.as_asgi()),
    re_path(r'ws/mlmodel/(?P<mlmodel>[0-9a-z-]+)/$', MLModelTerminalConsumer.as_asgi()),
])})