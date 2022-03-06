"""
ASGI config for SpineSplinr project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/asgi/
"""

import os

import django
#from channels.routing import get_default_application
from django.core.asgi import get_asgi_application
from django.urls import re_path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SpineSplinr.settings')
django.setup()
#application = get_default_application()

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from MLModelManager.consumers import MLModelTerminalConsumer
from caserooms.consumers import CaseRoomConsumer
from splineapp.consumers import UserConsumer, SsmConsumer



application = ProtocolTypeRouter({
    # Django's ASGI application to handle traditional HTTP requests
    #"http": django_asgi_app,

    # WebSocket chat handler
    "websocket": AuthMiddlewareStack(
        URLRouter([
            re_path(r'ws/splineapp/user/(?P<username>[0-9a-z-]+|\w+)/$', UserConsumer.as_asgi()),
            re_path(r'ws/caseroom/(?P<caseroom>[0-9a-z-]+)/$', CaseRoomConsumer.as_asgi()),
            re_path(r'ws/mlmodel/(?P<mlmodel>[0-9a-z-]+)/$', MLModelTerminalConsumer.as_asgi()),
            # re_path(r'ws/splineapp/(?P<uuid>[0-9a-f-]+)/$',consumers.SsmConsumer),
            # re_path(r'ws/splineapp/(?P<username>\w+)/$', consumers.SsmConsumer),
            re_path(r'dummy/$', SsmConsumer.as_asgi()),
        ])
    ),
})
