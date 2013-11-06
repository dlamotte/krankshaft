from .exceptions import InvalidOptions

class Annotate(object):
    '''
    with Annotate(request, 'auth', Auth(request)):
        ...

    Helper object to help with creating and cleaning up annotations on other
    objects.
    '''
    def __init__(self, obj, annotations):
        self.obj = obj
        self.annotations = annotations

    def __enter__(self):
        for name, value in self.annotations.iteritems():
            setattr(self.obj, name, value)

    def __exit__(self, exc_type, exc_value, traceback):
        for name, value in self.annotations.iteritems():
            delattr(self.obj, name)

def defaults(opts, *defaults):
    '''defaults({'a': 'a'}, {'a': 'b', 'b': 'b'}) -> {'a': 'a', 'b': 'b'}

    Set defaults in a dictionary.
    '''
    for default in defaults:
        for key, value in default.iteritems():
            if key not in opts:
                opts[key] = value
    return opts

def kw_as_header(kw):
    '''kw_as_header('Content_Type') -> Content-Type

    Convert a Python Keyword argument name to a valid Header name.  Since some
    characters used in headers are not valid Python Keyword characters, this
    serves as a translation for convenience.
    '''
    return kw.replace('_', '-')

def valid(opts, allowed):
    '''valid({'key': 'value'}, 'opt') -> raise InvalidOptions

    Validate that a dictionary has only valid options/keys.
    '''
    allowed = set(allowed)
    used = set(opts.keys())
    invalid = used - allowed
    if invalid:
        raise InvalidOptions(', '.join(sorted(list(invalid))))
    return opts
