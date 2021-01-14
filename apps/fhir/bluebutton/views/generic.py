import logging
import voluptuous
import waffle
from requests import Session, Request
from rest_framework import (exceptions, permissions)
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.fhir.parsers import FHIRParser
from apps.fhir.renderers import FHIRRenderer
from apps.dot_ext.throttling import TokenRateThrottle
from apps.fhir.server import connection as backend_connection
from ..signals import (
    pre_fetch,
    post_fetch
)
from apps.authorization.permissions import DataAccessGrantPermission
from ..authentication import OAuth2ResourceOwner
from ..permissions import (HasCrosswalk, ResourcePermission, ApplicationActivePermission)
from ..exceptions import process_error_response
from ..utils import (build_fhir_response,
                     FhirServerVerify,
                     get_resourcerouter)

logger = logging.getLogger('hhs_server.%s' % __name__)


class FhirDataView(APIView):

    parser_classes = [JSONParser, FHIRParser]
    renderer_classes = [JSONRenderer, FHIRRenderer]
    throttle_classes = [TokenRateThrottle]
    authentication_classes = [OAuth2ResourceOwner]
    # BB2-149 note, check authenticated first, then app active etc.
    permission_classes = [
        permissions.IsAuthenticated,
        ApplicationActivePermission,
        HasCrosswalk,
        ResourcePermission,
        DataAccessGrantPermission]

    # Must return a Crosswalk
    def check_resource_permission(self, request, **kwargs):
        raise NotImplementedError()

    def build_parameters(self, request):
        raise NotImplementedError()

    def map_parameters(self, params):
        transforms = getattr(self, "QUERY_TRANSFORMS", {})
        for key, correct in transforms.items():
            val = params.pop(key, None)
            if val is not None:
                params[correct] = val
        return params

    def filter_parameters(self, request):
        params = self.map_parameters(request.query_params.dict())
        # Get list from _lastUpdated QueryDict(), since it can have multi params
        params['_lastUpdated'] = request.query_params.getlist('_lastUpdated')

        schema = voluptuous.Schema(
            getattr(self, "QUERY_SCHEMA", {}),
            extra=voluptuous.REMOVE_EXTRA)
        return schema(params)

    def validate_response(self, response):
        pass

    def initial(self, request, resource_type, *args, **kwargs):
        """
        Read from Remote FHIR Server
        # Example client use in curl:
        # curl -X GET http://127.0.0.1:8000/fhir/Patient/1234
        """

        logger.debug("resource_type: %s" % resource_type)
        logger.debug("Interaction: read")
        logger.debug("Request.path: %s" % request.path)

        request.resource_type = resource_type

        super(FhirDataView, self).initial(request, *args, **kwargs)

    def get(self, request, resource_type, *args, **kwargs):

        out_data = self.fetch_data(request, resource_type, *args, **kwargs)

        return Response(out_data)

    def fetch_data(self, request, resource_type, *args, **kwargs):
        resource_router = get_resourcerouter(request.crosswalk)
        api_ver = 'v2' if request.path.startswith("/v2") else 'v1'
        # BB2-291 v2 switch enforced here, entry of all fhir resources queries
        if request.path.startswith("/v2"):
            if (not waffle.switch_is_active('bfd_v2')):
                raise exceptions.NotFound("bfd_v2 disabled.")
            if (not waffle.flag_is_active(request, 'bfd_v2_flag')):
                raise exceptions.NotFound("bfd_v2_flag not active.")

        target_url = self.build_url(resource_router,
                                    resource_type,
                                    *args,
                                    **dict(kwargs, ver=api_ver))

        logger.debug('FHIR URL with key:%s' % target_url)

        try:
            get_parameters = {**self.filter_parameters(request), **self.build_parameters(request)}
        except voluptuous.error.Invalid as e:
            raise exceptions.ParseError(detail=e.msg)

        logger.debug('Here is the URL to send, %s now add '
                     'GET parameters %s' % (target_url, get_parameters))

        # Now make the call to the backend API
        req = Request('GET',
                      target_url,
                      data=get_parameters,
                      params=get_parameters,
                      headers=backend_connection.headers(request, url=target_url))
        s = Session()
        prepped = s.prepare_request(req)
        # Send signal
        pre_fetch.send_robust(FhirDataView, request=req, api_ver=api_ver)
        r = s.send(
            prepped,
            cert=backend_connection.certs(crosswalk=request.crosswalk),
            timeout=resource_router.wait_time,
            verify=FhirServerVerify(crosswalk=request.crosswalk))
        # Send signal
        post_fetch.send_robust(FhirDataView, request=prepped, response=r, api_ver=api_ver)
        response = build_fhir_response(request._request, target_url, request.crosswalk, r=r, e=None)

        # BB2-128
        error = process_error_response(response)

        if error is not None:
            raise error

        self.validate_response(response)

        out_data = r.json()

        self.check_object_permissions(request, out_data)

        return out_data
