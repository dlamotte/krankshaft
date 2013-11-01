class KrankshaftError(Exception):
    pass

class Abort(KrankshaftError):
    def __init__(self, response):
        self.response = response

class InvalidDispatchOptions(KrankshaftError):
    pass
