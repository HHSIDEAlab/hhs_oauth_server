import logging

from voluptuous import (
    Required,
    All,
    Match,
    Range,
    Coerce,
)
from rest_framework import (permissions)

from apps.fhir.bluebutton.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from apps.fhir.bluebutton.views.generic import FhirDataView
from apps.authorization.permissions import DataAccessGrantPermission
from apps.capabilities.permissions import TokenHasProtectedCapability
from ..permissions import (SearchCrosswalkPermission, ResourcePermission, ApplicationActivePermission)

logger = logging.getLogger('hhs_server.%s' % __name__)


class SearchView(FhirDataView):
    # Base class for FHIR resource search views

    # BB2-149 note, check authenticated first, then app active etc.
    permission_classes = [
        permissions.IsAuthenticated,
        ApplicationActivePermission,
        ResourcePermission,
        SearchCrosswalkPermission,
        DataAccessGrantPermission,
        TokenHasProtectedCapability,
    ]

    # Regex to match a valid _lastUpdated value that can begin with lt, le, gt and ge operators
    REGEX_LASTUPDATED_VALUE = r'^((lt)|(le)|(gt)|(ge)).+'

    QUERY_TRANSFORMS = {
        'count': '_count',
    }

    QUERY_SCHEMA = {
        Required('startIndex', default=0): Coerce(int),
        Required('_count', default=DEFAULT_PAGE_SIZE): All(Coerce(int), Range(min=0, max=MAX_PAGE_SIZE)),
        '_lastUpdated': [Match(REGEX_LASTUPDATED_VALUE, msg="the _lastUpdated operator is not valid")]
    }

    def __init__(self):
        self.resource_type = None

    def initial(self, request, *args, **kwargs):
        return super().initial(request, self.resource_type, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return super().get(request, self.resource_type, *args, **kwargs)

    def build_url(self, resource_router, resource_type, *args, **kwargs):
        api_ver = kwargs.get('ver')
        if resource_router.fhir_url.endswith('v1/fhir/'):
            # only if called by tests
            return "{}{}/".format(resource_router.fhir_url, resource_type)
        else:
            return "{}/{}/fhir/{}/".format(resource_router.fhir_url, api_ver,
                                           resource_type)


class SearchViewPatient(SearchView):
    # Class used for Patient resource search view

    def __init__(self):
        self.resource_type = "Patient"

    def build_parameters(self, request, *args, **kwargs):
        return {
            '_format': 'application/json+fhir',
            '_id': request.crosswalk.fhir_id,
        }


class SearchViewCoverage(SearchView):
    # Class used for Coverage resource search view

    def __init__(self):
        self.resource_type = "Coverage"

    def build_parameters(self, request, *args, **kwargs):
        return {
            '_format': 'application/json+fhir',
            'beneficiary': 'Patient/' + request.crosswalk.fhir_id,
        }


class SearchViewExplanationOfBenefit(SearchView):
    # Class used for ExplanationOfBenefit resource search view

    # Regex to match a valid type value
    REGEX_TYPE_VALUE = r"(carrier)|" + \
        r"(pde)|" + \
        r"(dme)|" + \
        r"(hha)|" + \
        r"(hospice)|" + \
        r"(inpatient)|" + \
        r"(outpatient)|" + \
        r"(snf)|" + \
        r"(https://bluebutton.cms.gov/resources/codesystem/eob-type\|)|" + \
        r"(https://bluebutton.cms.gov/resources/codesystem/eob-type\|carrier)|" + \
        r"(https://bluebutton.cms.gov/resources/codesystem/eob-type\|pde)|" + \
        r"(https://bluebutton.cms.gov/resources/codesystem/eob-type\|dme)|" + \
        r"(https://bluebutton.cms.gov/resources/codesystem/eob-type\|hha)|" + \
        r"(https://bluebutton.cms.gov/resources/codesystem/eob-type\|hospice)|" + \
        r"(https://bluebutton.cms.gov/resources/codesystem/eob-type\|inpatient)|" + \
        r"(https://bluebutton.cms.gov/resources/codesystem/eob-type\|outpatient)|" + \
        r"(https://bluebutton.cms.gov/resources/codesystem/eob-type\|snf)"

    # Regex to match a list of comma separated type values with IGNORECASE
    REGEX_TYPE_VALUES_LIST = r'(?i)^((' + REGEX_TYPE_VALUE + r')\s*,*\s*)+$'

    # Add type parameter to schema only for EOB
    QUERY_SCHEMA = {**SearchView.QUERY_SCHEMA,
                    'type': Match(REGEX_TYPE_VALUES_LIST, msg="the type parameter value is not valid")}

    def __init__(self):
        self.resource_type = "ExplanationOfBenefit"

    def build_parameters(self, request, *args, **kwargs):
        return {
            '_format': 'application/json+fhir',
            'patient': request.crosswalk.fhir_id,
        }
