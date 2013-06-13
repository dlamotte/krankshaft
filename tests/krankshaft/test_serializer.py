from __future__ import absolute_import

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from django.core.handlers.wsgi import WSGIRequest
from django.test.client import FakePayload
from krankshaft.serializer import Serializer
from tests.base import TestCaseNoDB
from urlparse import urlparse
import pytz

class SerializerConvertTest(TestCaseNoDB):
    dt = datetime(2013, 6, 8, 14, 34, 28, 121251)
    dt_expect = '2013-06-08T14:34:28.121251'
    td = timedelta(1, 2, 3)
    tz = pytz.timezone('America/Chicago')

    def do(self, obj, expect):
        self.assertEquals(expect, self.serializer.convert(obj))

    def setUp(self):
        self.serializer = Serializer()

    def test_date(self):
        self.do(self.dt.date(), self.value(self.dt_expect.split('T')[0]))

    def test_datetime(self):
        self.do(self.dt, self.value(self.dt_expect))

    def test_datetime_with_timezone(self):
        self.do(
            self.tz.normalize(self.tz.localize(self.dt)),
            self.value(self.dt_expect + '-05:00')
        )

    def test_decimal(self):
        self.do(Decimal('1.7921579150'), self.value('1.7921579150'))

    def test_dict(self):
        self.do(
            {'key': self.dt},
            {'key': self.dt_expect}
        )

    def test_list(self):
        self.do(
            [self.dt],
            [self.dt_expect]
        )

    def test_primitive(self):
        for value in self.serializer.primitive_values + (1, 1L, 1.1, 'a', u'a'):
            self.assertEquals(value, self.serializer.convert(value))

    def test_serializer_default_content_type(self):
        serializer = Serializer(
            default_content_type='application/json'
        )
        content, content_type = serializer.serialize({'key': 'value'})
        self.assertEquals(content, '{"key": "value"}')
        self.assertEquals(content_type, 'application/json')

    def test_time(self):
        self.do(self.dt.time(), self.value(self.dt_expect.split('T')[1]))

    def test_timedelta(self):
        self.do(self.td, self.value(86402.000003))

    def test_tuple(self):
        self.do(
            (self.dt,),
            [self.dt_expect]
        )

    def test_unserializable(self):
        self.assertRaises(TypeError, self.serializer.convert, object())

    def value(self, val):
        return val

class SerializerJSONTest(SerializerConvertTest):
    def do(self, obj, expect):
        self.assertEquals(expect, self.serializer.to_json(obj))

    def setUp(self):
        self.serializer = Serializer()

    def test_dict(self):
        self.do(
            {'key': self.dt},
            '{"key": "%s"}' % self.dt_expect
        )

    def test_list(self):
        self.do(
            [self.dt],
            '["%s"]' % self.dt_expect
        )

    def test_tuple(self):
        self.do(
            (self.dt,),
            '["%s"]' % self.dt_expect
        )

    def test_unserializable(self):
        self.assertRaises(TypeError, self.serializer.to_json, object())

    def value(self, val):
        if isinstance(val, basestring):
            return '"%s"' % val
        else:
            return str(val)

class SerializerSerializeTest(TestCaseNoDB):
    def setUp(self):
        self.dt = SerializerConvertTest.dt
        self.dt_expect = SerializerConvertTest.dt_expect
        self.serializer = Serializer()

        self.data = {'key': self.dt}

    def test_application_json(self):
        content, content_type = \
            self.serializer.serialize(self.data, 'application/json')
        self.assertEquals(content_type, 'application/json')
        self.assertEquals(
            content,
            '{"key": "%s"}' % self.dt_expect
        )

    def test_application_json_indent(self):
        content, content_type = \
            self.serializer.serialize(self.data, 'application/json; indent=4')
        self.assertEquals(content_type, 'application/json')
        self.assertEquals(
            content,
            '{\n    "key": "%s"\n}' % self.dt_expect
        )

    def test_application_json_indent_invalid(self):
        content, content_type = \
            self.serializer.serialize(self.data, 'application/json; indent=a')
        self.assertEquals(content_type, 'application/json')
        self.assertEquals(
            content,
            '{"key": "%s"}' % self.dt_expect
        )

    def test_application_json_q(self):
        content, content_type = \
            self.serializer.serialize(self.data, 'application/json; q=0.5')
        self.assertEquals(content_type, 'application/json')
        self.assertEquals(
            content,
            '{"key": "%s"}' % self.dt_expect
        )

    def test_default(self):
        content, content_type = \
            self.serializer.serialize(self.data)
        self.assertEquals(content_type, self.serializer.default_content_type)
        self.assertEquals(
            content,
            '{"key": "%s"}' % self.dt_expect
        )

    def test_unsupported(self):
        self.assertRaises(
            self.serializer.Unsupported,
            self.serializer.get_format,
            'unsupported/content-type'
        )

class SerializerDeserializeTest(TestCaseNoDB):
    def setUp(self):
        self.data = {'key': 'value'}
        self.serializer = Serializer()

    def test_application_json(self):
        self.assertEquals(
            self.data,
            self.serializer.deserialize('{"key": "value"}', 'application/json')
        )

    def test_application_json_indent(self):
        self.assertEquals(
            self.data,
            self.serializer \
                .deserialize('{"key": "value"}', 'application/json; indent=4')
        )

    def test_invalid_data(self):
        for content_type in self.serializer.content_types.keys():
            if content_type.startswith('multipart/'):
                continue
            self.assertRaises(
                ValueError,
                self.serializer.deserialize,
                'invalid body data',
                content_type
            )

    def test_invalid_multipart_boundary(self):
        data = 'data'
        boundary = '\xffinvalid boundary'
        parsed = urlparse('/path/')
        environ = self.client._base_environ(**{
            'CONTENT_TYPE': 'multipart/form-data; boundary=%s' % boundary,
            'CONTENT_LENGTH': len(data),
            'PATH_INFO': self.client._get_path(parsed),
            'QUERY_STRING': parsed[4],
            'REQUEST_METHOD': 'POST',
            'wsgi.input': FakePayload(data),
        })
        request = WSGIRequest(environ)

        for content_type in self.serializer.content_types.keys():
            if not content_type.startswith('multipart/'):
                continue
            self.assertRaises(
                ValueError,
                self.serializer.deserialize_request,
                request,
                request.META['CONTENT_TYPE']
            )

    def test_invalid_multipart_content_length(self):
        data = 'data'
        boundary = 'boundary'
        parsed = urlparse('/path/')
        environ = self.client._base_environ(**{
            'CONTENT_TYPE': 'multipart/form-data; boundary=%s' % boundary,
            'CONTENT_LENGTH': -1,
            'PATH_INFO': self.client._get_path(parsed),
            'QUERY_STRING': parsed[4],
            'REQUEST_METHOD': 'POST',
            'wsgi.input': FakePayload(data),
        })
        request = WSGIRequest(environ)

        for content_type in self.serializer.content_types.keys():
            if not content_type.startswith('multipart/'):
                continue
            self.assertRaises(
                ValueError,
                self.serializer.deserialize_request,
                request,
                request.META['CONTENT_TYPE']
            )

class SerializerFormatTest(TestCaseNoDB):
    def setUp(self):
        self.serializer = Serializer()

    def test_get_content_type_json(self):
        self.assertEquals(
            self.serializer.get_content_type('json'),
            'application/json'
        )
