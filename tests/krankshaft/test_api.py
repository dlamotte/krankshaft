from __future__ import absolute_import

from krankshaft.api import API as APIBase
from krankshaft.auth import Auth as AuthBase
from krankshaft.authn import Authn
from krankshaft.authz import Authz
from krankshaft.exceptions import KrankshaftError
from tempfile import NamedTemporaryFile
from tests.base import TestCaseNoDB
import json
import sys

class Auth(AuthBase):
    authn = Authn()
    authz = Authz()

class API(APIBase):
    Auth = Auth

class APITest(TestCaseNoDB):
    def _pre_setup(self):
        self.api = API('v1')
        self.apid = API('v1', debug=True)
        self.api_error = API('v1', debug=True, error='custom error message')
        super(APITest, self)._pre_setup()

    def test_abort(self):
        self.assertRaises(self.api.Abort, self.api.abort, 401)
        try:
            self.api.abort(401)
        except Exception, exc:
            self.assertEquals(401, exc.response.status_code)

        response = self.api.response(401)
        try:
            self.api.abort(response)
        except Exception, exc:
            self.assertEquals(response, exc.response)

        self.assertRaises(KrankshaftError, self.api.abort, response, Header='')

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

    def test_deserialize_unsupported_content_type(self):
        response = self.client.post(
            '/serialize-payload/',
            '!',
            content_type='unsupported/content-type'
        )
        self.assertEquals(response.status_code, 415)

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
            self.api.abort(400)
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
        for code in (301, 302):
            response = self.api.redirect(code, '/hello world/')
            self.assertEquals(response.status_code, code)
            self.assertEquals(response['Location'], '/hello%20world/')

    def test_redirect_abort(self):
        for code in (301, 302):
            try:
                self.api.abort(self.api.redirect(code, '/'))
            except Exception, e:
                self.assertEquals(e.response.status_code, code)
                self.assertEquals(e.response['Location'], '/')

    def test_response(self):
        response = self.api.response(
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

    @property
    def urls(self):
        from django.conf.urls import url
        return self.make_urlconf(
            url('^serialize-payload/$', self.api(self.view_serialize_payload)),
        )

    def view_serialize_payload(self, request):
        query, data = self.api.deserialize(request)

        for key, value in data.items():
            if hasattr(value, 'read'):
                data[key] = value.read()

        query.update(data)

        return self.api.serialize(request, 200, query)
