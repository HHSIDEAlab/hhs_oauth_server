import re
import uuid
from django.core.exceptions import MultipleObjectsReturned
from django.db import transaction
from django.db.utils import IntegrityError
from oauth2_provider.models import get_application_model
from .models import AuthFlowUuid


"""
  Logger related functions for dot_ext/mymedicare_cb modules.

  The AuthFlowUuid tracking object is used to track the
  auth flow between beneficiary and 3rd party application sessions.

  Values are retrieved/updated in the request.session.
"""

# List of value keys that are being tracked via request.session
SESSION_AUTH_FLOW_TRACE_KEYS = ['auth_uuid', 'auth_client_id', 'auth_grant_type', 'auth_app_id',
                                'auth_app_name', 'auth_pkce_method', 'auth_crosswalk_action',
                                'auth_share_demographic_scopes', 'auth_require_demographic_scopes']

# REGEX of paths that should be updated with auth flow info in hhs_oauth_server.request_logging.py
AUTH_FLOW_REQUEST_LOGGING_PATHS_REGEX = ("(^/[v1|v2]/o/authorize/.*"
                                         "|^/mymedicare/login$|^/mymedicare/sls-callback$"
                                         "|^/[v1|v2]/o/token/$)")


def is_path_part_of_auth_flow_trace(path):
    '''
    Check if provided path is related to the authorization flow logging.

    CALLED FROM: hhs_oauth_server.request_logging.RequestResponseLog.__str__()
    '''
    return re.match(AUTH_FLOW_REQUEST_LOGGING_PATHS_REGEX, path)


def cleanup_session_auth_flow_trace(request):
    '''
    Clean up auth flow related items in a session.

    CALLED FROM:  apps.testclient.views.callback()
                  apps.dot_ext.views.authorization.AuthorizationView.form_valid()
    '''
    for k in SESSION_AUTH_FLOW_TRACE_KEYS:
        try:
            del request.session[k]
        except KeyError:
            pass


def create_session_auth_flow_trace(request):
    '''
    Create auth flow log tracing related items.

    - Create a new AuthFlowUuid instance.
    - Set new auth flow values in session.

    CALLED FROM:  apps.dot_ext.views.authorization.AuthorizationView.dispatch()
    '''
    Application = get_application_model()

    # Create new authorization flow trace UUID.
    new_auth_uuid = str(uuid.uuid4())

    # Clear out session keys in case existing from another auth flow.
    clear_session_auth_flow_trace(request)

    request.session['auth_uuid'] = new_auth_uuid

    client_id_param = request.GET.get("client_id", None)
    auth_pkce_method = request.GET.get("code_challenge_method", None)

    if client_id_param:
        try:
            application = Application.objects.get(client_id=client_id_param)

            # Set values in session.
            auth_flow_dict = {"auth_uuid": new_auth_uuid,
                              "auth_app_id": str(application.id),
                              "auth_app_name": application.name,
                              "auth_require_demographic_scopes": str(application.require_demographic_scopes),
                              "auth_client_id": application.client_id,
                              "auth_pkce_method": auth_pkce_method,
                              }
            set_session_auth_flow_trace(request, auth_flow_dict)

            try:
                # Create and return AuthFlowUuid instance for tracking.
                with transaction.atomic():
                    AuthFlowUuid.objects.create(auth_uuid=new_auth_uuid,
                                                client_id=application.client_id,
                                                auth_pkce_method=auth_pkce_method)
            except IntegrityError:
                pass
        except Application.DoesNotExist:
            # Clear values in session. Set to empty value to denote not found.
            auth_flow_dict = {"auth_uuid": new_auth_uuid,
                              "auth_app_id": "",
                              "auth_app_name": "",
                              "auth_require_demographic_scopes": "",
                              "auth_client_id": "",
                              "auth_pkce_method": "",
                              }
            set_session_auth_flow_trace(request, auth_flow_dict)


def get_session_auth_flow_trace(request):
    '''
    Get auth flow related items from the session.

    Returns a auth_flow_dict type DICT of values for logging.
    '''
    if request:
        auth_flow_dict = {}
        for k in SESSION_AUTH_FLOW_TRACE_KEYS:
            if k in request.session:
                auth_flow_dict[k] = request.session.get(k)
        return auth_flow_dict
    else:
        # Some unit test calls to this have request=None, so return empty dict.
        return {}


def set_session_auth_flow_trace(request, auth_flow_dict):
    '''
    Set auth flow related items in the session from a dictionary.
    '''
    if request.session:
        for k in SESSION_AUTH_FLOW_TRACE_KEYS:
            if k in auth_flow_dict:
                request.session[k] = auth_flow_dict.get(k)


def clear_session_auth_flow_trace(request):
    '''
    Clear auth flow related keys from the session.
    '''
    if request.session:
        for k in SESSION_AUTH_FLOW_TRACE_KEYS:
            request.session.pop(k, None)


def set_session_values_from_auth_flow_uuid(request, auth_flow_uuid):
    '''
    Set auth flow related items in the session given an AuthFlowUuid instance.
    '''
    Application = get_application_model()

    if auth_flow_uuid:
        request.session['auth_uuid'] = str(auth_flow_uuid.auth_uuid)
        if auth_flow_uuid.auth_pkce_method is not None:
            request.session['auth_pkce_method'] = auth_flow_uuid.auth_pkce_method
        if auth_flow_uuid.auth_crosswalk_action is not None:
            request.session['auth_crosswalk_action'] = auth_flow_uuid.auth_crosswalk_action
        if auth_flow_uuid.auth_share_demographic_scopes is not None:
            request.session['auth_share_demographic_scopes'] = str(auth_flow_uuid.auth_share_demographic_scopes)

        try:
            application = Application.objects.get(client_id=auth_flow_uuid.client_id)

            # Set values in session.
            request.session['auth_app_id'] = str(application.id)
            request.session['auth_app_name'] = application.name
            request.session['auth_require_demographic_scopes'] = str(application.require_demographic_scopes)
            request.session['auth_client_id'] = application.client_id
        except Application.DoesNotExist:
            pass


def set_session_auth_flow_trace_value(request, key, value):
    '''
    Set auth flow key value in the session.
    '''
    if request.session:
        request.session[key] = value


def update_instance_auth_flow_trace_with_code(auth_dict, code):
    '''
    Update AuthFlowUuid instance with code, crosswalk_action and share_demographic_scopes values.

    CALLED FROM:  apps.dot_ext.views.authorization.AuthorizationView.form_valid()
    '''
    auth_uuid = auth_dict.get('auth_uuid', None)
    auth_crosswalk_action = auth_dict.get('auth_crosswalk_action', None)
    auth_share_demographic_scopes = auth_dict.get('auth_share_demographic_scopes', None)

    try:
        if auth_uuid:
            with transaction.atomic():
                auth_flow_uuid = AuthFlowUuid.objects.get(auth_uuid=auth_uuid)

                if code and len(code.strip()) != 0:
                    auth_flow_uuid.code = code

                if auth_crosswalk_action:
                    auth_flow_uuid.auth_crosswalk_action = auth_crosswalk_action

                if auth_share_demographic_scopes:
                    if auth_share_demographic_scopes == "True":
                        auth_flow_uuid.auth_share_demographic_scopes = True
                    elif auth_share_demographic_scopes == "False":
                        auth_flow_uuid.auth_share_demographic_scopes = False
                auth_flow_uuid.save()
    except AuthFlowUuid.DoesNotExist:
        pass
    except IntegrityError:
        pass


def update_session_auth_flow_trace_from_code(request, code):
    '''
    Update session values from AuthFlowUuid instance from code.

    CALLED FROM:  apps.dot_ext.oauth2_backends.OAuthLibSMARTonFHIR.create_token_response()
    '''
    # Get session values from AuthFlowUuid via code.
    try:
        # Get previously created AuthFlowUuid with code.
        if code and len(code.strip()) != 0:
            auth_flow_uuid = AuthFlowUuid.objects.get(code=code)
            set_session_values_from_auth_flow_uuid(request, auth_flow_uuid)
            # Delete the no longer needed instance
            auth_flow_uuid.delete()
    except AuthFlowUuid.DoesNotExist:
        pass
    except MultipleObjectsReturned:
        pass


def update_instance_auth_flow_trace_with_state(request, state):
    '''
    Update AuthFlowUuid instance with state value.

    CALLED FROM:  apps.mymedicare_cb.views.mymedicare_login()
    '''
    # Update AuthFlowUuid instance to pass along auth_uuid using state.
    auth_uuid = request.session.get('auth_uuid', None)

    if auth_uuid:
        # Store state in AuthFlowUuid.
        try:
            if state and len(state.strip()) != 0:
                with transaction.atomic():
                    auth_flow_uuid = AuthFlowUuid.objects.get(auth_uuid=auth_uuid)
                    auth_flow_uuid.state = state
                    auth_flow_uuid.save()
        except AuthFlowUuid.DoesNotExist:
            pass
        except IntegrityError:
            pass


def update_session_auth_flow_trace_from_state(request, state):
    '''
    Update session values from AuthFlowUuid instance from state.

    CALLED FROM:  apps.mymedicare_cb.views.authenticate()
    '''
    # Retreive auth flow session values using previous state in AuthFlowUuid.
    try:
        if state and len(state.strip()) != 0:
            auth_flow_uuid = AuthFlowUuid.objects.get(state=state)
            set_session_values_from_auth_flow_uuid(request, auth_flow_uuid)
    except AuthFlowUuid.DoesNotExist:
        pass
    except MultipleObjectsReturned:
        pass
