import json

from httmock import all_requests, HTTMock
from oauth2_provider.compat import parse_qs, urlparse
from oauth2_provider.models import AccessToken
from waffle.testutils import override_switch, override_flag

from apps.capabilities.models import ProtectedCapability
from apps.authorization.models import DataAccessGrant
from apps.fhir.bluebutton.signals import pre_fetch
from apps.fhir.bluebutton.views.generic import FhirDataView
from apps.test import BaseApiTest
from ..models import Application


def create_patient_capability(group,
                              fhir_prefix,
                              title="My general patient and demographic information."):

    c = None
    description = "Patient FHIR Resource"
    smart_scope_string = "patient/Patient.read"
    pr = []
    pr.append(["GET", "%sPatient/" % fhir_prefix])
    pr.append(["GET", "%sPatient/[id]" % fhir_prefix])
    if not ProtectedCapability.objects.filter(slug=smart_scope_string).exists():
        c = ProtectedCapability.objects.create(group=group,
                                               title=title,
                                               description=description,
                                               slug=smart_scope_string,
                                               protected_resources=json.dumps(pr, indent=4))
    return c


class TestBFDHeaders(BaseApiTest):
    def fetching_data(self, sender, request=None, **kwargs):
        hdr = request.headers.get('includeAddressFields')
        self.assertTrue(hdr)
        self.assertEqual(hdr, "False")

    def setUp(self):
        # found this test silently went through without testing the header's present
        # the reason: sender=SearchView no longer match the runtime code:
        # now the signal is sent with sender=FhirDataView
        # pre_fetch.connect(self.fetching_data, sender=SearchView)
        pre_fetch.connect(self.fetching_data, sender=FhirDataView)

    def tearDown(self):
        # pre_fetch.disconnect(self.fetching_data, sender=SearchView)
        pre_fetch.disconnect(self.fetching_data, sender=FhirDataView)

    def _create_test_token(self, user, application):
        # user logs in
        self.client.force_login(user)
        # post the authorization form with only one scope selected
        payload = {
            'client_id': application.client_id,
            'response_type': 'code',
            'redirect_uri': application.redirect_uris,
            'scope': application.scopes().split(" "),
            'expires_in': 86400,
            'allow': True,
        }
        if application.authorization_grant_type == Application.GRANT_IMPLICIT:
            payload['response_type'] = 'token'
        response = self.client.post('/v1/o/authorize/', data=payload)
        self.client.logout()
        if response.status_code != 302:
            raise Exception(response.context_data)
        self.assertEqual(response.status_code, 302)
        # now extract the authorization code and use it to request an access_token
        if application.authorization_grant_type == Application.GRANT_IMPLICIT:
            fragment = parse_qs(urlparse(response['Location']).fragment)
            tkn = fragment.pop('access_token')[0]
        else:
            query_dict = parse_qs(urlparse(response['Location']).query)
            authorization_code = query_dict.pop('code')
            token_request_data = {
                'grant_type': 'authorization_code',
                'code': authorization_code,
                'redirect_uri': application.redirect_uris,
                'client_id': application.client_id,
                'client_secret': application.client_secret,
            }

            response = self.client.post('/v1/o/token/', data=token_request_data)
            self.assertEqual(response.status_code, 200)
            # Now we have a token and refresh token
            tkn = response.json()['access_token']

        t = AccessToken.objects.get(token=tkn)
        return t

    @override_switch('bfd_v2', active=True)
    @override_flag('bfd_v2_flag', active=True)
    def test_fhir_request_has_header(self):
        # create an app for a user and obtain a token
        anna = self._create_user('anna', '123456', fhir_id='-20140000008325')
        # capability_a = self._create_capability('token_management', [['DELETE', r'/v1/o/tokens/\d+/']], default=False)
        application = self._create_application(
            'an app', grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris='http://example.it')
        fhir_prefix = "/v1/fhir/"
        test_grp = self._create_group('test')
        pt_cap = create_patient_capability(test_grp, fhir_prefix)
        application.scope.add(pt_cap)
        tkn = self._create_test_token(anna, application)
        # check access token
        self.assertTrue(DataAccessGrant.objects.filter(
            beneficiary=anna,
            application=application,
        ).exists())

        @all_requests
        def catchall(url, req):
            return {
                'status_code': 200,
                'content':{"resourceType":"Patient","id":"-20140000008325","extension":[{"url":"https://bluebutton.cms.gov/resources/variables/race","valueCoding":{"system":"https://bluebutton.cms.gov/resources/variables/race","code":"1","display":"White"}}],"identifier":[{"system":"https://bluebutton.cms.gov/resources/variables/bene_id","value":"-20140000008325"},{"system":"https://bluebutton.cms.gov/resources/identifier/hicn-hash","value":"2025fbc612a884853f0c245e686780bf748e5652360ecd7430575491f4e018c5"}],"name":[{"use":"usual","family":"Doe","given":["Jane","X"]}],"gender":"unknown","birthDate":"2014-06-01","address":[{"district":"999","state":"15","postalCode":"99999"}]} # noqa
            }

        with HTTMock(catchall):
            response = self.client.get('/v1/fhir/Patient', HTTP_AUTHORIZATION="Bearer " + tkn.token)
            self.assertEqual(response.status_code, 200)
            # v2 support
            response = self.client.get('/v2/fhir/Patient', HTTP_AUTHORIZATION="Bearer " + tkn.token)
            self.assertEqual(response.status_code, 200)
            response = self.client.get('/v1/fhir/Patient/-20140000008325', HTTP_AUTHORIZATION="Bearer " + tkn.token)
            self.assertEqual(response.status_code, 200)
            # v2 support
            response = self.client.get('/v2/fhir/Patient/-20140000008325', HTTP_AUTHORIZATION="Bearer " + tkn.token)
            self.assertEqual(response.status_code, 200)
