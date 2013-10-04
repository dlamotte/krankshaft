# TODO fire signal on auth failure?

from . import authn, authz

class Auth(object):
    '''
    Bind a request to this object and centralizes all Authentication and
    Authorization interfaces.

    For convenience, you may test it in a boolean way to ensure the request
    is both authenticated and authorized.

        auth = Auth(request)
        if auth:
            # request is authorized (depending on your authorization scheme
            # the request may or may not be authenticated)
            obj = ...
            if auth.is_authorized_obj(obj):
                # now the request is authorized to operate on the object
            else:
                # request is not authorized to the object
        else:
            # request is not authorized (but may be authenticated)

    As an option, you can set 'authn' to a list/tuple of Authn's.  When
    initialized, it will decide which Authn to use and bind it permanently.
    '''
    AuthnedInterface = authn.AuthnedInterface

    authn = authn.AuthnDjangoBasic()
    authz = authz.AuthzReadonly()

    def __init__(self, request):
        self.authned = None
        self.request = request

        if isinstance(self.authn, (list, tuple)):
            use_authn = None
            for authn in self.authn:
                if authn.can_handle(self.request):
                    use_authn = authn
                    break
            self.authn = use_authn

    def __nonzero__(self):
        return self.is_authorized_request()

    def authenticate(self):
        '''authenticate() -> self.authned

        Process the request and test if the request is authenticated.
        '''
        if not self.authn:
            return None

        authned = self.authn.authenticate(self.request)
        if authned and self.authn.is_valid(authned):
            self.authned = self.AuthnedInterface(authned)
            return self.authned
        return None

    def challenge(self, response):
        '''challenge(response) -> response

        Update a response in flight.  Useful to add HTTP Authenticate headers.
        '''
        if self.authn:
            response = self.authn.challenge(self.request, response)
        return response

    @property
    def id(self):
        '''
        A unique identifier for a request.  If not authenticated, the
        REMOTE_ADDR of the request is used.
        '''
        if self.authned:
            return '%s-%s' % (
                self.authned.name,
                self.authned.id
            )

        else:
            return 'anon-%s' % self.request.META.get('REMOTE_ADDR', 'noaddr')

    def is_authenticated(self):
        '''is_authenticated() -> bool

        Test if the bound request is authned.

        note: depends on .authenticate() being called otherwise always False
        '''
        return bool(self.authned)

    def is_authorized_obj(self, obj):
        '''is_authorized_obj(obj) -> bool

        Test if authorized to operate on object.
        '''
        return self.authz.is_authorized_obj(self.request, self.authned, obj)

    def is_authorized_request(self):
        '''is_authorized_request() -> bool

        Test if authorized to process request further.  No guarantees are
        placed on if .is_authorized_obj() will be called ever.
        '''
        return self.authz.is_authorized_request(self.request, self.authned)

    def limit(self, query):
        '''limit(query) -> limited_query

        Pass the given query through any applicable authorization limits and
        return a new limited query that should only be visible to the
        requester.
        '''
        return self.authz.limit(self.request, self.authned, query)

    @property
    def user(self):
        if self.authned:
            return self.authned.user
        return None
