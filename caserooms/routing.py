from django.urls import re_path
from . import consumers

caseroom_urlpatterns=[
    re_path(r'ws/caseroom/(?P<caseroom>[0-9a-z-]+|\w+)/$', consumers.CaseRoomConsumer.as_asgi()),
]