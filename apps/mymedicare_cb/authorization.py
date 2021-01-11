import logging
import requests
import datetime

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.dot_ext.loggers import get_session_auth_flow_trace
from apps.logging.serializers import SLSTokenResponse, SLSxTokenResponse, SLSxUserInfoResponse

from .loggers import log_authenticate_start
from .signals import response_hook_wrapper

logger = logging.getLogger('hhs_server.%s' % __name__)


class BBMyMedicareSLSxTokenException(APIException):
    # BB2-391 custom exception
    status_code = status.HTTP_502_BAD_GATEWAY


class BBMyMedicareSLSxUserinfoException(APIException):
    # BB2-391 custom exception
    status_code = status.HTTP_502_BAD_GATEWAY


class OAuth2Config(object):
    def __init__(self, v2=False):
        if v2:
            self.redirect_uri = settings.MEDICARE_REDIRECT_URI_V2
        else:
            self.redirect_uri = settings.MEDICARE_REDIRECT_URI

        self.token_endpoint = settings.SLS_TOKEN_ENDPOINT
        self.verify_ssl = getattr(settings, 'SLS_VERIFY_SSL', False)
        self.token = None

    @property
    def client_id(self):
        return getattr(settings, 'SLS_CLIENT_ID', False)

    @property
    def client_secret(self):
        return getattr(settings, 'SLS_CLIENT_SECRET', False)

    def basic_auth(self):
        if self.client_id and self.client_secret:
            return (self.client_id, self.client_secret)
        return None

    def exchange(self, code, request):
        logger.debug("token_endpoint %s" % (self.token_endpoint))
        logger.debug("redirect_uri %s" % (self.redirect_uri))

        token_dict = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }

        # keep using deprecated conv - no conflict issue
        headers = {"X-SLS-starttime": str(datetime.datetime.utcnow())}
        if request is not None:
            headers.update({"X-Request-ID": str(getattr(request, '_logging_uuid', None)
                            if hasattr(request, '_logging_uuid') else '')})

        # Get auth flow trace session values dict.
        auth_flow_dict = get_session_auth_flow_trace(request)

        response = requests.post(
            self.token_endpoint,
            auth=self.basic_auth(),
            json=token_dict,
            headers=headers,
            verify=self.verify_ssl,
            hooks={
                'response': [
                    response_hook_wrapper(sender=SLSTokenResponse,
                                          auth_flow_dict=auth_flow_dict)]})
        response.raise_for_status()

        token_response = response.json()
        self.token = token_response
        return self.token['access_token']

    def auth_header(self):
        return {"Authorization": "Bearer %s" % (self.token['access_token'])}


class OAuth2ConfigSLSx(object):
    token_endpoint = settings.SLSX_TOKEN_ENDPOINT
    token_endpoint_aca_token = settings.MEDICARE_SLSX_AKAMAI_ACA_TOKEN
    redirect_uri = settings.MEDICARE_SLSX_REDIRECT_URI
    userinfo_endpoint = settings.SLSX_USERINFO_ENDPOINT
    healthcheck_endpoint = settings.SLSX_HEALTH_CHECK_ENDPOINT
    verify_ssl = getattr(settings, 'SLSX_VERIFY_SSL', False)

    @property
    def client_id(self):
        return getattr(settings, 'SLSX_CLIENT_ID', False)

    @property
    def client_secret(self):
        return getattr(settings, 'SLSX_CLIENT_SECRET', False)

    def basic_auth(self):
        if self.client_id and self.client_secret:
            return (self.client_id, self.client_secret)
        return None

    def exchange_for_access_token(self, req_token, request):
        data_dict = {
            "request_token": req_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        headers = {"Content-Type": "application/json",
                   "Cookie": self.token_endpoint_aca_token,
                   "X-SLS-starttime": str(datetime.datetime.utcnow())}

        if request is not None:
            headers.update({"X-Request-ID": str(getattr(request, '_logging_uuid', None)
                            if hasattr(request, '_logging_uuid') else '')})

        # Get auth flow trace session values dict.
        auth_flow_dict = get_session_auth_flow_trace(request)

        response = requests.post(
            self.token_endpoint,
            auth=self.basic_auth(),
            json=data_dict,
            headers=headers,
            verify=self.verify_ssl,
            hooks={
                'response': [
                    response_hook_wrapper(sender=SLSxTokenResponse,
                                          auth_flow_dict=auth_flow_dict)]})

        response.raise_for_status()

        token_response = response.json()

        auth_token = token_response.get('auth_token', None)
        if auth_token is None:
            log_authenticate_start(auth_flow_dict, "FAIL",
                                   "Exchange auth_token is missing in response error")
            raise BBMyMedicareSLSxTokenException(settings.MEDICARE_ERROR_MSG)

        user_id = token_response.get('user_id', None)
        if user_id is None:
            log_authenticate_start(auth_flow_dict, "FAIL",
                                   "Exchange user_id is missing in response error")
            raise BBMyMedicareSLSxTokenException(settings.MEDICARE_ERROR_MSG)

        return auth_token, user_id

    def auth_header(self):
        return {"Authorization": "Bearer %s" % (self.token['access_token'])}

    def get_user_info(self, access_token, user_id, request):
        headers = {"Authorization": "Bearer %s" % (access_token)}
        # keep using deprecated conv - no conflict issue
        headers.update({"X-SLS-starttime": str(datetime.datetime.utcnow())})

        if request is not None:
            headers.update({"X-Request-ID": str(getattr(request, '_logging_uuid', None)
                            if hasattr(request, '_logging_uuid') else '')})

        # Get auth flow session values.
        auth_flow_dict = get_session_auth_flow_trace(request)
        try:
            response = requests.get(self.userinfo_endpoint + "/" + user_id,
                                    headers=headers,
                                    verify=self.verify_ssl,
                                    hooks={
                                        'response': [
                                            response_hook_wrapper(sender=SLSxUserInfoResponse,
                                                                  auth_flow_dict=auth_flow_dict)]})
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            log_authenticate_start(auth_flow_dict, "FAIL",
                                   "SLSx userinfo request response error {reason}".format(reason=e))
            raise BBMyMedicareSLSxUserinfoException(settings.MEDICARE_ERROR_MSG)

        # Get data.user part of response
        try:
            data_user_response = response.json().get('data').get('user')
        except KeyError:
            log_authenticate_start(auth_flow_dict, "FAIL",
                                   "SLSx userinfo issue with data.user sub fields in response error")
            raise BBMyMedicareSLSxUserinfoException(settings.MEDICARE_ERROR_MSG)

        if data_user_response.get('id', None) is None:
            log_authenticate_start(auth_flow_dict, "FAIL",
                                   "SLSx userinfo user_id is missing in response error")
            raise BBMyMedicareSLSxUserinfoException(settings.MEDICARE_ERROR_MSG)

        if user_id != data_user_response.get('id', None):
            log_authenticate_start(auth_flow_dict, "FAIL",
                                   "SLSx userinfo user_id is not equal in response error")
            raise BBMyMedicareSLSxUserinfoException(settings.MEDICARE_ERROR_MSG)

        return data_user_response

    def service_health_check(self):
        response = requests.get(self.healthcheck_endpoint, verify=self.verify_ssl)
        response.raise_for_status()
