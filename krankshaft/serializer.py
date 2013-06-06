from .exceptions import KrankshaftError
from datetime import datetime, date, time, timedelta
from functools import partial
import decimal
import json
import mimeparse

class Serializer(object):
    '''
    Create a serializer to register serializable's against.  Understands how to
    serialize objects to a data representation.
    '''
    class SerializableExists(KrankshaftError): pass

    content_types = {
        'application/json': 'json',
    }
    default_content_type = 'application/json'

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

        for klass in (obj.__class__, ) + obj.__bases__:
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

    def deserialize(self, body, content_type):
        '''deserialize(body, content_type) -> data

        Deserialize a request body into a data-structure.
        '''
        method = getattr(self, 'from_%s' % self.get_format(content_type))
        return method(body)

    def from_json(self, body):
        return json.loads(body)

    def get_format(self, accept):
        '''get_format(content_type) -> format

        Find a suitable format from a content type.
        '''
        content_type = mimeparse.best_match(self.content_types.keys(), accept)
        return self.content_types[content_type]

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
        method = getattr(self, 'to_%s' % self.get_format(accept))

        params = mimeparse.parse_mime_type(accept)[2]
        for key, value in params.items():
            opts.setdefault(key, value)

        return method(obj, **opts)

    def to_json(self, obj, **opts):
        convert = self.convert
        if opts:
            convert = partial(convert, **opts)

        dopts = {}
        if 'indent' in opts:
            try:
                dopts['indent'] = int(opts.pop('indent'))
            except ValueError:
                pass

        return json.dumps(obj, default=convert, **dopts)
