import logging
import requests
import waffle

from django.db import connection

from apps.fhir.bluebutton.utils import get_resourcerouter
from apps.fhir.server import connection as backend_connection
from apps.mymedicare_cb.authorization import OAuth2ConfigSLSx


logger = logging.getLogger('hhs_server.%s' % __name__)


def django_rds_database():
    connection.ensure_connection()
    return connection.is_usable()


def bfd_fhir_dataserver(v2=False):
    resource_router = get_resourcerouter()
    target_url = "{}{}".format(resource_router.fhir_url, "/v2/fhir/metadata" if v2 else "/v1/fhir/metadata")
    r = requests.get(target_url,
                     params={"_format": "json"},
                     cert=backend_connection.certs(),
                     verify=False)
    try:
        r.raise_for_status()
    except Exception:
        logger.exception("Failed to ping backend")
        return False
    return r.json()


def slsx():
    # SLS vs. SLSx flow based on feature switch slsx-enable (true = SLSx / false = SLS)
    # TODO: Remove switch logic after migration to SLSx
    if waffle.switch_is_active('slsx-enable'):
        # Perform health check on SLSx service
        slsx_client = OAuth2ConfigSLSx()
        try:
            slsx_client.service_health_check()
        except requests.exceptions.HTTPError as e:
            return "SLSx service health check error {reason}".format(reason=e).json()
    return True


internal_services = (
    django_rds_database,
)

external_services = (
    bfd_fhir_dataserver,
    slsx,
)
