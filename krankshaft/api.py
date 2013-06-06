# TODO features
#   - caching
#   - throttling
#
#   - automatic model resources/serialization/...
#       - form validation... does it even make sense at API level?
#       - pagination (is this only related to objects, seems like it...)?

# TODO stop **headers crap, make a headers object and pass that around...
# TODO transactions

from .auth import Auth
from .exceptions import Abort
from .serializer import Serializer
from .throttle import Throttle
import functools
import logging
import mimeparse
import sys
import traceback

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

    default_error_message = 'Internal Server Error'

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
        self.error = error or self.default_error_message

        self.serializer = self.Serializer()

    def __call__(self, f=None, auth=True, error=None, only=False):
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
                optionally pass in Auth subclass to replace how Auth is done
            error: message to use in case of unhandled exception
            only: only wrap the method to provide
                .abort()/unhandled-exception support
        '''
        def _decorator(f):
            @functools.wraps(f)
            def _call(request, *args, **kwargs):
                try:
                    if only:
                        return f(request, *args, **kwargs)

                    if auth:
                        if auth is True:
                            auth = self.Auth
                        _auth = self.auth(request, Auth=auth)
                        if not _auth:
                            return _auth.challenge(self.response(401))

                    return f(request, *args, **kwargs)
                except Exception:
                    return self.handle_exc(request, message=error)

            return self.update_view(_call)

        if f:
            # used as a decorator
            # @api
            # def view(...):
            return _decorator(f)

        else:
            # passing params, return will be used as a decorator
            # @api(param=val)
            # def view(...):
            return _decorator

    def abort(self, status_or_response, **headers):
        '''abort(401)

        Return HTTP Response with given status.

        Example:

            try:
                ...
                api.abort(401)
                ...
            except Exception:
                return api.handle_exc(request)

        Or use the decorator version:

            @api
            def view(request):
                ...
                api.abort(401)
        '''
        if isinstance(status_or_response, int):
            raise self.Abort(
                self.response(status=status_or_response, **headers)
            )
        else:
            assert not headers
            raise self.Abort(response)

    def auth(self, request, Auth=None):
        '''auth(request) -> auth

        Authenticate the current request and return an instance of Auth.
        '''
        Auth = Auth or self.Auth
        auth = Auth(request)
        auth.authenticate()
        return auth

    def deserialize(self, request):
        '''deserialize(request) -> data

        Read in the request data to a native data structure.
        '''
        data = {}
        if request.method == 'GET':
            return request.GET

        form_content_types = [
            'application/x-www-form-urlencoded',
            'multipart/form-data',
        ]

        content_type = request.META['CONTENT_TYPE']
        if mimeparse.best_match(form_content_types, content_type):
            data = request.POST
            data.update(request.FILES)
            return data

        else:
            return self.serializer.deserialize(request.body, content_type)

    def extra(self, **more):
        data = {
            'debug': self.debug,
            'name': self.name,
            'stack': True,
        }
        data.update(more)
        return data

    def handle_exc(self, request, exc_info=True, message=None):
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
            return self.handler500(request, exc_info, message=message)

    def handler500(self, request, exc_info, message=None):
        '''handler500(request, sys.exc_info())

        Returns a 500 response with error details.
        '''
        exc, inst, tb = exc_info
        message = message or self.error

        log.error(
            '%s: %s',
                message,
                inst,
            exc_info=exc_info,
            extra=self.extra(),
        )

        data = {
            'error': message,
        }

        if self.debug:
            data['exception'] = str(inst)
            data['traceback'] = '\n'.join(
                traceback.format_exception(*exc_info)
            )

        data = self.hook_500(data, exc_info)

        return self.serialize(request, 500, data)

    def hook_500(self, data, exc_info):
        '''hook_500(data, exc_info) -> data

        Convenience hook for changing data returned from a 500.
        '''
        return data

    def hook_response(self, response):
        '''hook_response(response) -> response

        Hook to update a response after creation.
        '''
        # TODO probably need to de-construct the Content-Type via the standard
        # and patch the header... general purpose 'http' module that implements
        # rfc standards parsing routines?
        response['Content-Type'] += '; charset=utf-8'
        return response

    def redirect(self, status, location, **headers):
        '''redirect(302, '/location') -> response

        Create a redirect response.
        '''
        return self.response(status, Location=location, **headers)

    def response(self, status, content=None, **headers):
        '''response(200) -> response

        Create a response object.

        Header name containing underscores will be changed to dash in order to
        make it less of a burden syntactically.

            Content_Type

        Becomes:

            Content-Type
        '''
        from django import http

        if status in (301, 302, 304):
            location = headers.pop('Location', '')
            if status == 301:
                response = http.HttpResponsePermanentRedirect(location)
            elif status == 302:
                response = http.HttpResponseRedirect(location)
            elif status == 304:
                response = http.HttpResponseNotModified(location)

        else:
            response = http.HttpResponse(status=status)

        for name, val in headers.items():
            name = name.replace('_', '-')
            response[name] = val

        if content:
            response.content = content

        return self.hook_response(response)

    def serialize(self, request, status, obj,
        content_type=None
        , headers=None
        , **opts
    ):
        '''serialize(request, 200, obj) -> response

        Serialize an status and object to a response given a request.
        '''
        headers = headers or {}
        content, content_type = self.serializer.serialize(
            obj,
            request.META.get('HTTP_ACCEPT', content_type),
            **opts
        )

        headers['Content-Type'] = content_type

        return self.response(status, content, **headers)

    def update_view(self, view):
        '''update_view(view) -> view

        Hook to make updates to a view.
        '''
        from django.views.decorators.csrf import csrf_exempt
        view = csrf_exempt(view)
        return view
