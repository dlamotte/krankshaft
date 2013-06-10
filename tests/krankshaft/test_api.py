from __future__ import absolute_import

from krankshaft.api import API as APIBase
from krankshaft.auth import Auth as AuthBase
from krankshaft.authn import Authn
from krankshaft.authz import Authz
from krankshaft.exceptions import KrankshaftError
from tempfile import NamedTemporaryFile
from tests.base import TestCaseNoDB
import json

class Auth(AuthBase):
    authn = Authn()
    authz = Authz()

class API(APIBase):
    Auth = Auth

class APITest(TestCaseNoDB):
    def _pre_setup(self):
        self.api = API('v1')
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
