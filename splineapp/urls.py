from django.urls import path, include
from django.views.generic import TemplateView
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.routers import DefaultRouter, SimpleRouter
from rest_framework.schemas import get_schema_view

from MLModelManager.views import MLModelManagerViewSet
from caserooms.permissions import IsPatient
from splineapp import views

from SpineSplinr import settings

# Create a router and register our viewsets with it.
from users.views import UserViewSet, ConsentContentViewSet, ConsentViewSet, UserroleViewSet, ProofViewSet, DeviceViewSet

router = DefaultRouter()

router.register(r'splineapp', views.SpineSplineViewSet, basename='splineapp')
router.register(r'collection',views.SpineSplineCollectionViewSet, basename='collection')
router.register(r'users',UserViewSet)
router.register(r'userrole',UserroleViewSet)
router.register(r'userproof',ProofViewSet)
router.register(r'device',DeviceViewSet)
router.register(r'consentcontent',ConsentContentViewSet)
router.register(r'consent',ConsentViewSet),
router.register(r'mlmodel',MLModelManagerViewSet),


def trigger_error(request):
    division_by_zero = 1 / 0

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path('', include(router.urls)),
   # url(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT,})
  #  path('img/<int:img_id>/', views.imgpage, name='imgpage'),
]

urlpatterns += [
 #   path('api-token-auth/',obtain_auth_token, name='api_token_auth' ),
    path('sentry-debug/', trigger_error),
]

#Documentation
urlpatterns += [
    # ...
    # Use the `get_schema_view()` helper to add a `SchemaView` to project URLs.
    #   * `title` and `description` parameters are passed to `SchemaGenerator`.
    #   * Provide view name for use with `reverse()`.
    path('openapi/', get_schema_view(
        title="SpineSplinrAPI",
        description="API for serving AI methods to analyze scoliotic deformity",
        version=settings.VERSION,
        authentication_classes=[OAuth2Authentication, SessionAuthentication],
        permission_classes=[IsAuthenticated, IsPatient, AllowAny]
    ), name='openapi-schema'),
    path('swagger-ui/', TemplateView.as_view(
        template_name='swagger-ui.html',
        extra_context={'schema_url': 'openapi-schema'}
    ), name='swagger-ui'),
]