import logging
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from collections import OrderedDict
from django.conf import settings
from django.urls import reverse
logger = logging.getLogger('hhs_server.%s' % __name__)


@require_GET
def openid_configuration(request):
    """
    Views that returns openid_configuration.
    """
    data = OrderedDict()
    issuer = base_issuer(request)
    data = build_endpoint_info(data, issuer=issuer, v2=request.path.endswith('openid-configuration-v2'))
    return JsonResponse(data)


def base_issuer(request):
    """
    define the base url for issuer

    """
    issuer = getattr(settings, 'HOSTNAME_URL', 'http://localhost:8000')

    if "http://" in issuer.lower():
        pass
    elif "https://" in issuer.lower():
        pass
    else:
        logger.debug("HOSTNAME_URL [%s] "
                     "does not contain http or https prefix. "
                     "Issuer:%s" % (settings.HOSTNAME_URL, issuer))
        # no http/https prefix in HOST_NAME_URL so we add it
        if request.is_secure():
            http_mode = 'https://'
        else:
            http_mode = 'http://'

        # prefix hostname with http/https://
        issuer = http_mode + issuer

    return issuer


def build_endpoint_info(data=OrderedDict(), issuer="", v2=False):
    """
    construct the data package
    issuer should be http: or https:// prefixed url.

    :param data:
    :return:
    """
    data["issuer"] = issuer
    data["authorization_endpoint"] = issuer + \
        reverse('oauth2_provider:authorize' if not v2 else 'oauth2_provider_v2:authorize-v2')
    data["token_endpoint"] = issuer + \
        reverse('oauth2_provider:token' if not v2 else 'oauth2_provider_v2:token-v2')
    data["userinfo_endpoint"] = issuer + \
        reverse('openid_connect_userinfo' if not v2 else 'openid_connect_userinfo_v2')
    data["ui_locales_supported"] = ["en-US", ]
    data["service_documentation"] = getattr(settings,
                                            'DEVELOPER_DOCS_URI',
                                            "https://cmsgov.github.io/bluebutton-developer-help/")
    data["op_tos_uri"] = settings.TOS_URI
    data["grant_types_supported"] = []
    for i in settings.GRANT_TYPES:
        data["grant_types_supported"].append(i[0])
    data["grant_types_supported"].append("refresh_token")
    data["response_types_supported"] = ["code", "token"]
    data["fhir_metadata_uri"] = issuer + \
        reverse('fhir_conformance_metadata' if not v2 else 'fhir_conformance_metadata_v2')
    return data
