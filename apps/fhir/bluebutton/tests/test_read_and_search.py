from unittest.mock import patch
import json
from httmock import all_requests, HTTMock, urlmatch
from apps.mymedicare_cb.tests.responses import patient_response
import apps.fhir.bluebutton.utils
import apps.fhir.bluebutton.views.home
from apps.fhir.bluebutton.views.home import (conformance_filter)
from django.test import TestCase, RequestFactory
from apps.test import BaseApiTest
from django.conf import settings
from django.test.client import Client
from oauth2_provider.models import get_access_token_model
from django.urls import reverse

# Get the pre-defined Conformance statement
from .data_conformance import CONFORMANCE

AccessToken = get_access_token_model()


class ConformanceReadRequestTest(TestCase):
    """ Check the BlueButton API call  """

    # 'fhir_server_testdata_prep.json',
    fixtures = ['fhir_bluebutton_test_rt.json']

    def setUp(self):
        # Setup the RequestFactory
        self.factory = RequestFactory()
        self.client = Client()

    @patch('apps.fhir.bluebutton.utils.requests')
    def test_fhir_bluebutton_read_conformance_testcase(self, mock_requests):
        """ Checking Conformance

            The @patch replaces the call to requests with mock_requests

        """

        call_to = '/bluebutton/fhir/v1/metadata'
        request = self.factory.get(call_to)

        # Now we can setup the responses we want to the call
        mock_requests.get.return_value.status_code = 200
        mock_requests.get.return_value.content = CONFORMANCE

        # Make the call to request_call which uses requests.get
        # patch will intercept the call to requests.get and
        # return the pre-defined values
        result = apps.fhir.bluebutton.utils.request_call(request,
                                                         call_to,
                                                         crosswalk=None)

        # Test for a match
        self.assertEqual(result._response.content, CONFORMANCE)

    def test_fhir_conformance_filter(self):
        """ Check filtering of Conformance Statement """

        conform_out = json.loads(CONFORMANCE)
        result = conformance_filter(conform_out)

        if "vision" in result['rest'][0]['resource']:
            filter_works = False
        else:
            filter_works = True

        self.assertEqual(filter_works, True)


class ThrottleReadRequestTest(BaseApiTest):

    def setUp(self):
        # create read and write capabilities
        self.read_capability = self._create_capability('Read', [])
        self.write_capability = self._create_capability('Write', [])
        self._create_capability('patient', [
            ["GET", r"\/v1\/fhir\/Patient\/\-\d+"],
            ["GET", "/v1/fhir/Patient"],
        ])
        # Setup the RequestFactory
        self.client = Client()

    @patch('apps.dot_ext.throttling.TokenRateThrottle.get_rate')
    def test_read_throttle(self,
                           mock_rates):
        mock_rates.return_value = '1/day'
        # create the user
        first_access_token = self.create_token('John', 'Smith')

        @all_requests
        def catchall(url, req):
            return {
                'status_code': 200,
                'content':{"resourceType":"Patient","id":"-20140000008325","extension":[{"url":"https://bluebutton.cms.gov/resources/variables/race","valueCoding":{"system":"https://bluebutton.cms.gov/resources/variables/race","code":"1","display":"White"}}],"identifier":[{"system":"https://bluebutton.cms.gov/resources/variables/bene_id","value":"-20140000008325"},{"system":"https://bluebutton.cms.gov/resources/identifier/hicn-hash","value":"2025fbc612a884853f0c245e686780bf748e5652360ecd7430575491f4e018c5"}],"name":[{"use":"usual","family":"Doe","given":["Jane","X"]}],"gender":"unknown","birthDate":"2014-06-01","address":[{"district":"999","state":"15","postalCode":"99999"}]} # noqa
            }

        with HTTMock(catchall):

            response = self.client.get(
                reverse(
                    'bb_oauth_fhir_patient_read_or_update_or_delete',
                    kwargs={'resource_id': -20140000008325}),
                Authorization="Bearer %s" % (first_access_token))

            self.assertEqual(response.status_code, 200)

            self.assertTrue(response.has_header("X-RateLimit-Limit"))
            self.assertEqual(response.get("X-RateLimit-Limit"), "1")

            self.assertTrue(response.has_header("X-RateLimit-Remaining"))
            self.assertEqual(response.get("X-RateLimit-Remaining"), "0")

            self.assertTrue(response.has_header("X-RateLimit-Reset"))
            # 86400.0 is 24 hours
            self.assertEqual(response.get("X-RateLimit-Reset"), '86400.0')

            response = self.client.get(
                reverse(
                    'bb_oauth_fhir_patient_read_or_update_or_delete',
                    kwargs={'resource_id': -20140000008325}),
                Authorization="Bearer %s" % (first_access_token))

            self.assertEqual(response.status_code, 429)
            # Assert that the proper headers are in place
            self.assertTrue(response.has_header("X-RateLimit-Limit"))
            self.assertEqual(response.get("X-RateLimit-Limit"), "1")

            self.assertTrue(response.has_header("X-RateLimit-Remaining"))
            self.assertEqual(response.get("X-RateLimit-Remaining"), "0")

            self.assertTrue(response.has_header("X-RateLimit-Reset"))
            # 86400.0 is 24 hours
            self.assertTrue(float(response.get("X-RateLimit-Reset")) < 86400.0)

            self.assertTrue(response.has_header("Retry-After"))
            self.assertEqual(response.get("Retry-After"), "86400")

            # Assert that the search endpoint is also ratelimited
            response = self.client.get(
                reverse(
                    'bb_oauth_fhir_patient_search'),
                Authorization="Bearer %s" % (first_access_token))

            self.assertEqual(response.status_code, 429)

            # Assert that another token is not rate limited
            second_access_token = self.create_token('Bob', 'Bobbington')
            self.assertFalse(second_access_token == first_access_token)

            response = self.client.get(
                reverse(
                    'bb_oauth_fhir_patient_read_or_update_or_delete',
                    kwargs={'resource_id': -20140000008325}),
                Authorization="Bearer %s" % (second_access_token))

            self.assertEqual(response.status_code, 200)


class BackendConnectionTest(BaseApiTest):

    def setUp(self):
        # create read and write capabilities
        self.read_capability = self._create_capability('Read', [])
        self.write_capability = self._create_capability('Write', [])
        self._create_capability('patient', [
            ["GET", r"\/v1\/fhir\/Patient\/\-\d+"],
            ["GET", r"\/v1\/fhir\/Patient\/\d+"],
            ["GET", "/v1/fhir/Patient"],
        ])
        self._create_capability('coverage', [
            ["GET", r"\/v1\/fhir\/Coverage\/.+"],
            ["GET", "/v1/fhir/Coverage"],
        ])
        self._create_capability('eob', [
            ["GET", r"\/v1\/fhir\/ExplanationOfBenefit\/.+"],
            ["GET", "/v1/fhir/ExplanationOfBenefit"],
        ])
        # Setup the RequestFactory
        self.client = Client()

    def test_search_request(self):
        # create the user
        first_access_token = self.create_token('John', 'Smith')

        expected_request = {
            'method': 'GET',
            'url': ("https://fhir.backend.bluebutton.hhsdevcloud.us/"
                    "v1/fhir/Patient/?_format=application%2Fjson%2Bfhir&_id=-20140000008325"),
            'headers': {
                'User-Agent': 'python-requests/2.25.1',
                'Accept-Encoding': 'gzip, deflate',
                'Accept': '*/*',
                'Connection': 'keep-alive',
                'BlueButton-OriginalQueryCounter': '1',
                'BlueButton-BeneficiaryId': 'patientId:-20140000008325',
                'BlueButton-Application': 'John_Smith_test',
                'X-Forwarded-For': '127.0.0.1',
                'keep-alive': 'timeout=120, max=10',
                'BlueButton-OriginalUrl': '/v1/fhir/Patient',
                'BlueButton-BackendCall': 'https://fhir.backend.bluebutton.hhsdevcloud.us/v1/fhir/Patient/',
            }
        }

        @all_requests
        def catchall(url, req):
            self.assertIn("https://fhir.backend.bluebutton.hhsdevcloud.us/v1/fhir/Patient/", req.url)
            self.assertIn("_format=application%2Fjson%2Bfhir", req.url)
            self.assertIn("_id=-20140000008325", req.url)
            self.assertIn("startIndex=0", req.url)
            self.assertIn("_count=5", req.url)
            self.assertNotIn("hello", req.url)
            self.assertEqual(expected_request['method'], req.method)
            self.assertDictContainsSubset(expected_request['headers'], req.headers)

            return {
                'status_code': 200,
                # TODO replace this with true backend response, this has been post proccessed
                'content': patient_response,
            }

        with HTTMock(catchall):
            response = self.client.get(
                reverse(
                    'bb_oauth_fhir_patient_search'),
                {'count': 5, 'hello': 'world'},
                Authorization="Bearer %s" % (first_access_token))

            self.assertEqual(response.status_code, 200)
            # asserts no significant transformation
            self.assertEqual(response.json()['entry'], patient_response['entry'])
            self.assertTrue(len(response.json()['link']) > 0)
            self.assertIn("_count=5", response.json()['link'][0]['url'])

    def test_search_request_unauthorized(self):
        response = self.client.get(
            reverse('bb_oauth_fhir_patient_search'),
            Authorization="Bearer bogus")

        self.assertEqual(response.status_code, 401)

    def test_search_request_not_found(self):
        # create the user
        first_access_token = self.create_token('John', 'Smith')

        expected_request = {
            'method': 'GET',
            'url': ("https://fhir.backend.bluebutton.hhsdevcloud.us/"
                    "v1/fhir/Patient/?_format=application%2Fjson%2Bfhir&_id=-20140000008325"),
            'headers': {
                'User-Agent': 'python-requests/2.25.1',
                'Accept-Encoding': 'gzip, deflate',
                'Accept': '*/*',
                'Connection': 'keep-alive',
                'BlueButton-OriginalQueryCounter': '1',
                'BlueButton-BeneficiaryId': 'patientId:-20140000008325',
                'BlueButton-Application': 'John_Smith_test',
                'X-Forwarded-For': '127.0.0.1',
                'keep-alive': 'timeout=120, max=10',
                'BlueButton-OriginalUrl': '/v1/fhir/Patient',
                'BlueButton-BackendCall': 'https://fhir.backend.bluebutton.hhsdevcloud.us/v1/fhir/Patient/',
            }
        }

        @all_requests
        def catchall(url, req):
            self.assertIn("https://fhir.backend.bluebutton.hhsdevcloud.us/v1/fhir/Patient/", req.url)
            self.assertIn("_format=application%2Fjson%2Bfhir", req.url)
            self.assertIn("_id=-20140000008325", req.url)
            self.assertEqual(expected_request['method'], req.method)
            self.assertDictContainsSubset(expected_request['headers'], req.headers)

            return {
                'status_code': 404,
                'content': {},
            }

        with HTTMock(catchall):
            response = self.client.get(
                reverse('bb_oauth_fhir_patient_search'),
                Authorization="Bearer %s" % (first_access_token))

            self.assertEqual(response.status_code, 404)

    def test_search_emptyset(self):
        # create the user
        first_access_token = self.create_token('John', 'Smith')

        @all_requests
        def catchall(url, req):
            return {
                'status_code': 200,
                'content': {
                    "resourceType": "Bundle",
                    "id": "4b74b5b0-f324-41cb-85db-f8d527f79128",
                    "meta": {
                        "lastUpdated": "2018-05-15T14:01:58.603+00:00"
                    },
                    "type": "searchset",
                    "total": 0,
                    "link": [
                        {
                            "relation": "self",
                            "url": "http://hapi.fhir.org/v1/fhir/ExplanationOfBenefit?_pretty=true&patient=1234"
                        },
                    ],
                },
            }

        with HTTMock(catchall):
            response = self.client.get(
                reverse('bb_oauth_fhir_eob_search'),
                Authorization="Bearer %s" % (first_access_token))

            self.assertEqual(response.status_code, 200)

    def test_search_request_failed(self):
        # create the user
        first_access_token = self.create_token('John', 'Smith')

        expected_request = {
            'method': 'GET',
            'url': ("https://fhir.backend.bluebutton.hhsdevcloud.us/"
                    "v1/fhir/Patient/?_format=application%2Fjson%2Bfhir&_id=-20140000008325"),
            'headers': {
                'User-Agent': 'python-requests/2.25.1',
                'Accept-Encoding': 'gzip, deflate',
                'Accept': '*/*',
                'Connection': 'keep-alive',
                'BlueButton-OriginalQueryCounter': '1',
                'BlueButton-BeneficiaryId': 'patientId:-20140000008325',
                'BlueButton-Application': 'John_Smith_test',
                'X-Forwarded-For': '127.0.0.1',
                'keep-alive': 'timeout=120, max=10',
                'BlueButton-OriginalUrl': '/v1/fhir/Patient',
                'BlueButton-BackendCall': 'https://fhir.backend.bluebutton.hhsdevcloud.us/v1/fhir/Patient/',
            }
        }

        @all_requests
        def catchall(url, req):
            self.assertIn("https://fhir.backend.bluebutton.hhsdevcloud.us/v1/fhir/Patient/", req.url)
            self.assertIn("_format=application%2Fjson%2Bfhir", req.url)
            self.assertIn("_id=-20140000008325", req.url)
            self.assertEqual(expected_request['method'], req.method)
            self.assertDictContainsSubset(expected_request['headers'], req.headers)

            return {
                'status_code': 500,
                'content': {},
            }

        with HTTMock(catchall):
            response = self.client.get(
                reverse('bb_oauth_fhir_patient_search'),
                Authorization="Bearer %s" % (first_access_token))

            self.assertEqual(response.status_code, 502)

    def test_search_request_failed_no_fhir_id_match(self):
        # create the user
        first_access_token = self.create_token('John', 'Smith')

        expected_request = {
            'method': 'GET',
            'url': ("https://fhir.backend.bluebutton.hhsdevcloud.us/"
                    "v1/fhir/Patient/?_format=application%2Fjson%2Bfhir&_id=-20140000008325"),
            'headers': {
                'User-Agent': 'python-requests/2.25.1',
                'Accept-Encoding': 'gzip, deflate',
                'Accept': '*/*',
                'Connection': 'keep-alive',
                'BlueButton-OriginalQueryCounter': '1',
                'BlueButton-BeneficiaryId': 'patientId:-20140000008325',
                'BlueButton-Application': 'John_Smith_test',
                'X-Forwarded-For': '127.0.0.1',
                'keep-alive': 'timeout=120, max=10',
                'BlueButton-OriginalUrl': '/v1/fhir/Patient',
                'BlueButton-BackendCall': 'https://fhir.backend.bluebutton.hhsdevcloud.us/v1/fhir/Patient/',
            }
        }

        @urlmatch(query=r'.*identifier=http%3A%2F%2Fbluebutton.cms.hhs.gov%2Fidentifier%23hicnHash%7C139e178537ed3bc486e6a7195a47a82a2cd6f46e911660fe9775f6e0dd3f1130.*')  # noqa
        def fhir_request(url, req):
            return {
                'status_code': 200,
                'content': {
                    'total': 1,
                    'entry': [{
                        'resource': {
                            'id': -20140000008325,
                        },
                    }],
                },
            }

        @all_requests
        def catchall(url, req):
            self.assertIn("https://fhir.backend.bluebutton.hhsdevcloud.us/v1/fhir/Patient/", req.url)
            self.assertIn("_format=application%2Fjson%2Bfhir", req.url)
            self.assertIn("_id=-20140000008325", req.url)
            self.assertEqual(expected_request['method'], req.method)
            self.assertDictContainsSubset(expected_request['headers'], req.headers)

            return {
                'status_code': 500,
                'content': {},
            }

        with HTTMock(fhir_request, catchall):
            response = self.client.get(
                reverse('bb_oauth_fhir_patient_search'),
                Authorization="Bearer %s" % (first_access_token))

            self.assertEqual(response.status_code, 502)

    def test_search_parameters_request(self):
        # create the user
        first_access_token = self.create_token('John', 'Smith')

        @all_requests
        def catchall(url, req):
            self.assertIn("https://fhir.backend.bluebutton.hhsdevcloud.us/v1/fhir/ExplanationOfBenefit/", req.url)
            self.assertIn("_format=application%2Fjson%2Bfhir", req.url)

            return {
                'status_code': 200,
                'content': {
                    'resourceType': 'ExplanationOfBenefit',
                    'patient': {
                        'reference': 'stuff/-20140000008325',
                    },
                },
            }

        # Test _lastUpdated with valid parameter starting with "lt"
        with HTTMock(catchall):
            response = self.client.get(
                reverse('bb_oauth_fhir_eob_search'),
                {'_lastUpdated': 'lt2019-11-22T14:00:00-05:00'},
                Authorization="Bearer %s" % (first_access_token))
            self.assertEqual(response.status_code, 200)

        # Test _lastUpdated with invalid parameter starting with "zz"
        with HTTMock(catchall):
            response = self.client.get(
                reverse('bb_oauth_fhir_eob_search'),
                {'_lastUpdated': 'zz2020-11-22T14:00:00-05:00'},
                Authorization="Bearer %s" % (first_access_token))

            content = json.loads(response.content.decode("utf-8"))
            self.assertEqual(content['detail'], 'the _lastUpdated operator is not valid')
            self.assertEqual(response.status_code, 400)

        # Test type= with single valid value: "pde"
        with HTTMock(catchall):
            response = self.client.get(
                reverse(
                    'bb_oauth_fhir_eob_search'),
                {'type': 'pde'},
                Authorization="Bearer %s" % (first_access_token))
            self.assertEqual(response.status_code, 200)

        # Test type= with multiple (all valid values)
        with HTTMock(catchall):
            response = self.client.get(
                reverse('bb_oauth_fhir_eob_search'),
                {'type': 'carrier,'
                         'pde,'
                         'dme,'
                         'hha,'
                         'hospice,'
                         'inpatient,'
                         'outpatient,'
                         'snf,'
                         'https://bluebutton.cms.gov/resources/codesystem/eob-type|carrier,'
                         'https://bluebutton.cms.gov/resources/codesystem/eob-type|pde,'
                         'https://bluebutton.cms.gov/resources/codesystem/eob-type|dme,'
                         'https://bluebutton.cms.gov/resources/codesystem/eob-type|hha,'
                         'https://bluebutton.cms.gov/resources/codesystem/eob-type|hospice,'
                         'https://bluebutton.cms.gov/resources/codesystem/eob-type|inpatient,'
                         'https://bluebutton.cms.gov/resources/codesystem/eob-type|outpatient,'
                         'https://bluebutton.cms.gov/resources/codesystem/eob-type|snf'},
                Authorization="Bearer %s" % (first_access_token))
            self.assertEqual(response.status_code, 200)

        # Test type= with an invalid type
        with HTTMock(catchall):
            response = self.client.get(
                reverse('bb_oauth_fhir_eob_search'),
                {'type': 'carrier,'
                         'INVALID-TYPE,'
                         'dme,'},
                Authorization="Bearer %s" % (first_access_token))

            content = json.loads(response.content.decode("utf-8"))
            self.assertEqual(content['detail'], 'the type parameter value is not valid')
            self.assertEqual(response.status_code, 400)

    def test_read_request_failed_no_fhir_id(self):
        # create the user
        first_access_token = self.create_token('John', 'Smith')

        @urlmatch(query=r'.*identifier=http%3A%2F%2Fbluebutton.cms.hhs.gov%2Fidentifier%23hicnHash%7C139e178537ed3bc486e6a7195a47a82a2cd6f46e911660fe9775f6e0dd3f1130.*')  # noqa
        def fhir_request(url, req):
            return {
                'status_code': 200,
                'content': {
                    'total': 1,
                    'entry': [{
                        'resource': {
                            'id': 20140000008324,
                        },
                    }],
                },
            }

        @all_requests
        def catchall(url, req):
            return {
                'status_code': 200,
                'content': {},
            }

        with HTTMock(fhir_request, catchall):
            response = self.client.get(
                reverse(
                    'bb_oauth_fhir_patient_read_or_update_or_delete',
                    kwargs={'resource_id': '-20140000008325'}),
                Authorization="Bearer %s" % (first_access_token))

            self.assertEqual(response.status_code, 403)

    def test_read_request(self):
        # create the user
        first_access_token = self.create_token('John', 'Smith')

        expected_request = {
            'method': 'GET',
            'url': 'https://fhir.backend.bluebutton.hhsdevcloud.us/v1/fhir/Patient/-20140000008325/?_format=json',
            'headers': {
                'User-Agent': 'python-requests/2.25.1',
                'Accept-Encoding': 'gzip, deflate',
                'Accept': '*/*',
                'Connection': 'keep-alive',
                'BlueButton-OriginalQueryCounter': '1',
                'BlueButton-BeneficiaryId': 'patientId:-20140000008325',
                'BlueButton-Application': 'John_Smith_test',
                'X-Forwarded-For': '127.0.0.1',
                'keep-alive': 'timeout=120, max=10',
                'BlueButton-OriginalUrl': '/v1/fhir/Patient/-20140000008325',
                'BlueButton-BackendCall': 'https://fhir.backend.bluebutton.hhsdevcloud.us/v1/fhir/Patient/-20140000008325/',
            }
        }

        @all_requests
        def catchall(url, req):
            self.assertEqual(expected_request['url'], req.url)
            self.assertEqual(expected_request['method'], req.method)
            self.assertDictContainsSubset(expected_request['headers'], req.headers)

            return {
                'status_code': 200,
                'content':{"resourceType":"Patient","id":"-20140000008325","extension":[{"url":"https://bluebutton.cms.gov/resources/variables/race","valueCoding":{"system":"https://bluebutton.cms.gov/resources/variables/race","code":"1","display":"White"}}],"identifier":[{"system":"https://bluebutton.cms.gov/resources/variables/bene_id","value":"-20140000008325"},{"system":"https://bluebutton.cms.gov/resources/identifier/hicn-hash","value":"2025fbc612a884853f0c245e686780bf748e5652360ecd7430575491f4e018c5"}],"name":[{"use":"usual","family":"Doe","given":["Jane","X"]}],"gender":"unknown","birthDate":"2014-06-01","address":[{"district":"999","state":"15","postalCode":"99999"}]} # noqa
            }

        with HTTMock(catchall):
            response = self.client.get(
                reverse(
                    'bb_oauth_fhir_patient_read_or_update_or_delete',
                    kwargs={'resource_id': '-20140000008325'}),
                {'hello': 'world'},
                Authorization="Bearer %s" % (first_access_token))

            self.assertEqual(response.status_code, 200)

    def test_read_eob_request(self):
        # create the user
        first_access_token = self.create_token('John', 'Smith')

        @all_requests
        def catchall(url, req):
            return {
                'status_code': 200,
                'content': {
                    'resourceType': 'ExplanationOfBenefit',
                    'patient': {
                        'reference': 'stuff/-20140000008325',
                    },
                },
            }

        with HTTMock(catchall):
            response = self.client.get(
                reverse(
                    'bb_oauth_fhir_eob_read_or_update_or_delete',
                    kwargs={'resource_id': 'eob_id'}),
                Authorization="Bearer %s" % (first_access_token))

            self.assertEqual(response.status_code, 200)

    def test_read_coverage_request(self):
        # create the user
        first_access_token = self.create_token('John', 'Smith')

        @all_requests
        def catchall(url, req):
            return {
                'status_code': 200,
                'content': {
                    'resourceType': 'Coverage',
                    'beneficiary': {
                        'reference': 'stuff/-20140000008325',
                    },
                },
            }

        with HTTMock(catchall):
            response = self.client.get(
                reverse(
                    'bb_oauth_fhir_coverage_read_or_update_or_delete',
                    kwargs={'resource_id': 'coverage_id'}),
                Authorization="Bearer %s" % (first_access_token))

            self.assertEqual(response.status_code, 200)

    def test_application_first_last_active(self):
        # create the user
        first_access_token = self.create_token('John', 'Smith')

        access_token_obj = AccessToken.objects.get(token=first_access_token)
        application = access_token_obj.application

        # Check that application last_active and first_active are not set (= None)
        self.assertEqual(application.first_active, None)
        self.assertEqual(application.last_active, None)

        @all_requests
        def catchall(url, req):
            return {
                'status_code': 200,
                'content': {
                    'resourceType': 'Coverage',
                    'beneficiary': {
                        'reference': 'stuff/-20140000008325',
                    },
                },
            }

        with HTTMock(catchall):
            response = self.client.get(
                reverse(
                    'bb_oauth_fhir_coverage_read_or_update_or_delete',
                    kwargs={'resource_id': 'coverage_id'}),
                Authorization="Bearer %s" % (first_access_token))

            self.assertEqual(response.status_code, 200)

        access_token_obj = AccessToken.objects.get(token=first_access_token)
        application = access_token_obj.application

        # Check that application last_active and first_active are set
        self.assertNotEqual(application.first_active, None)
        self.assertNotEqual(application.last_active, None)

        prev_first_active = application.first_active
        prev_last_active = application.last_active

        # 2nd resource call
        @all_requests
        def catchall(url, req):
            return {
                'status_code': 200,
                'content': {
                    'resourceType': 'Coverage',
                    'beneficiary': {
                        'reference': 'stuff/-20140000008325',
                    },
                },
            }

        with HTTMock(catchall):
            response = self.client.get(
                reverse(
                    'bb_oauth_fhir_coverage_read_or_update_or_delete',
                    kwargs={'resource_id': 'coverage_id'}),
                Authorization="Bearer %s" % (first_access_token))

            self.assertEqual(response.status_code, 200)

        access_token_obj = AccessToken.objects.get(token=first_access_token)
        application = access_token_obj.application

        # Check that application first_active is the same
        self.assertEqual(application.first_active, prev_first_active)
        # Check that application last_active was updated
        self.assertNotEqual(application.last_active, prev_last_active)

    def test_permission_deny_fhir_request_on_disabled_app_org(self):
        # create the user
        first_access_token = self.create_token('John', 'Smith')

        access_token_obj = AccessToken.objects.get(token=first_access_token)
        application = access_token_obj.application
        user = access_token_obj.user

        application.active = False
        application.save()

        self.assertEqual(application.active, False)
        self.assertEqual(user.is_active, True)

        @all_requests
        def catchall(url, req):
            return {
                'status_code': 200,
                'content': {
                    'resourceType': 'Coverage',
                    'beneficiary': {
                        'reference': 'stuff/-20140000008325',
                    },
                },
            }

        with HTTMock(catchall):
            response = self.client.get(
                reverse(
                    'bb_oauth_fhir_coverage_read_or_update_or_delete',
                    kwargs={'resource_id': 'coverage_id'}),
                Authorization="Bearer %s" % (first_access_token))
            self.assertEqual(response.status_code, 403)
            errStr = str(response.json().get("detail"))
            errwords = errStr.split()
            packedErrStr = "-".join(errwords)
            msgwords = settings.APPLICATION_TEMPORARILY_INACTIVE.split()
            packedMsg = "-".join(msgwords)
            self.assertEqual(packedErrStr, packedMsg.format(application.name))

        # 2nd resource call
        @all_requests
        def catchall(url, req):
            return {
                'status_code': 200,
                'content': {
                    'resourceType': 'Coverage',
                    'beneficiary': {
                        'reference': 'stuff/-20140000008325',
                    },
                },
            }

        with HTTMock(catchall):
            response = self.client.get(
                reverse(
                    'bb_oauth_fhir_coverage_read_or_update_or_delete',
                    kwargs={'resource_id': 'coverage_id'}),
                Authorization="Bearer %s" % (first_access_token))
            self.assertEqual(response.status_code, 403)
            errStr = str(response.json().get("detail"))
            errwords = errStr.split()
            packedErrStr = "-".join(errwords)
            msgwords = settings.APPLICATION_TEMPORARILY_INACTIVE.split()
            packedMsg = "-".join(msgwords)
            self.assertEqual(packedErrStr, packedMsg.format(application.name))
        # set app user back to active - not to affect subsequent tests
        application.active = True
        application.save()
