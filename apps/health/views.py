import logging
from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import APIException
from rest_framework.views import APIView
from rest_framework.response import Response
from .checks import (
    internal_services,
    external_services,
)

logger = logging.getLogger('hhs_server.%s' % __name__)


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'Service temporarily unavailable, try again later.'
    default_code = 'service_unavailable'


class Check(APIView):

    def get(self, request, format=None):
        try:
            for check in self.get_services():
                v2 = True if request.path.endswith('external_v2') else False
                if not check(v2):
                    raise ServiceUnavailable()
        except ServiceUnavailable:
            raise
        except Exception as e:
            logger.exception("health check raised exception. {reason}".format(reason=e))
            raise ServiceUnavailable(detail="Service temporarily unavailable, try again later. There is an issue with the - {svc}"
                                            " - service check. Reason: {reason}".format(svc=check.__name__, reason=e))
        return Response({'message': 'all\'s well'})

    def get_services(self):
        if not hasattr(self, "services"):
            raise ImproperlyConfigured
        if len(self.services) < 1:
            raise ImproperlyConfigured(
                "please specify at least one service to check")
        return self.services


class CheckInternal(Check):
    services = internal_services


class CheckExternal(Check):
    services = external_services
