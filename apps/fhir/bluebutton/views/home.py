import json
import logging

from collections import OrderedDict
from urllib.parse import urlencode
from django.http import JsonResponse
from django.shortcuts import HttpResponse
from oauth2_provider.compat import urlparse
from apps.fhir.bluebutton import constants
from apps.fhir.bluebutton.utils import (request_call,
                                        prepend_q,
                                        get_resourcerouter,
                                        get_response_text,
                                        build_oauth_resource)


logger = logging.getLogger('hhs_server.%s' % __name__)


def fhir_conformance(request, via_oauth=False, *args, **kwargs):
    """ Pull and filter fhir Conformance statement

    BaseStu3 = "CapabilityStatement"

    :param request:
    :param via_oauth:
    :param args:
    :param kwargs:
    :return:
    """
    crosswalk = None
    resource_router = get_resourcerouter()
    call_to = resource_router.fhir_url
    api_ver = 'v1' if request.path is not None and request.path.startswith('/v1') else 'v2'
    parsed_url = urlparse(resource_router.fhir_url)

    if parsed_url.path is not None:
        call_to = '{}://{}/{}/fhir/metadata'.format(parsed_url.scheme, parsed_url.netloc, api_ver)
    else:
        # url with no path
        call_to = '{}/{}/fhir/metadata'.format(resource_router.fhir_url, api_ver)

    pass_params = {'_format': 'json'}

    encoded_params = urlencode(pass_params)
    pass_params = prepend_q(encoded_params)

    r = request_call(request, call_to + pass_params, crosswalk)

    text_out = ''

    if r.status_code >= 300:
        logger.debug("We have an error code to deal with: %s" % r.status_code)
        return HttpResponse(json.dumps(r._content),
                            status=r.status_code,
                            content_type='application/json')

    text_in = get_response_text(fhir_response=r)

    text_out = json.loads(text_in, object_pairs_hook=OrderedDict)

    od = conformance_filter(text_out)

    # Append Security to ConformanceStatement
    security_endpoint = build_oauth_resource(request, format_type="json")
    od['rest'][0]['security'] = security_endpoint
    # Fix format values
    od['format'] = ['application/json', 'application/fhir+json']

    return JsonResponse(od)


def conformance_filter(text_block):
    """ Filter FHIR Conformance Statement based on
        supported ResourceTypes
    """

    resource_names = constants.ALLOWED_RESOURCE_TYPES
    ct = 0
    if text_block:
        if 'rest' in text_block:
            for k in text_block['rest']:
                for i, v in k.items():
                    if i == 'resource':
                        supp_resources = get_supported_resources(v, resource_names)
                        text_block['rest'][ct]['resource'] = supp_resources
                ct += 1
        else:
            text_block = ""
    else:
        text_block = ""

    return text_block


def get_supported_resources(resources, resource_names):
    """ Filter resources for resource type matches """

    resource_list = []

    # if resource 'type in resource_names add resource to resource_list
    for item in resources:
        for k, v in item.items():
            if k == 'type':
                if v in resource_names:
                    item['interaction'] = [{"code": "read"}, {"code": "search-type"}]
                    resource_list.append(item)

    return resource_list
