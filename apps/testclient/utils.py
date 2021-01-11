from collections import OrderedDict
from django.conf import settings
from ..dot_ext.models import Application


def test_setup(include_client_secret=True, v2=False):
    response = OrderedDict()
    ver = 'v2' if v2 else 'v1'
    oa2client = Application.objects.get(name="TestApp")
    response['client_id'] = oa2client.client_id
    if include_client_secret:
        response['client_secret'] = oa2client.client_secret
    host = getattr(settings, 'HOSTNAME_URL', 'http://localhost:8000')
    if not (host.startswith("http://") or host.startswith("https://")):
        host = "https://" + host
    response['resource_uri'] = host
    # this has to match app's redirect uri
    if v2:
        response['redirect_uri'] = '{}{}'.format(host, settings.TESTCLIENT_REDIRECT_URI_V2)
    else:
        response['redirect_uri'] = '{}{}'.format(host, settings.TESTCLIENT_REDIRECT_URI)
    response['authorization_uri'] = '{}/{}/o/authorize/'.format(host, ver)
    response['token_uri'] = '{}/{}/o/token/'.format(host, ver)
    response['userinfo_uri'] = '{}/{}/connect/userinfo'.format(host, ver)
    response['patient_uri'] = '{}/{}/fhir/Patient/'.format(host, ver)
    response['eob_uri'] = '{}/{}/fhir/ExplanationOfBenefit/'.format(host, ver)
    response['coverage_uri'] = '{}/{}/fhir/Coverage/'.format(host, ver)
    return(response)


def get_client_secret():
    oa2client = Application.objects.get(name="TestApp")
    return oa2client.client_secret
