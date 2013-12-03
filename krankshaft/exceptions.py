class KrankshaftError(Exception):
    pass

class KrankshaftErrorList(KrankshaftError):
    def __init__(self, errors):
        self.errors = errors

    def __str__(self):
        from pprint import pformat
        msg = pformat(self.errors)
        if '\n' in msg:
            msg = '\n' + msg
        return msg

class Abort(KrankshaftError):
    def __init__(self, response):
        self.response = response

class ExpectedIssue(KrankshaftError):
    pass

class InvalidOptions(KrankshaftError):
    pass

class QueryIssues(KrankshaftErrorList):
    pass

class ResolveError(KrankshaftError):
    pass

class ValueIssue(KrankshaftErrorList):
    pass
