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
    def __str__(self):
        return '\n'.join([
            self.args[0],
            '\n'.join([
                '%s: %s' % (self.__class__.__name__, arg)
                for arg in self.args[1:]
            ]),
        ])
