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
from .exceptions import Abort, KrankshaftError, InvalidOptions, ValueIssue
from .serializer import Serializer
from .throttle import Throttle
from .util import Annotate
from .valid import Expecter
import functools
import inspect
import logging
import sys
import traceback
import urlparse

log = logging.getLogger(__name__)

# TODO resolve('/api/path/...') -> resource, args, kwargs
# TODO reverse(resource, args, kwargs) -> '/api/path/...'

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
    Error = KrankshaftError
    Expecter = Expecter
    InvalidOptions = InvalidOptions
    Serializer = Serializer
    Throttle = Throttle
    ValueIssue = property(lambda self: self.expecter.ValueIssue)

    defaults_dispatch = {
        'auth': True,
        'error': None,
        'methods': None,
        'only': False,
        'throttle': True,
        'throttle_suffix': None,
    }

    error = 'Internal Server Error'
    methods = (
        'get',
        'head',
        'options',
        'post',
        'put',
        'delete',
    )

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
        self.error = error or self.error
        self.name = name
        self.registry = []

        self.expecter = self.Expecter()
        self.serializer = self.Serializer()

    def __call__(self, view_or_resource=None, register=True, url=None, **opts):
        '''To be used as a decorator.

            @api
            def view(request):
                pass

        Or

            @api(option=value)
            def view(request):
                ...

        Or

            @api
            class MyResource(object):
                ...

        Or

            @api(option=value)
            class MyResource(object):
                ...

        For options, see wrap().  Only difference is register is default True.

        Do not use for creating resource urls.  Instead use wrap().
        '''
        return self.wrap(
            view_or_resource,
            register=register,
            url=url,
            **opts
        )

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
                raise self.Error(
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

    def dispatch(self, view, opts, request, *args, **kwargs):
        '''dispatch(view, None, request, *args, **kwargs) -> response

        Dispatch a view function wrapping it in exception handling (support
        for api.abort()) as well as handle authenticating, throttling, ... as
        defined by opts.
        '''
        opts = self.options_dispatch(opts)

        try:
            if opts['only']:
                return view(request, *args, **kwargs)

            if opts['methods'] is not None \
               and request.method not in opts['methods'] \
               and request.method.lower() not in opts['methods']:
                return self.response(request, 405,
                    Allow=', '.join([
                        method.upper()
                        for method in opts['methods']
                    ])
                )

            auth = self.Auth if opts['auth'] is True else opts['auth']
            throttle = None
            if auth:
                auth = auth(request)
                auth.authenticate()

                if not auth:
                    return self.challenge(request, auth)

                throttle = \
                    self.Throttle \
                    if opts['throttle'] is True \
                    else opts['throttle']

                if throttle:
                    throttle = throttle(request, auth)
                    allowed, headers = \
                        throttle.allow(suffix=opts['throttle_suffix'])

                    if not allowed:
                        return self.throttled(request, **headers)

            with Annotate(request, {
                'auth': auth,
                'throttle': throttle,
            }):
                return view(request, *args, **kwargs)

        except Exception:
            return self.handle_exc(request, error=opts['error'])

    def expect(self, expected, data):
        '''expect({'key': int}, {'key': '1'}) -> clean data

        In the above scenario, the returned data is:

            {'key': 1}

        Notice that the 1 goes from a string to an integer as part of the
        cleaning process.  Ideally, the returned datastructure can be fed into
        whatever it needs to be safely at this point without worrying about
        types of the values as a side-effect of just validating a proper data
        structure (no extraneous keys and proper expected values for the key).

        Simple validators as well as complex are supported.  See
        krankshaft.valid module for more details.

        Raises ValueIssue when expected does not properly validate data.
        '''
        return self.expecter.expect(expected, data)

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

    def make_resource_helper(self, klass_to_wrap, opts):
        '''make_resource_helper(klass) -> helper_instance

        This helper makes it possible to decorate a class and have it be
        connectable to Django.
        '''
        api = self

        # annotate wrapping api onto the class so it may be used without a prior
        # outside reference
        klass_to_wrap.api = api

        class Helper(object):
            __doc__ = klass_to_wrap.__doc__
            instance = klass_to_wrap()
            klass = klass_to_wrap

            def __call__(self, request, *args, **kwargs):
                view = lambda request, *args, **kwargs: \
                    api.route(self.instance, request, args, kwargs)
                return api.dispatch(view, opts, request, *args, **kwargs)

            def __getattr__(self, name):
                return getattr(self.instance, name)

        Helper.__module__ = klass_to_wrap.__module__
        Helper.__name__ = 'Helper.' + klass_to_wrap.__name__

        return Helper()

    def options_dispatch(self, opts):
        '''options_dispatch({'auth': False}) -> {'auth': False, ... defaults}

        Options:
            auth: only authed requests get through (default: True)
                optionally pass in Auth subclass
            error: message to use in case of unhandled exception
            methods: HTTP methods to allow through (default: all)
            only: only wrap the method to provide
                .abort()/unhandled-exception support
            throttle: rate-limit clients (default: True)
                optionally pass in Throttle subclass, depends on auth
            throttle_suffix: suffix the throttle key
                throttle the view seperately
        '''
        return util.valid(
            util.defaults({} if opts is None else opts, self.defaults_dispatch),
            self.defaults_dispatch.keys()
        )

    def redirect(self, request, status, location, **headers):
        '''redirect(request, 302, '/location') -> response

        Create a redirect response.
        '''
        return self.response(request, status, Location=location, **headers)

    def register(self, view, url=None):
        '''register(myview)

        Register the view with the API.

        url can be just a regex or a tuple/list of (regex, kwargs, name,
        prefix). It is essentially the same calling convention as
        django.conf.urls.url but minus the view parameter.
        '''
        if url is not None:
            if not isinstance(url, basestring) \
               and not (isinstance(url, (list, tuple)) and 1 <= len(url) <= 4):
                raise self.Error(
                    'register called with invalid url param: %r' % (url, )
                )

            if hasattr(view, 'urls'):
                raise self.Error(
                    'Will not register a resource to a url '
                    'if it has an urls attribute'
                )

        self.registry.append((view, url))

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

    def route(self, obj, request, args, kwargs):
        '''route(obj, request, args, kwargs) -> response

        Route a request to given obj.  If a route method exists on the object,
        simply forward control to it.  Otherwise, do a simple routing method
        based on the HTTP method of the request.

        Example:

            @api
            class SimpleResource(object):
                def all(self, request, *args, **kwargs):
                    ...

                def route(self, request, args, kwargs):
                    return self.all(request, *args, **kwargs)

        Example with default routing:

            @api
            class MethodResource(object):
                def get(self, request):
                    ...

                def post(self, request):
                    ...

        If obj is a dictionary, you can specify the handling of each method
        specifically.

            methods = {
                'post': self.post,
            }
            return api.route(methods, request, args, kwargs)

        '''
        # assume its an instance of a class
        if hasattr(obj, 'route'):
            return obj.route(request, args, kwargs)

        if isinstance(obj, dict):
            avail = obj.copy()
            for method in self.methods:
                avail.setdefault(method, None)

        else:
            avail = {
                method: getattr(obj, method, None)
                for method in self.methods
            }

        # assume its a class, route to a specific method
        method = request.method.lower()
        view = avail.get(method)

        if not view:
            return self.response(request, 405,
                Allow=', '.join([
                    method.upper()
                    for method, view in avail.iteritems()
                    if view
                ])
            )

        return view(request, *args, **kwargs)

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

    def throttled(self, request, code=429, **headers):
        return self.response(request, code, **headers)

    def update_view(self, view):
        '''update_view(view) -> view

        Hook to make updates to a view.

        In this context, a view can be a class or a function.  In the class
        case, its considered a resource.
        '''
        # Django's way of marking a view csrf_exempt
        view.csrf_exempt = True

        return view

    @property
    def urls(self):
        '''
        Returns the list of registered endpoints.

        For example, in your urls.py:

            url('^api/', include(api.urls))

        '''
        urlpatterns = []
        for view, url in self.registry:
            if url:
                urlitem = (url, view)
                if not isinstance(url, basestring):
                    urlitem = (url[0], view) + url[1:]

                urlpatterns.append(urlitem)

            extraurls = getattr(view, 'urls', None)
            if extraurls:
                urlpatterns.extend(extraurls)


        from django.conf.urls import include, patterns, url

        urlpatterns = patterns('', *urlpatterns)
        if self.name:
            urlpatterns = patterns('',
                url(r'^%s/' % self.name, include(urlpatterns)),
            )

        return urlpatterns

    def wrap(self, view_or_resource=None, register=False, url=None, **opts):
        '''wrap(myview) -> wrapped_view

        Wrap up a view function in an API container.

        Ideally used when setting up the urls property for resources.  ie:

            @propery
            def urls(self):
                return [
                    (r'^path/$', api.wrap(self.route_list)),
                    (r'^path/(?P<id>\d+)/$', api.wrap(self.route_object)),
                ]

        However, it has the same semantics as the decorator way to wrap a view.
        Except that this function defaults register to False (vs True for the
        api decorator).  So to wrap a view that you dont want to register:

            @api.wrap
            def myview(request):
                ...

        Options:

            register    whether or not to register the view (default: False)
            url         passed directly to register()

        See options_dispatch() for more available options.
        '''
        self.options_dispatch(opts)

        def decorator(view_or_resource):
            if inspect.isclass(view_or_resource):
                view = self.make_resource_helper(view_or_resource, opts)

            else:
                @functools.wraps(view_or_resource)
                def view(request, *args, **kwargs):
                    return self.dispatch(
                        view_or_resource,
                        opts,
                        request,
                        *args,
                        **kwargs
                    )

            view = self.update_view(view)
            if register:
                self.register(view, url=url)
            return view

        if view_or_resource:
            # used as a decorator
            # @api
            # class/def ...
            return decorator(view_or_resource)

        else:
            # passing params, return will be used as a decorator
            # @api(param=val)
            # class/def ...
            return decorator
