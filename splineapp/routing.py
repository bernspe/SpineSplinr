from django.urls import re_path
from . import consumers

websocket_urlpatterns=[
    re_path(r'ws/splineapp/user/(?P<username>[0-9a-z-]+|\w+)/$', consumers.UserConsumer.as_asgi()),
    #re_path(r'ws/splineapp/user/(?P<username>\w+)/$', consumers.UserConsumer.as_asgi()),
    #re_path(r'ws/splineapp/(?P<uuid>[0-9a-f-]+)/$',consumers.SsmConsumer),
    #re_path(r'ws/splineapp/(?P<username>\w+)/$', consumers.SsmConsumer),
    re_path(r'dummy/$',consumers.SsmConsumer),
]