
from django.contrib import admin

from django.contrib.auth.decorators import login_required
from django.urls import path, include
from django.conf.urls import url
from django.views.static import serve
from rest_framework.decorators import permission_classes, api_view
from rest_framework.permissions import IsAuthenticated

from MLModelManager.views import get_mlmodel_types
from SpineSplinr import settings
from users.views import UserRegister, check_token, forgot_password, confirm_email, TokenView, \
    UserViewSet, get_minprofile_from_users, ConsentTypesList, \
    get_dependent_children, validate_names, get_caregiver, check_emailexists, set_new_password, check_defaultpassword, \
    invite_new_user_via_email, get_medical_users, invite_new_user_via_pdf, get_version, invite_new_user_via_qrcode, \
    get_minprofile_from_currently_invited_user, deny_qrcode_login, exchange_auth0_token


# shielding media folders from unauthorized access
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def protected_serve(request, path, document_root=None, show_indexes=False):
    return serve(request, path, document_root, show_indexes)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('cr/', include('caserooms.urls')),
    path('', include('splineapp.urls')),

]

urlpatterns += [
    url(r'^%s(?P<path>.*)$' % settings.MEDIA_URL_PROTECTED[1:], protected_serve, {'document_root': settings.MEDIA_ROOT_PROTECTED}),
    url(r'^%s(?P<path>.*)$' % settings.MEDIA_URL[1:], serve, {'document_root': settings.MEDIA_ROOT,}),
    #   url(r'^api/login/', include('rest_social_auth.urls_token')),
 #   url(r'^api/login/', include('rest_social_auth.urls_session')),
 #   url(r'^auth/', include('rest_framework_social_oauth2.urls')),
    url(r'version/',get_version),
    url(r'userinfo/', check_token),
    url(r'emailexists',check_emailexists),
    url(r'forgotpassword/email/', forgot_password),
    path('setnewpassword/',set_new_password),
    path('check_defaultpassword/',check_defaultpassword),
    path('invite_via_email/', invite_new_user_via_email),
    path('invite_via_pdf/', invite_new_user_via_pdf),
    path('invite_via_qrcode/', invite_new_user_via_qrcode),
    path('api-auth/', include('rest_framework.urls')),
    path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    path('o/emailtoken/', TokenView.as_view()),  # The customized TokenView
    path('auth0token/', exchange_auth0_token),
#    path('sociallogin/', SocialLogin.as_view()),
    path('register/activate/<pk>/',confirm_email), #Link to confirm user eMail and set guest status or retain status
    path('register/', UserRegister.as_view()),
    path('consenttypeslist/', ConsentTypesList.as_view()),
#    path('getmedicalstaff/', get_medical_staff),
    path('getmedicalusers/', get_medical_users),
    path('getdependentchildren/', get_dependent_children),
    path('getcaregiver/', get_caregiver),
    path('getminprofilefromusers/', get_minprofile_from_users),
    path('getminprofilefromcurrentlyinviteduser/',get_minprofile_from_currently_invited_user),
    path('denyqrcodelogin/',deny_qrcode_login),
    path('validatenames/', validate_names),
    path('getmlmodeltypes/',get_mlmodel_types),

 ]
