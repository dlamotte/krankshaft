def kw_as_header(kw):
    '''kw_as_header('Content_Type') -> Content-Type

    Convert a Python Keyword argument name to a valid Header name.  Since some
    characters used in headers are not valid Python Keyword characters, this
    serves as a translation for convenience.
    '''
    return kw.replace('_', '-')
