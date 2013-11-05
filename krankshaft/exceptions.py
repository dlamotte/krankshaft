class KrankshaftError(Exception):
    pass

class Abort(KrankshaftError):
    def __init__(self, response):
        self.response = response

class DispatchInvalidOptions(KrankshaftError):
    pass

class QueryInvalidOptions(KrankshaftError):
    pass

class QueryIssues(KrankshaftError):
    pass

class ExpectedIssue(KrankshaftError):
    pass

class ValueIssue(KrankshaftError):
    pass
