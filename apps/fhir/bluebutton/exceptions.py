from rest_framework.exceptions import NotFound, APIException
from rest_framework import status
from requests import Response
from .models import Fhir_Response


def process_error_response(response: Fhir_Response) -> APIException:
    """
    TODO: This should be more specific (original comment before BB2-128)
    BB2-128: check FHIR response: if error is "IllegalArgumentException: Unsupported ID pattern..."
    then append the error to the general error message: 'An error occurred contacting the upstream server'
    As of BB2-291 in support BFD v2, it's a good time to map BFD 500 (server error) response where diagnostics contains
    java.lang.IllegalArgumentException to 'client error' 400 Bad Request, this will reduce large number of 500 (server error)
    alerts at runtime
    """
    err: APIException = None
    r: Response = response.backend_response
    if response.status_code >= 300:
        if response.status_code == 404:
            err = NotFound('The requested resource does not exist')
        else:
            msg = 'An error occurred contacting the upstream server'
            err = UpstreamServerException(msg)
            if response.status_code == 500:
                try:
                    json = r.json()
                    if json is not None:
                        issues = json.get('issue')
                        issue = issues[0] if issues else None
                        diagnostics = issue.get('diagnostics') if issue else None
                        if diagnostics is not None:
                            if "IllegalArgumentException" in diagnostics:
                                err = BadRequestToBackendError("{}:{}".format(msg, diagnostics))
                            else:
                                err = UpstreamServerException("{}:{}".format(msg, diagnostics))
                except Exception:
                    pass
    return err


class UpstreamServerException(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY


class BadRequestToBackendError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
