# TODO features
#   - caching
#
#   - automatic model resources/serialization/...
#       - form validation... does it even make sense at API level?
#       - pagination (is this only related to objects, seems like it...)?

# TODO stop **headers crap, make a headers object and pass that around...
# TODO transactions

from . import util
from .auth import Auth
from .exceptions import Abort, KrankshaftError
from .serializer import Serializer
from .throttle import Throttle
from .util import Annotate
import functools
import logging
import sys
import traceback
import urlparse

log = logging.getLogger(__name__)

class API(object):
    '''
    Create a new API.

    apiv1 = API('v1')

    Use it as a decorator:

        @apiv1
        def view(request):
            return apiv1.serialize(request, 200, {
                'key': 'value',
            })

    Or programatically:

        @apiv1(only=True)
        def view(request):
            auth = apiv1.auth(request)
            if auth:
                return apiv1.serialize(request, 200, {
                    'authed': 'response',
                })
            else:
                return apiv1.serialize(request, 200, {
                    'un-authed': 'response',
                })
    '''

    Abort = Abort
    Auth = Auth
    Serializer = Serializer
    Throttle = Throttle

    error = 'Internal Server Error'

    def __init__(self,
        name=''
        , debug=False
        , error=None
    ):
        '''
        Options:
            debug: enable debugging (default: False)
            error: default un-handled exception

        Example of using error:

            API(error='Error, see http://host.com/in-case-of-error/')
        '''
        self.debug = debug
        self.name = name
        self.error = error or self.error

        self.serializer = self.Serializer()

    # TODO if auth is done, how does view figure out where the 'auth' object is?
    #      ie: who is the requested authned for?
    def __call__(self,
        f=None,
        auth=True,
        error=None,
        only=False,
        throttle=True,
        throttle_suffix=None
    ):
        '''To be used as a decorator.

        Only pass keyword arguments to this function.

        @api
        def view(request):
            pass

        Or

        @api(option=value)
        def view(request):
            ...

        Options:
            auth: only authed requests get through (default: True)
                optionally pass in Auth subclass
            error: message to use in case of unhandled exception
            only: only wrap the method to provide
                .abort()/unhandled-exception support
            throttle: rate-limit clients (default: True)
                optionally pass in Throttle subclass
            throttle_suffix: suffix the throttle key
                throttle the view seperately
        '''
        def decorator(view):
            @functools.wraps(view)
            def call(request, *args, **kwargs):
                try:
                    if only:
                        return view(request, *args, **kwargs)

                    Auth = self.Auth
                    if auth not in (True, False):
                        Auth = auth

                    _auth = Auth(request)
                    if auth:
                        _auth.authenticate()
                        if not _auth:
                            return self.challenge(request, _auth)

                    Throttle = self.Throttle
                    if throttle not in (True, False):
                        Throttle = throttle

                    _throttle = Throttle()
                    if throttle:
                        allowed, headers = _throttle.allow(_auth,
                            suffix=throttle_suffix
                        )
                        if not allowed:
                            return self.response(request, 429, **headers)

                    with Annotate(request, {
                        'auth': _auth,
                        'throttle': _throttle,
                    }):
                        return view(request, *args, **kwargs)

                except Exception:
                    return self.handle_exc(request, error=error)

            return self.update_view(call)

        if f:
            # used as a decorator
            # @api
            # def view(...):
            return decorator(f)

        else:
            # passing params, return will be used as a decorator
            # @api(param=val)
            # def view(...):
            return decorator

    def abort(self, request, status_or_response, **headers):
        '''abort(request, 400)

        Abort current execution with HTTP Response with given status.  If a
        response is given, abort current execution with given response.

        Example:

            try:
                ...
                api.abort(request, 400)
                ...
            except Exception:
                return api.handle_exc(request)

        Or use the decorator version:

            @api
            def view(request):
                ...
                api.abort(request, 400)
        '''
        if isinstance(status_or_response, int):
            raise self.Abort(
                self.response(request, status=status_or_response, **headers)
            )
        else:
            if headers:
                raise KrankshaftError(
                    'Cannot pass headers with given a response'
                )
            raise self.Abort(status_or_response)

    def auth(self, request, Auth=None):
        '''auth(request) -> auth

        Authenticate the current request and return an instance of Auth.
        '''
        Auth = Auth or self.Auth
        auth = Auth(request)
        auth.authenticate()
        return auth

    def challenge(self, request, auth, status=401):
        return auth.challenge(self.response(request, status))

    def deserialize(self, request, abortable=True):
        '''deserialize(request) -> query, body

        Read in the request data to a native data structures.
        '''
        from django.utils.datastructures import MultiValueDict

        try:
            query = urlparse.parse_qs(
                request.META.get('QUERY_STRING', ''),
                keep_blank_values=True
            )
            query = MultiValueDict(query)

            content_type = request.META.get('CONTENT_TYPE')
            content_length = request.META.get('HTTP_CONTENT_LENGTH',
                request.META.get('CONTENT_LENGTH', 0)
            )
            try:
                content_length = int(content_length)
            except ValueError:
                content_length = 0

            if content_type and content_length > 0:
                data = self.serializer.deserialize_request(
                    request,
                    content_type
                )
            else:
                data = {}

            if not isinstance(data, MultiValueDict):
                # fake out returned value to ensure same interface
                data = MultiValueDict({
                    key: value if isinstance(value, (tuple, list)) else [value]
                    for key, value in data.iteritems()
                })

            return (query, data)
        except ValueError:
            if abortable:
                self.abort(request, 400)
            else:
                raise

        except self.serializer.Unsupported:
            if abortable:
                self.abort(request, 415)
            else:
                raise

    def extra(self, **more):
        data = {
            'api': self.name,
            'debug': self.debug,
            'stack': True,
        }
        data.update(more)
        return data

    def handle_exc(self, request, exc_info=True, error=None):
        '''handle_exc(request) -> response

        Handle arbitrary exceptions.  Serves two main purposes:

        1) needed to support abort()
        2) pass other exceptions to handler500()
        '''
        if exc_info is True:
            exc_info = sys.exc_info()

        exc, inst, tb = exc_info
        if issubclass(exc, self.Abort):
            return inst.response

        else:
            return self.handler500(request, exc_info, error=error)

    def handler500(self, request, exc_info, error=None):
        '''handler500(request, sys.exc_info())

        Returns a 500 response with error details.
        '''
        exc, inst, tb = exc_info
        error = error or self.error

        log.error(
            '%s, %s: %s',
                error,
                exc.__name__,
                inst,
            exc_info=exc_info,
            extra=self.extra(),
        )

        data = {
            'error': error,
        }

        if self.debug:
            data['exception'] = '%s: %s' % (exc.__name__, inst)
            data['traceback'] = '\n'.join(
                traceback.format_exception(*exc_info)
            )

        data = self.hook_500(data, request, exc_info)

        return self.serialize(request, 500, data)

    def hook_500(self, data, request, exc_info):
        '''hook_500(data, request, exc_info) -> data

        Convenience hook for changing data returned from a 500.
        '''
        return data

    # TODO patch vary headers...
    #   - default to "Vary: Accept", depending on authn type, do we change it to
    #     "Vary: Accept, Cookie" also?
    # TODO cache control headers...
    #   - default to "Cache-Control: no-store" and "Pragma: no-cache"?
    #   - check out tastypie.cache.SimpleCache
    def hook_response(self, response):
        '''hook_response(response) -> response

        Hook to update a response after creation.
        '''
        # TODO probably need to de-construct the Content-Type via the standard
        # and patch the header... general purpose 'http' module that implements
        # rfc standards parsing routines?
        response['Content-Type'] += '; charset=utf-8'
        return response

    def redirect(self, request, status, location, **headers):
        '''redirect(request, 302, '/location') -> response

        Create a redirect response.
        '''
        return self.response(request, status, Location=location, **headers)

    def response(self, request, status, content=None, **headers):
        '''response(request, 200) -> response

        Create a response object.

        Header name containing underscores will be changed to dash in order to
        make it less of a burden syntactically.

            Content_Type

        Becomes:

            Content-Type
        '''
        from django import http

        if status in (301, 302):
            location = headers.pop('Location', '')
            if status == 301:
                response = http.HttpResponsePermanentRedirect(location)
            elif status == 302:
                response = http.HttpResponseRedirect(location)

        else:
            response = http.HttpResponse(status=status)

        for name, val in headers.items():
            response[util.kw_as_header(name)] = val

        if content:
            response.content = content

        return self.hook_response(response)

    def serialize(self, request, status, obj,
        content_type=None
        , opts=None
        , **headers
    ):
        '''serialize(request, 200, obj) -> response

        Serialize an status and object to a response given a request.
        '''
        opts = opts or {}
        content, content_type = self.serializer.serialize(
            obj,
            content_type or request.META.get('HTTP_ACCEPT'),
            **opts
        )

        headers['Content-Type'] = content_type

        return self.response(request, status, content, **headers)

    def update_view(self, view):
        '''update_view(view) -> view

        Hook to make updates to a view.
        '''
        from django.views.decorators.csrf import csrf_exempt
        view = csrf_exempt(view)
        return view
