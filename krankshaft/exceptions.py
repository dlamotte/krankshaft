class KrankshaftError(Exception):
    pass

class Abort(KrankshaftError):
    def __init__(self, response):
        self.response = response

class ExpectedIssue(KrankshaftError):
    pass

class InvalidOptions(KrankshaftError):
    pass

class QueryIssues(KrankshaftError):
    pass

class ResolveError(KrankshaftError):
    pass

class ValueIssue(KrankshaftError):
    def __init__(self, errors):
        self.errors = errors

    def __str__(self):
        from pprint import pformat
        msg = pformat(self.errors)
        if '\n' in msg:
            msg = '\n' + msg
        return msg
