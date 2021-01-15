import re
import json
from django.urls import reverse
from django.test.client import Client
from django.contrib.auth.models import Group
from httmock import all_requests, HTTMock, urlmatch
from waffle.testutils import override_switch, override_flag

from apps.dot_ext.models import Application
from apps.test import BaseApiTest
from apps.mymedicare_cb.views import generate_nonce
from apps.mymedicare_cb.models import AnonUserState
from apps.mymedicare_cb.tests.responses import patient_response

loggers = [
    'audit.authorization.token',
    'audit.authorization.sls',
    'audit.data.fhir',
    'audit.authenticate.sls',
    'audit.authenticate.mymedicare_cb',
    'audit.authenticate.match_fhir_id',
    'audit.hhs_oauth_server.request_logging'
]


class HTTMockWithResponseHook(HTTMock):

    def intercept(self, request, **kwargs):
        response = super().intercept(request, **kwargs)
        # process hooks - we only have response hook for now
        self.dispatch_hook("response", request.hooks, response, **kwargs)
        return response

    def dispatch_hook(self, key, hooks, hook_data, **kwargs):
        """Dispatches a hook dictionary on a given piece of data."""
        hooks = hooks or {}
        hooks = hooks.get(key)
        if hooks:
            if hasattr(hooks, '__call__'):
                hooks = [hooks]
            for hook in hooks:
                _hook_data = hook(hook_data, **kwargs)
                if _hook_data is not None:
                    hook_data = _hook_data
        return hook_data


class TestAuditEventLoggers(BaseApiTest):

    def setUp(self):
        Group.objects.create(name='BlueButton')
        self.callback_url = reverse('mymedicare-sls-callback')
        self.callback_url_v2 = reverse('mymedicare-sls-callback-v2')
        self.read_capability = self._create_capability('Read', [])
        self.write_capability = self._create_capability('Write', [])
        self._create_capability('patient', [
            ["GET", r"\/v1\/fhir\/Patient\/\-\d+"],
            ["GET", "/v1/fhir/Patient"],
            ["GET", r"\/v2\/fhir\/Patient\/\-\d+"],
            ["GET", "/v2/fhir/Patient"],
        ])
        # Setup the RequestFactory
        self.client = Client()
        self._redirect_loggers(loggers)

    def tearDown(self):
        self._cleanup_logger()

    def get_log_content(self, logger_name):
        return self._collect_logs(loggers).get(logger_name)

    def test_fhir_events_logging(self):
        self._fhir_events_logging(False)

    @override_switch('bfd_v2', active=True)
    @override_flag('bfd_v2_flag', active=True)
    def test_fhir_events_logging_v2(self):
        self._fhir_events_logging(True)

    def _fhir_events_logging(self, v2=False):
        first_access_token = self.create_token('John', 'Smith')
        api_ver = 'v1' if not v2 else 'v2'

        @all_requests
        def catchall(url, req):
            fhir_log_content = self.get_log_content('audit.data.fhir')
            self.assertIsNotNone(fhir_log_content)

            log_entry_dict = json.loads(fhir_log_content)
            compare_dict = {'api_ver': api_ver,
                            'application': {'id': '1', 'name': 'John_Smith_test', 'user': {'id': '1'}},
                            'fhir_id': '-20140000008325',
                            'includeAddressFields': 'False',
                            'path': '/{}/fhir/Patient'.format(api_ver),
                            'type': 'fhir_pre_fetch',
                            'user': 'patientId:-20140000008325'}
            self.assert_log_entry_valid(log_entry_dict, compare_dict, ['start_time', 'uuid'], None)

            return {
                'status_code': 200,
                # TODO replace this with true backend response, this has been post proccessed
                'content': patient_response,
            }

        with HTTMock(catchall):
            self.client.get(
                reverse('bb_oauth_fhir_patient_search' if not v2 else 'bb_oauth_fhir_patient_search_v2'),
                {'count': 5, 'hello': 'world'},
                Authorization="Bearer %s" % (first_access_token))

            # fhir_log_content, token_log_content
            # check fhir log content
            fhir_log_content = self.get_log_content('audit.data.fhir')
            self.assertIsNotNone(fhir_log_content)
            log_entries = fhir_log_content.splitlines()

            # Validate fhir_pre_fetch entry
            log_entry_dict = json.loads(log_entries[0])
            compare_dict = {'api_ver': api_ver,
                            'application': {'id': '1', 'name': 'John_Smith_test', 'user': {'id': '1'}},
                            'fhir_id': '-20140000008325',
                            'includeAddressFields': 'False',
                            'path': '/{}/fhir/Patient'.format(api_ver),
                            'type': 'fhir_pre_fetch',
                            'user': 'patientId:-20140000008325'}
            self.assert_log_entry_valid(log_entry_dict, compare_dict, ['start_time', 'uuid'], None)

            # Validate fhir_post_fetch entry
            log_entry_dict = json.loads(log_entries[1])
            compare_dict = {'api_ver': api_ver,
                            'application': {'id': '1', 'name': 'John_Smith_test', 'user': {'id': '1'}},
                            'code': 200,
                            'fhir_id': '-20140000008325',
                            'includeAddressFields': 'False',
                            'path': '/{}/fhir/Patient'.format(api_ver),
                            'size': 1270,
                            'type': 'fhir_post_fetch',
                            'user': 'patientId:-20140000008325'}
            self.assert_log_entry_valid(log_entry_dict, compare_dict, ['start_time', 'uuid', 'elapsed'], None)

            # Validate AccessToken entry
            token_log_content = self.get_log_content('audit.authorization.token')
            self.assertIsNotNone(token_log_content)
            log_entries = token_log_content.splitlines()

            log_entry_dict = json.loads(log_entries[0])
            compare_dict = {'action': 'authorized',
                            'application': {'id': 1,
                                            'name': 'John_Smith_test',
                                            'user': {'id': 1, 'username': 'John'}},
                            'auth_grant_type': 'password',
                            'id': 1,
                            'scopes': 'read write patient',
                            'type': 'AccessToken',
                            'user': {'id': 1, 'username': 'John'}}
            self.assert_log_entry_valid(log_entry_dict, compare_dict, ['access_token'], None)

    def test_callback_url_success_sls_logger(self):
        self._callback_url_success_sls_logger(False)

    @override_switch('bfd_v2', active=True)
    @override_flag('bfd_v2_flag', active=True)
    def test_callback_url_success_sls_logger_v2(self):
        self._callback_url_success_sls_logger(True)

    def _callback_url_success_sls_logger(self, v2=False):
        # copy and adapted for SLS logger test
        state = generate_nonce()
        AnonUserState.objects.create(
            state=state,
            next_uri="http://www.google.com?client_id=test&redirect_uri=test.com&response_type=token&state=test")
        # mock sls token endpoint
        api_ver = 'v1' if not v2 else 'v2'

        # mock sls token endpoint (not api versioned, and for test it is hardcoded as '/v1/oauth/token')
        @urlmatch(netloc='dev.accounts.cms.gov', path='/v1/oauth/token')
        def sls_token_mock(url, request):
            return {
                'status_code': 200,
                'content': {'access_token': 'works'},
            }

        # mock sls user info endpoint (not api versioned, and for test it is hardcoded as '/v1/oauth/userinfo')
        @urlmatch(netloc='dev.accounts.cms.gov', path='/v1/oauth/userinfo')
        def sls_user_info_mock(url, request):
            return {
                'status_code': 200,
                'content': {
                    'sub': '00112233-4455-6677-8899-aabbccddeeff',
                    'given_name': '',
                    'family_name': '',
                    'email': 'bob@bobserver.bob',
                    'hicn': '1234567890A',
                    'mbi': '1SA0A00AA00',
                },
            }

        # mock fhir user info endpoint
        @urlmatch(netloc='fhir.backend.bluebutton.hhsdevcloud.us',
                  path='/{}/fhir/Patient/'.format(api_ver))
        def fhir_patient_info_mock(url, request):
            return {
                'status_code': 200,
                'content': patient_response,
            }

        @all_requests
        def catchall(url, request):
            raise Exception(url)

        with HTTMockWithResponseHook(sls_token_mock,
                                     sls_user_info_mock,
                                     fhir_patient_info_mock,
                                     catchall):
            s = self.client.session
            s.update({"auth_uuid": "84b4afdc-d85d-4ea4-b44c-7bde77634429",
                      "auth_app_id": "2",
                      "auth_app_name": "TestApp-001",
                      "auth_client_id": "uouIr1mnblrv3z0PJHgmeHiYQmGVgmk5DZPDNfop"})
            s.save()
            self.client.get(self.callback_url if not v2 else self.callback_url_v2, data={'code': 'test', 'state': state})

            sls_log_content = self.get_log_content('audit.authorization.sls')

            quoted_strings = re.findall("{[^{}]+}", sls_log_content)
            self.assertEqual(len(quoted_strings), 2)
            sls_token_dict = json.loads(quoted_strings[0])
            compare_dict = {
                'code': 200,
                'path': '/v1/oauth/token',
                'type': 'SLS_token'
            }
            remove_list = [
                'size',
                'elapsed',
                'start_time',
                'access_token',
                'uuid'
            ]
            hasvalue_list = [
                'access_token',
                'uuid'
            ]
            self.assert_log_entry_valid(sls_token_dict, compare_dict, remove_list, hasvalue_list)

            sls_userinfo_dict = json.loads(quoted_strings[1])
            compare_dict = {
                'code': 200,
                'path': '/v1/oauth/userinfo',
                'sub': '00112233-4455-6677-8899-aabbccddeeff',
                'type': 'SLS_userinfo',
            }
            remove_list = [
                'elapsed',
                'size',
                'start_time',
                'uuid'
            ]
            hasvalue_list = [
                'uuid'
            ]
            self.assert_log_entry_valid(sls_userinfo_dict, compare_dict, remove_list, hasvalue_list)

            authn_sls_log_content = self.get_log_content('audit.authenticate.sls')
            log_entries = authn_sls_log_content.splitlines()
            self.assertEqual(len(log_entries), 2)
            # Authentication:start
            log_entry_dict = json.loads(log_entries[0])
            compare_dict = {
                'sls_mbi_format_msg': 'Valid',
                'sls_mbi_format_synthetic': True,
                'sls_mbi_format_valid': True,
                'sls_status': 'OK',
                'sls_status_mesg': None,
                'sub': '00112233-4455-6677-8899-aabbccddeeff',
                'type': 'Authentication:start'
            }
            remove_list = [
                'sls_hicn_hash',
                'sls_mbi_hash'
            ]
            hasvalue_list = [
                'sls_hicn_hash',
                'sls_mbi_hash'
            ]
            self.assert_log_entry_valid(log_entry_dict, compare_dict, remove_list, hasvalue_list)
            log_entry_dict = json.loads(log_entries[1])
            compare_dict = {
                'auth_crosswalk_action': 'C',
                'sub': '00112233-4455-6677-8899-aabbccddeeff',
                'type': 'Authentication:success',
            }
            remove_list = [
                'user'
            ]
            hasvalue_list = [
                'user'
            ]
            self.assert_log_entry_valid(log_entry_dict, compare_dict, remove_list, hasvalue_list)

            mymedicare_cb_log_content = self.get_log_content('audit.authenticate.mymedicare_cb')
            log_entries = mymedicare_cb_log_content.splitlines()
            self.assertEqual(len(log_entries), 2)
            # mymedicare_cb:create_beneficiary_record
            log_entry_dict = json.loads(log_entries[0])

            compare_dict = {
                'fhir_id': '-20140000008325',
                'mesg': 'CREATE beneficiary record',
                'status': 'OK',
                'type': 'mymedicare_cb:create_beneficiary_record',
                'username': '00112233-4455-6677-8899-aabbccddeeff'
            }
            remove_list = [
                'user_hicn_hash',
                'user_mbi_hash'
            ]
            hasvalue_list = [
                'user_hicn_hash',
                'user_mbi_hash'
            ]
            self.assert_log_entry_valid(log_entry_dict, compare_dict, remove_list, hasvalue_list)

            # mymedicare_cb:get_and_update_user
            log_entry_dict = json.loads(log_entries[1])

            compare_dict = {
                'fhir_id': '-20140000008325',
                'hash_lookup_type': 'M',
                'mesg': 'CREATE beneficiary record',
                'status': 'OK',
                'type': 'mymedicare_cb:get_and_update_user'
            }
            remove_list = [
                'crosswalk',
                'hicn_hash',
                'mbi_hash',
            ]
            hasvalue_list = [
                'crosswalk',
                'hicn_hash',
                'mbi_hash'
            ]
            self.assert_log_entry_valid(log_entry_dict, compare_dict, remove_list, hasvalue_list)

            fhir_log_content = self.get_log_content('audit.data.fhir')
            log_entries = fhir_log_content.splitlines()
            self.assertEqual(len(log_entries), 2)
            # fhir_auth_pre_fetch
            log_entry_dict = json.loads(log_entries[0])

            compare_dict = {
                'api_ver': api_ver,
                'includeAddressFields': 'False',
                'path': 'patient search',
                'type': 'fhir_auth_pre_fetch',
            }
            remove_list = [
                'start_time',
                'uuid'
            ]
            hasvalue_list = [
                'start_time',
                'uuid'
            ]
            self.assert_log_entry_valid(log_entry_dict, compare_dict, remove_list, hasvalue_list)

            # fhir_auth_post_fetch
            log_entry_dict = json.loads(log_entries[1])
            compare_dict = {
                'api_ver': api_ver,
                'code': 200,
                'includeAddressFields': 'False',
                'path': 'patient search',
                'type': 'fhir_auth_post_fetch',
            }
            remove_list = [
                'elapsed',
                'size',
                'start_time',
                'uuid'
            ]
            hasvalue_list = [
                'elapsed',
                'size',
                'start_time',
                'uuid'
            ]
            self.assert_log_entry_valid(log_entry_dict, compare_dict, remove_list, hasvalue_list)

            match_fhir_id_log_content = self.get_log_content('audit.authenticate.match_fhir_id')
            log_entries = match_fhir_id_log_content.splitlines()
            self.assertGreater(len(log_entries), 0)
            # fhir.server.authentication.match_fhir_id
            log_entry_dict = json.loads(log_entries[0])
            compare_dict = {
                'fhir_id': '-20140000008325',
                'hash_lookup_mesg': 'FOUND beneficiary via mbi_hash',
                'hash_lookup_type': 'M',
                'match_found': True,
                'type': 'fhir.server.authentication.match_fhir_id'
            }
            remove_list = [
                'auth_app_id',
                'auth_app_name',
                'auth_client_id',
                'auth_pkce_method',
                'hicn_hash',
                'mbi_hash',
                'auth_uuid'
            ]
            hasvalue_list = [
                'hicn_hash',
                'mbi_hash'
            ]
            self.assert_log_entry_valid(log_entry_dict, compare_dict, remove_list, hasvalue_list)

            hhs_oauth_server_log_content = self.get_log_content('audit.hhs_oauth_server.request_logging')
            log_entries = hhs_oauth_server_log_content.splitlines()
            self.assertGreater(len(log_entries), 0)
            # hhs oauth server request logging
            # quote out for v2 this fld:  "auth_crosswalk_action", come back later
            log_entry_dict = json.loads(log_entries[0])
            log_flds = ["start_time", "end_time", "request_uuid",
                        "path", "response_code", "size", "location",
                        "app_name", "app_id", "dev_id", "dev_name",
                        "access_token_hash", "ip_addr",
                        "user", "fhir_id"]
            keys = log_entry_dict.keys()
            for f in log_flds:
                self.assertTrue(f in keys)

    def test_creation_on_approval_token_logger(self):
        self._creation_on_approval_token_logger(False)

    @override_switch('bfd_v2', active=True)
    @override_flag('bfd_v2_flag', active=True)
    def test_creation_on_approval_token_logger_v2(self):
        self._creation_on_approval_token_logger(True)

    def _creation_on_approval_token_logger(self, v2=False):
        # copy and adapted to test token logger
        redirect_uri = 'http://localhost'
        self._create_user('anna', '123456')
        capability_a = self._create_capability('Capability A', [])
        capability_b = self._create_capability('Capability B', [])
        application = self._create_application(
            'an app',
            grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris=redirect_uri)
        application.scope.add(capability_a, capability_b)
        api_ver = 'v1' if not v2 else 'v2'
        self.client.login(username='anna', password='123456')

        payload = {
            'client_id': application.client_id,
            'response_type': 'code',
            'redirect_uri': redirect_uri,
        }
        response = self.client.get('/{}/o/authorize'.format(api_ver), data=payload)
        payload = {
            'client_id': application.client_id,
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'scope': ['capability-a'],
            'expires_in': 86400,
            'allow': True,
        }
        response = self.client.post(response['Location'], data=payload)
        self.assertEqual(response.status_code, 302)
        # assert token logger record works by assert some top level fields
        token_log_content = self.get_log_content('audit.authorization.token')
        self.assertIsNotNone(token_log_content)
        token_log_dict = json.loads(token_log_content)
        compare_dict = {
            'allow': True,
            'auth_app_name': 'an app',
            'auth_require_demographic_scopes': 'True',
            'auth_status': 'OK',
            'scopes': 'capability-a',
            'type': 'Authorization'
        }
        remove_list = [
            'access_token_delete_cnt',
            'application',
            'auth_app_id',
            'auth_client_id',
            'auth_pkce_method',
            'auth_status_code',
            'auth_uuid',
            'auth_share_demographic_scopes',
            'data_access_grant_delete_cnt',
            'refresh_token_delete_cnt',
            'share_demographic_scopes',
            'user'
        ]
        hasvalue_list = [
            'auth_uuid',
            'user',
            'application'
        ]
        self.assert_log_entry_valid(token_log_dict, compare_dict, remove_list, hasvalue_list)
