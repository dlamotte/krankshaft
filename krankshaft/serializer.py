from .exceptions import KrankshaftError
from collections import namedtuple
from cStringIO import StringIO
from datetime import datetime, date, time, timedelta
from functools import partial
import decimal
import json
import mimeparse
import urlparse

# TODO: Accept: */* dumps: no method to_urlencoded
#       maybe only consider serializers we have a method for?
# TODO use 406 Not Acceptable in case where we cannot serialize

class Serializer(object):
    '''
    Create a serializer to register serializable's against.  Understands how to
    serialize objects to a data representation.
    '''
    class SerializableExists(KrankshaftError): pass
    class Unsupported(KrankshaftError): pass

    SerializedContainer = \
        namedtuple('SerializedContainer', ['data', 'content_type'])

    content_types = {
        'application/json': 'json',
        'application/x-www-form-urlencoded': 'urlencoded',
        'multipart/form-data': 'multipart_form_data',
    }
    default_content_type = 'application/json'
    format_to_content_type = {
        'json': 'application/json',
    }

    dict_like_iterables = (
        dict,
    )
    list_like_iterables = (
        list,
        tuple,
    )
    primitive_classes = (
        int,
        long,
        float,
        basestring,
    )
    primitive_values = (
        None,
        True,
        False,
    )

    def __init__(self, default_content_type=None):
        if default_content_type:
            self.default_content_type = default_content_type

        self.complex = (
            # date/time
            (date, self.convert_datetime_ish),
            (datetime, self.convert_datetime_ish),
            (time, self.convert_datetime_ish),
            (timedelta, self.convert_timedelta),

            # other
            (decimal.Decimal, self.convert_decimal),
        )

        self.registered = {}

    def convert(self, obj, **opts):
        '''convert(obj) -> serializable

        Convert an arbitrary object into something serializable.

        Raises TypeError if unable to convert.
        '''
        if obj in self.primitive_values:
            return obj

        elif isinstance(obj, self.primitive_classes):
            return obj

        elif isinstance(obj, self.list_like_iterables):
            return [
                self.convert(subobj, **opts)
                for subobj in obj
            ]

        elif isinstance(obj, self.dict_like_iterables):
            return {
                self.convert(key, **opts): self.convert(val, **opts)
                for key, val in obj.items()
            }

        for klass, method in self.complex:
            if isinstance(obj, klass):
                return method(obj)

        for klass in (obj.__class__, ) + getattr(obj, '__bases__', ()):
            if klass in self.registered:
                serializable = self.registered[klass](obj)
                return serializable.convert(**opts)

        return self.convert_unknown(obj)

    def convert_datetime_ish(self, obj):
        return obj.isoformat()

    def convert_decimal(self, obj):
        return str(obj)

    def convert_timedelta(self, obj):
        return obj.total_seconds()

    def convert_unknown(self, obj):
        raise TypeError(repr(obj) + ' is not serializable')

    def deserialize(self, body, content_type, **opts):
        '''deserialize(body, content_type) -> data

        Deserialize a request body into a data-structure.
        '''
        method = getattr(self, 'from_%s' % self.get_format(content_type)[1])
        return method(body, content_type=content_type, **opts)

    def deserialize_request(self, request, content_type, **opts):
        format = self.get_format(content_type)[1]
        if format == 'multipart_form_data':
            return self.from_multipart_form_data(request, **opts)
        else:
            return self.deserialize(request.body, content_type, **opts)

    def from_urlencoded(self, body, **opts):
        data = urlparse.parse_qs(
            body,
            keep_blank_values=True,
            strict_parsing=True
        )
        return {
            key: value[-1]
            for key, value in data.iteritems()
        }

    def from_multipart_form_data(self, request, **opts):
        from django.utils.datastructures import MultiValueDict

        # XXX not thrilled with this, but django itself uses an 'expect:' clause
        # to handle errors in this... so this is only slightly better...
        try:
            if hasattr(request, '_body'):
                data = StringIO(request._body)
            else:
                data = request
            post, files = request.parse_file_upload(request.META, data)
            data = MultiValueDict()
            data.update(post)
            data.update(files)
            return {
                key: value
                for key, value in data.iteritems()
            }
        except Exception, e:
            raise ValueError(str(e))

    def from_json(self, body, **opts):
        return json.loads(body)

    def get_content_type(self, format):
        '''get_content_type(format) -> content_type

        Look up a content type from a format.
        '''
        return self.format_to_content_type[format]

    def get_format(self, accept):
        '''get_format(content_type) -> format

        Find a suitable format from a content type.
        '''
        # ensure default_content_type is last so that accept = '*/*' picks up
        # our default_content_type
        content_types = self.content_types.keys()
        content_types.sort(key=lambda x: x == self.default_content_type)

        content_type = mimeparse.best_match(content_types, accept)
        if not content_type:
            raise self.Unsupported(accept)
        return content_type, self.content_types[content_type]

    def register(self, serializable):
        '''register(MyObject, SerializableMyObject(MyObject))

        Register a Serializable to use with a custom object.
        '''
        if serializable.klass in self.registered:
            raise self.SerializableExists('%s = %s' % (
                repr(serializable.klass),
                repr(self.registered[serializable.klass])
            ))
        self.registered[serializable.klass] = serializable

    def serialize(self, obj, accept=None, **opts):
        '''serialize(obj) -> content, content_type

        Serialize an object to text.
        '''
        accept = accept or self.default_content_type
        content_type, format = self.get_format(accept)
        method = getattr(self, 'to_%s' % format)

        # ugly hack to get the params to the header part out
        try:
            accept = [
                part
                for part in accept.split(',')
                if part.startswith(content_type)
            ][0]
        except IndexError:
            # '*/*' case
            accept = content_type

        params = mimeparse.parse_mime_type(accept)[2]
        for key, value in params.items():
            opts.setdefault(key, value)

        return self.SerializedContainer(method(obj, **opts), content_type)

    def to_json(self, obj, **opts):
        convert = self.convert
        dopts = {}

        if 'indent' in opts:
            try:
                dopts['indent'] = int(opts.pop('indent'))
            except ValueError:
                pass

        if opts:
            convert = partial(convert, **opts)

        return json.dumps(obj, default=convert, **dopts)
