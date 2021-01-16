from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from rest_framework import status
from django.conf.urls import include, url
from django.contrib import admin
from apps.accounts.views.oauth2_profile import openidconnect_userinfo
from apps.fhir.bluebutton.views.home import fhir_conformance
from hhs_oauth_server.hhs_oauth_server_context import IsAppInstalled

admin.autodiscover()

ADMIN_REDIRECTOR = getattr(settings, 'ADMIN_PREPEND_URL', '')


urlpatterns = [
    url(r'^health', include('apps.health.urls')),
    url(r'^.well-known/', include('apps.wellknown.urls')),
    url(r'^v1/accounts/', include('apps.accounts.urls')),
    url(r'^v1/connect/userinfo', openidconnect_userinfo, name='openid_connect_userinfo'),
    url(r'^v1/fhir/metadata$', fhir_conformance, name='fhir_conformance_metadata'),
    url(r'^v1/fhir/', include('apps.fhir.bluebutton.urls')),
    url(r'^v1/o/', include('apps.dot_ext.urls')),
    url(r'^v1/o/', include('apps.authorization.urls')),
    url(r'^v1/', include('apps.openapi.urls')),

    url(r'^v2/accounts/', include('apps.accounts.v2.urls')),
    url(r'^v2/connect/userinfo', openidconnect_userinfo, name='openid_connect_userinfo_v2'),
    url(r'^v2/fhir/metadata$', fhir_conformance, name='fhir_conformance_metadata_v2'),
    url(r'^v2/fhir/', include('apps.fhir.bluebutton.v2.urls')),
    url(r'^v2/o/', include('apps.dot_ext.v2.urls')),
    url(r'^v2/o/', include('apps.authorization.v2.urls')),
    url(r'^v2/', include('apps.openapi.urls')),

    url(r'^' + ADMIN_REDIRECTOR + 'admin/metrics/', include('apps.metrics.urls')),


    url(r'^' + ADMIN_REDIRECTOR + 'admin/', admin.site.urls),
]

# If running in local development, add the media and static urls:
if settings.IS_MEDIA_URL_LOCAL is True:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if IsAppInstalled("apps.testclient"):
    urlpatterns += [
        url(r'^testclient/', include('apps.testclient.urls')),
    ]

if IsAppInstalled("apps.mymedicare_cb"):
    urlpatterns += [
        url(r'^mymedicare/', include('apps.mymedicare_cb.urls')),
    ]

if not getattr(settings, 'NO_UI', False):
    urlpatterns += [
        url(r'', include('apps.home.urls')),
    ]

handler500 = 'hhs_oauth_server.urls.server_error'
handler400 = 'hhs_oauth_server.urls.bad_request'


# TODO Replace this with defaults from rest_framework once upgrated to > 3.7.7
def server_error(request, *args, **kwargs):
    """
    Generic 500 error handler.
    """
    data = {
        'error': 'Server Error (500)'
    }
    return JsonResponse(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def bad_request(request, exception, *args, **kwargs):
    """
    Generic 400 error handler.
    """
    data = {
        'error': 'Bad Request (400)'
    }
    return JsonResponse(data, status=status.HTTP_400_BAD_REQUEST)
