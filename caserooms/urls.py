from rest_framework.routers import DefaultRouter
from django.urls import path, include
from caserooms.views import CaseRoomViewSet, CaseRoomEntryViewSet

router = DefaultRouter()
router.register(r'caseroom', CaseRoomViewSet)
router.register(r'caseroomentry', CaseRoomEntryViewSet)

urlpatterns = [
    path('', include(router.urls))
    ]