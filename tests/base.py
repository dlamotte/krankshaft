from __future__ import absolute_import

from django.core.handlers.wsgi import WSGIRequest
from django.test import TestCase
from django.test.client import MULTIPART_CONTENT, FakePayload
from django.utils.http import urlencode
from urlparse import urlparse

class TestCaseBase(TestCase):
    def make_request(self,
        method='GET',
        path='/',
        data=None,
        content_type=None,
        **extra
    ):
        if data is None:
            data = {}

        payload = None
        content_length = None
        if method not in ('DELETE', 'GET', 'HEAD', 'OPTIONS'):
            if content_type is None:
                content_type = MULTIPART_CONTENT
            encoded = self.client._encode_data(data, content_type)
            content_length = len(encoded)
            payload = FakePayload(encoded)
            data = {}

        if content_type is None:
            content_type = 'text/html; charset=utf-8'

        parsed = urlparse(path)
        environ = self.client._base_environ(**{
            'CONTENT_TYPE': content_type,
            'PATH_INFO': self.client._get_path(parsed),
            'QUERY_STRING': urlencode(data, doseq=True) or parsed[4],
            'REQUEST_METHOD': method,
        })

        if payload:
            environ['CONTENT_LENGTH'] = content_length
            environ['wsgi.input'] = payload

        environ.update(extra)
        return WSGIRequest(environ)

    def make_urlconf(self, *args, **kwargs):
        from django.conf.urls import patterns

        class Helper(object):
            pass

        module = Helper()
        module.urlpatterns = patterns('', *args, **kwargs)
        return module

class TestCaseNoDB(TestCaseBase):
    def _pre_setup(self):
        self.client = self.client_class()
        self._urlconf_setup()

    def _post_teardown(self):
        self._urlconf_teardown()
