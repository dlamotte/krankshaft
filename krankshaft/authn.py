# TODO OAuth1/2

# TODO Convert "expect" to "method"

import logging

log = logging.getLogger(__name__)

class Authn(object):
    '''
    Basic interface for any authenticator.  Always returns the request as
    not authenticated.
    '''
    expect = None

    def __init__(self, realm=None):
        self.use_realm = realm

    def authenticate(self, request):
        return None

    def authorization(self, request):
        return ''

    def can_handle(self, request):
        return bool(self.parse_expect(request))

    def challenge(self, request, response):
        return response

    def find_realm(self):
        return ''

    def is_valid(self, authned):
        return True

    def parse(self, request):
        credentials = self.parse_expect(request)
        if not credentials:
            return None

        try:
            identifer, credential = credentials.split(':', 1)
        except ValueError:
            return None

        if not (identifer and credential):
            return None

        return (identifer, credential)

    def parse_expect(self, request):
        header = self.authorization(request)
        if not header:
            return None

        try:
            method, credentials = header.split(None, 1)
        except ValueError:
            return None

        expect = self.expect
        if not expect:
            return credentials

        if isinstance(expect, (tuple, list)):
            if method.lower() not in expect:
                return None

        elif method.lower() != expect:
            return None

        return credentials

    @property
    def realm(self):
        return self.use_realm or self.find_realm()

    @property
    def secret(self):
        return ''

class AuthnDjango(Authn):
    '''
    Meant to be subclassed by Django Authenticators.  Will not work by itself.
    '''
    def authenticate(self, **credentials):
        from django.contrib.auth import authenticate as auth_authenticate
        return auth_authenticate(**credentials)

    def authorization(self, request):
        return request.META.get('HTTP_AUTHORIZATION', '')

    def find_realm(self):
        from django.contrib.sites.models import Site
        return Site.objects.get_current().name

    def is_valid(self, authned):
        return authned.user.is_active

    @property
    def secret(self):
        from django.conf import settings
        return settings.SECRET_KEY

class AuthnDjangoAPIToken(AuthnDjango):
    '''AuthnDjangoAPIToken(APIToken)

    An authenticator that uses a model that sub-classes the
    krankshaft.models.APITokenBase class as a form of authentication. Intended
    to make it possible to have credentials for a user separate from the
    password that are easily invalidated in one way or another.
    '''
    expect = ('apitoken', 'apikey')

    def __init__(self, model, **kwargs):
        super(AuthnDjangoAPIToken, self).__init__(**kwargs)
        self.model = model

    def authenticate(self, request):
        try:
            owner, token = self.parse(request)
        except TypeError:
            return None

        try:
            return self.model.get(owner, token)
        except (self.model.DoesNotExist, self.model.MultipleObjectsReturned):
            return None

    def challenge(self, request, response):
        response['WWW-Authenticate'] = 'APIToken realm="%s"' % self.realm
        return response

    def is_valid(self, authned):
        return authned.is_valid()

class AuthnDjangoBasic(AuthnDjango):
    '''
    Basic authentication using Django's Auth framework.
    '''
    expect = 'basic'

    def authenticate(self, request):
        try:
            username, password = self.parse(request)
        except TypeError:
            return None

        return super(AuthnDjangoBasic, self).authenticate(
            username=username,
            password=password,
        )

    def challenge(self, request, response):
        response['WWW-Authenticate'] = 'Basic realm="%s"' % self.realm
        return response

class AuthnDjangoMiddleware(AuthnDjango):
    '''
    An authenticator that passes through any authentication already provided
    by middleware.  Typically usage could be with Session middleware.
    Specifically, it uses whatever user is attached to the request object.

    note: CSRF validation is done to ensure a certain level of safety that the
    request came from a page served by the application.
    See: https://docs.djangoproject.com/en/dev/ref/contrib/csrf/#ajax
    '''
    def authenticate(self, request):
        from django.middleware.csrf import CsrfViewMiddleware

        # return reason not response
        class CSRF(CsrfViewMiddleware):
            def _reject(self, request, reason):
                return reason

        user = getattr(request, 'user', None)
        if not user:
            return None

        if not user.is_authenticated():
            return None

        reason = CSRF().process_view(request, None, (), {})
        if reason:
            log.warn('Authn failed due to CSRF verification failure')
            return None

        return user

class AuthnedInterface(object):
    '''
    Proxy to an authned object to give a common interface to objects returned
    from Authn.authenticate() or any of its subclasses.
    '''
    def __init__(self, authned):
        self.authned = authned

    @property
    def id(self):
        return self.authned.id

    def is_valid(self):
        is_valid = None

        if hasattr(self.authned, 'is_valid'):
            is_valid = self.authned.is_valid

        if is_valid and hasattr(is_valid, '__call__'):
            return is_valid()

        return bool(is_valid)

    @property
    def name(self):
        return self.authned.__class__.__name__

    @property
    def user(self):
        if hasattr(self.authned, 'user'):
            return self.authned.user
        return self.authned # assume we're an interface to a user
