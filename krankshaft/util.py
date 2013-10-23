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

def kw_as_header(kw):
    '''kw_as_header('Content_Type') -> Content-Type

    Convert a Python Keyword argument name to a valid Header name.  Since some
    characters used in headers are not valid Python Keyword characters, this
    serves as a translation for convenience.
    '''
    return kw.replace('_', '-')
