from __future__ import absolute_import

from datetime import timedelta
from django.core.cache import cache
from functools import partial
from krankshaft.api import API as APIBase
from krankshaft.auth import Auth as AuthBase
from krankshaft.authn import Authn
from krankshaft.authz import Authz
from krankshaft.exceptions import KrankshaftError
from krankshaft.throttle import Throttle
from tempfile import NamedTemporaryFile
from tests.base import TestCaseNoDB
import json
import sys

class Auth(AuthBase):
    authn = Authn()
    authz = Authz()

class API(APIBase):
    Auth = Auth


class AuthzDeny(Authz):
    def is_authorized_request(self, request, authned):
        return False

class AuthDeny(AuthBase):
    authn = Authn()
    authz = AuthzDeny()

class APIDeny(APIBase):
    Auth = AuthDeny

ThrottleOne = partial(
    Throttle,
    anon_bucket=timedelta(seconds=2),
    anon_rate=(1, timedelta(seconds=10)),
    bucket=timedelta(seconds=2),
    cache=cache,
    rate=(1, timedelta(seconds=10))
)

class APITest(TestCaseNoDB):
    def _pre_setup(self):
        self.api = API('v1')
        self.apid = API('v1', debug=True)
        self.api_error = API('v1', debug=True, error='custom error message')
        super(APITest, self)._pre_setup()

        # make sure cache is clear
        cache.clear()

    def test_abort(self):
        request = self.make_request()
        self.assertRaises(self.api.Abort, self.api.abort, request, 401)
        try:
            self.api.abort(request, 401)
        except Exception, exc:
            self.assertEquals(401, exc.response.status_code)

        response = self.api.response(request, 401)
        try:
            self.api.abort(request, response)
        except Exception, exc:
            self.assertEquals(response, exc.response)

        self.assertRaises(
            KrankshaftError,
            self.api.abort,
            request,
            response,
            Header=''
        )

    def test_annotate(self):
        def fakeview(request):
            return \
                hasattr(request, 'auth') \
                and isinstance(request.auth, self.api.Auth)
        fakeview = self.api(fakeview)

        request = self.make_request()
        self.assertEqual(hasattr(request, 'auth'), False)
        self.assertEqual(fakeview(request), True)
        self.assertEqual(hasattr(request, 'auth'), False)

    def test_auth_deny(self):
        response = self.client.get('/deny/?key=value')
        self.assertEquals(response.status_code, 401)
        self.assertTrue(not response.content)

    def test_auth_deny_decorator_only(self):
        response = self.client.get('/deny-decorator-only/?key=value')
        self.assertEquals(response.status_code, 200)
        self.assertEquals(
            response['Content-Type'].split(';')[0],
            'application/json'
        )
        self.assertEquals(
            json.loads(response.content),
            {'key': 'value'}
        )

    def test_auth_deny_manual(self):
        response = self.client.get('/deny-decorator-only-manual/')
        self.assertEquals(response.status_code, 401)
        self.assertTrue(not response.content)

    def test_deserialize_delete_get_head_options(self):
        for method in (
            self.client.delete,
            self.client.get,
            self.client.head,
            self.client.options,
        ):
            response = method('/serialize-payload/?key=value&key2=value2')
            self.assertEquals(response.status_code, 200)
            self.assertEquals(
                response['Content-Type'].split(';')[0],
                'application/json'
            )
            if method not in (self.client.head,):
                self.assertEquals(
                    json.loads(response.content),
                    {'key': 'value', 'key2': 'value2'}
                )

    def test_deserialize_post_put_form_types(self):
        for method in (
            self.client.post,
            self.client.put,
        ):
            response = method(
                '/serialize-payload/',
                'key=value&key2=value2',
                content_type='application/x-www-form-urlencoded'
            )
            self.assertEquals(response.status_code, 200)
            self.assertEquals(
                response['Content-Type'].split(';')[0],
                'application/json'
            )
            self.assertEquals(
                json.loads(response.content),
                {'key': 'value', 'key2': 'value2'}
            )

            response = method(
                '/serialize-payload/',
                {'key': 'value', 'key2': 'value2'}
            )
            self.assertEquals(response.status_code, 200)
            self.assertEquals(
                response['Content-Type'].split(';')[0],
                'application/json'
            )
            self.assertEquals(
                json.loads(response.content),
                {'key': 'value', 'key2': 'value2'}
            )

            tmp = NamedTemporaryFile()
            tmp.write('value\n')
            tmp.seek(0)
            response = method('/serialize-payload/', {'file': tmp})
            self.assertEquals(response.status_code, 200)
            self.assertEquals(
                response['Content-Type'].split(';')[0],
                'application/json'
            )
            self.assertEquals(
                json.loads(response.content),
                {'file': 'value\n'}
            )
            tmp.close()

    def test_deserialize_invalid_content(self):
        response = self.client.post(
            '/serialize-payload/',
            '!',
            content_type='application/json'
        )
        self.assertEquals(response.status_code, 400)

    def test_deserialize_invalid_content_length(self):
        request = self.make_request('POST',
            data='{"key": "value"}',
            content_type='application/json',
            CONTENT_LENGTH='a'
        )
        query, data = self.api.deserialize(request)
        self.assertTrue(not data)

    def test_deserialize_invalid_content_nonabortable(self):
        request = self.make_request('POST',
            data='!',
            content_type='application/json'
        )
        self.assertRaises(
            ValueError,
            self.api.deserialize,
            request,
            abortable=False
        )

    def test_deserialize_unsupported_content_type(self):
        response = self.client.post(
            '/serialize-payload/',
            '!',
            content_type='unsupported/content-type'
        )
        self.assertEquals(response.status_code, 415)

    def test_deserialize_unsupported_content_type_nonabortable(self):
        request = self.make_request('POST',
            data='!',
            content_type='unsupported/content-type'
        )
        self.assertRaises(
            self.api.serializer.Unsupported,
            self.api.deserialize,
            request,
            abortable=False
        )

    def test_deserialize_invalid_query_string(self):
        response = self.client.get('/serialize-payload/?key=value&invalid')
        self.assertEquals(response.status_code, 200)
        self.assertEquals(
            response['Content-Type'].split(';')[0],
            'application/json'
        )
        self.assertEquals(
            json.loads(response.content),
            {'key': 'value', 'invalid': ''}
        )

    def test_handle_exc_abort(self):
        request = self.make_request()
        try:
            self.api.abort(request, 400)
        except Exception:
            response = self.api.handle_exc(request)

        self.assertEquals(response.status_code, 400)

    def test_handle_exc_unhandled_exception(self):
        request = self.make_request()
        try:
            {}['key']
        except Exception:
            response = self.api.handle_exc(request)

        self.assertEquals(response.status_code, 500)
        self.assertEquals(
            response['Content-Type'].split(';')[0],
            'application/json'
        )

        data = json.loads(response.content)
        self.assertEquals(data['error'], self.api.error)
        self.assertTrue('exception' not in data)
        self.assertTrue('traceback' not in data)

    def test_handle_exc_unhandled_exception_debug(self):
        request = self.make_request()
        try:
            {}['key']
        except Exception:
            response = self.apid.handle_exc(request)

        self.assertEquals(response.status_code, 500)
        self.assertEquals(
            response['Content-Type'].split(';')[0],
            'application/json'
        )

        data = json.loads(response.content)
        self.assertEquals(data['error'], self.apid.error)
        self.assertEquals(data['exception'], "KeyError: 'key'")
        self.assertTrue(data['traceback'])

    def test_handle_exc_unhandled_exception_debug_custom(self):
        request = self.make_request()
        try:
            {}['key']
        except Exception:
            response = self.apid.handle_exc(request, error='myerror')

        self.assertEquals(response.status_code, 500)
        self.assertEquals(
            response['Content-Type'].split(';')[0],
            'application/json'
        )

        data = json.loads(response.content)
        self.assertEquals(data['error'], 'myerror')
        self.assertEquals(data['exception'], "KeyError: 'key'")
        self.assertTrue(data['traceback'])

    def test_handle_exc_unhandled_exception_debug_custom_init(self):
        request = self.make_request()
        try:
            {}['key']
        except Exception:
            response = self.api_error.handle_exc(request)

        self.assertEquals(response.status_code, 500)
        self.assertEquals(
            response['Content-Type'].split(';')[0],
            'application/json'
        )

        data = json.loads(response.content)
        self.assertEquals(data['error'], self.api_error.error)
        self.assertEquals(data['exception'], "KeyError: 'key'")
        self.assertTrue(data['traceback'])

    def test_handle_exc_unhandled_exception_debug_specific(self):
        request = self.make_request()
        try:
            {}['key']
        except Exception:
            exc_info_keyerror = sys.exc_info()

        try:
            [][1]
        except Exception:
            exc_info_indexerror = sys.exc_info()
            response = self.apid.handle_exc(request, exc_info=exc_info_keyerror)

        self.assertEquals(response.status_code, 500)
        self.assertEquals(
            response['Content-Type'].split(';')[0],
            'application/json'
        )

        data = json.loads(response.content)
        self.assertEquals(data['error'], self.apid.error)
        self.assertEquals(data['exception'], "KeyError: 'key'")
        self.assertTrue(data['traceback'])

    def test_redirect(self):
        request = self.make_request()
        for code in (301, 302):
            response = self.api.redirect(request, code, '/hello world/')
            self.assertEquals(response.status_code, code)
            self.assertEquals(response['Location'], '/hello%20world/')

    def test_redirect_abort(self):
        request = self.make_request()
        for code in (301, 302):
            try:
                self.api.abort(request, self.api.redirect(request, code, '/'))
            except Exception, e:
                self.assertEquals(e.response.status_code, code)
                self.assertEquals(e.response['Location'], '/')

    def test_response(self):
        response = self.api.response(
            self.make_request(),
            200,
            'content',
            Content_Type='text/plain'
        )
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.content, 'content')
        self.assertEquals(
            response['Content-Type'].split(';')[0],
            'text/plain'
        )

    def test_serialize(self):
        data = {'one': 1}
        request = self.make_request(HTTP_ACCEPT='application/json; indent=4')
        response = self.api.serialize(request, 200, data)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(
            response['Content-Type'].split(';')[0],
            'application/json'
        )
        self.assertEquals(response.content, json.dumps(data, indent=4))

    def test_serialize_force_content_type(self):
        data = {'one': 1}
        request = self.make_request(HTTP_ACCEPT='application/xml')
        response = self.api.serialize(request, 200, data,
            content_type='application/json'
        )
        self.assertEquals(response.status_code, 200)
        self.assertEquals(
            response['Content-Type'].split(';')[0],
            'application/json'
        )
        self.assertEquals(response.content, json.dumps(data))

    def test_throttle(self):
        response = self.client.get('/throttle/?key=value')
        self.assertEquals(response.status_code, 200)
        self.assertEquals(
            response['Content-Type'].split(';')[0],
            'application/json'
        )
        self.assertEquals(
            json.loads(response.content),
            {'key': 'value'}
        )

        response = self.client.get('/throttle/?key=value')
        self.assertEquals(response.status_code, 429)
        self.assertTrue(not response.content)
        self.assertEquals(response['Retry-After'], '13')

    @property
    def urls(self):
        from django.conf.urls import url
        return self.make_urlconf(
            url('^deny/$',
                self.api(self.view_serialize_payload, auth=AuthDeny)
            ),
            url('^deny-decorator-only/$',
                self.api(auth=AuthDeny, only=True)(self.view_serialize_payload)
            ),
            url('^deny-decorator-only-manual/$',
                self.api(only=True)(self.view_auth_manual)
            ),
            url('^serialize-payload/$', self.api(self.view_serialize_payload)),
            url('^throttle/$',
                self.api(self.view_serialize_payload, throttle=ThrottleOne)
            ),
        )

    def view_auth_manual(self, request):
        auth = self.api.auth(request, Auth=AuthDeny)
        if auth:
            return self.api.serialize(request, 200, {'authed': True})

        else:
            return auth.challenge(self.api.response(request, 401))

    def view_serialize_payload(self, request):
        query, data = self.api.deserialize(request)

        for key, value in data.items():
            if hasattr(value, 'read'):
                data[key] = value.read()

        query.update(data)

        return self.api.serialize(request, 200, query)
