'''
valid - helper routines for validating/cleaning data from untrusted inputs

The pattern and reason for this module are quite simple.  Make it easy to
define an expected structure and clean incoming data based on that structure.

To write a validator, you need only be able to write a function that raises
ValueError with a valuable message on data that is not valid.  Then using
expect(), you can reuse that function to properly valid more complex data
structures.  If a value is valid, but needs transformation (ie: '1' -> 1,
convert from string 1 to integer 1) simply return the cleaned value from the
function.

Ideally, you can simply use something like this:

    from krankshaft import valid

    try:
        clean = api.expect(
            {
                'count': valid.int,
                'name': valid.str_max_length(100),
                'text': valid.str,
            },
            data
        )
    except api.ValueIssue as exc:
        print str(exc)

The above validates many things:

- that data has only 3 keys in the top-level dictionary
- that the values of each of those keys comply with their given validator

The clean dictionary (because you expected a dictionary) is then clean and ready
to be used by your program safely.

A ValueIssue will be raised with the ValueError message of each offending value
in data. (it does not stop at the first offending value)
'''

from . import util
from .exceptions import ExpectedIssue, KrankshaftError, ValueIssue

class Expecter(object):
    '''
    The expect() runtime and handling of specific data structures.

    An Expecter simply contains some configuration options along with methods
    to handle specific data structures (dict, list).  This can be expanded or
    changed via subclasses which is about the only reason this exists
    as a class vs a function.

    Some specific details about how this implementation works.  The expect()
    function is the standard entry point for general users.

        from krankshaft import valid
        expecter = valid.Expecter()
        expecter.expect(valid.int, '1') # returns integer 1

    The expect function works recursively to dive through data structures so
    that the simple validators can be used within them and offer a way to
    define the expected data structure exactly.

    For dictionaries:

        expecter.expect({'key': valid.int}, {'key': '1'}) # returns {'key': 1}

    As you can see, the same valid.int validator is being used, but this time
    within a dict data structure.  The expect routine handles anything not
    callable (`hasattr(obj, '__call__')`) as a data structure that needs to
    be handled.  In the dict case, it iterates over the keys shared between
    the expected dict and the given data dict and applies the expected dict
    value (the validator) to the data dict value.  If a failure occurs for
    a specific key, the routine keeps track of the error but continues on to
    the next key.  In this way, all errors will be discovered versus only the
    first error.

    When errors are found, a `expecter.ValueIssue` is raised with all errors
    encountered.

    The expect dictionary logic is by default very strict about what keys exist
    in the given data.  By default, the keys in the given data must match
    exactly those in the expected dictionary.  You can lift those restrictions
    in a few ways.

        expecter = valid.Expecter(strict_dict=False)
        expecter = valid.Expecter(ignore_extra_keys=True)
        expecter = valid.Expecter(ignore_missing_keys=True)

        expecter.expect({...}, {...}, strict_dict=False)
        expecter.expect({...}, {...}, ignore_extra_keys=True)
        expecter.expect({...}, {...}, ignore_missing_keys=True)

    Either you configure the `Expecter` to handle dictionaries that why be
    default, or you override the option at the call site.  The `strict_dict`
    option is a quick way to make both extra/missing keys True or False.  So
    `strict_dict=False` would make `ignore_extra_keys` and `ignore_missing_keys`
    both True.

    Lists get some special non-intuitive (at first) treatment compared to
    dictionaries.  Let's start with the most obvious case:

        expecter.expect([valid.int, valid.int], ['1', 2]) # returns [1, 2]

    Makes sense right?  `expect()` iterates over the list and applies the
    validator to each matching member of the given data list.  And as you'd
    expect, if the given data list had more or less members than the expected
    list, it will blow up.

    Another list case, but a little more confusing:

        expecter.expect([], [1, 'a', None]) # returns [1, 'a', None]

    An empty list accepts all lists, since no validator is given.  An empty
    list is accepted as well.

    The last list case which may be the most confusing at first is this:

        expecter.expect([valid.int], [1, '2']) # returns [1, 2]

    A single validator in a list is special in that that validator is applied
    to all given members of the given data list.  It accepts zero or more
    values in the given data list.  It makes it easy to validate a list of
    homegenus elements which is very typical.

    This makes it a bit tough to validate a list of one or more members.  But
    there is a special validator for that.  The `list_x_or_more` is the
    validator you want:

        expecter.expect(valid.list_x_or_more(valid.int, 1), ['1', 2])

    The above will guarantee at least one member exists and that all members
    are `valid.int`s.

    As for tuple's, they behave just like lists.
    '''
    ExpectedIssue = ExpectedIssue
    ValueIssue = ValueIssue

    defaults = {
        'ignore_extra_keys': False,
        'ignore_missing_keys': False,
    }

    def __init__(self, **opts):
        self.opts = self.options(opts, self.defaults)

    def depthstr(self, depth):
        '''
        An internal helper to format the depth list to be user readable.
        '''
        depthstr = 'depth@root'
        if depth:
            depthstr = 'depth@' + '.'.join(depth)

        return depthstr

    def expect(self, expected, data, depth=None, **opts):
        '''expect({'key': valid.int}, {'key': '1'}) -> {'key': 1}

        Clean and validate a given data structure using an expected structure.

        You may pass valid options directly here via opts.
        '''
        if depth is None:
            opts = self.options(opts, self.opts)

        depth = depth or []

        if hasattr(expected, '__call__'):
            try:
                if getattr(expected, 'needs_expecter', False):
                    data = expected(self, data,
                        depth=depth + [expected.__name__],
                        opts=opts
                    )

                else:
                    data = expected(data)

            except ValueError as exc:
                raise self.ValueIssue(
                    '%s: expected %r, saw %r with ValueError: %s' % (
                        self.depthstr(depth),
                        expected,
                        data,
                        str(exc),
                    )
                )

            else:
                return data

        if expected.__class__ is not data.__class__:
            raise self.ValueIssue('%s: expected %r, saw %r' % (
                self.depthstr(depth),
                expected.__class__,
                data.__class__,
            ))

        method = getattr(self, 'expect_' + expected.__class__.__name__, None)
        if not method:
            raise self.ExpectedIssue(
                'Your expected data structure is unhandled for type: %s'
                % expected.__class__
            )

        return method(expected, data,
            depth=depth + [expected.__class__.__name__],
            opts=opts
        )

    def expect_dict(self, expected, data, depth, opts):
        '''
        Dictionary data structure handling with expect().

        You probably dont want to use this directly.
        '''
        expected_keys = set(expected.keys())
        data_keys = set(data.keys())
        clean = {}

        errors = []
        if (
            not (opts['ignore_extra_keys'] and opts['ignore_missing_keys'])
            and expected_keys != data_keys
        ):
            extra_keys = data_keys - expected_keys
            missing_keys = expected_keys - data_keys
            if not opts['ignore_extra_keys'] and extra_keys:
                errors.append('%s: Extra keys, %s' % (
                    self.depthstr(depth),
                    ', '.join(list(extra_keys)),
                ))

            if not opts['ignore_missing_keys'] and missing_keys:
                errors.append('%s: Missing keys: %s' % (
                    self.depthstr(depth),
                    ', '.join(list(missing_keys)),
                ))

        for key in (expected_keys & data_keys):
            try:
                clean[key] = self.expect(expected[key], data[key],
                    depth=depth + [key]
                )

            except self.ValueIssue as exc:
                errors.extend(exc.args)

        if errors:
            raise self.ValueIssue(*errors)

        return clean

    def expect_list(self, expected, data, depth, opts):
        '''
        List data structure handling with expect().

        You probably dont want to use this directly.
        '''
        clean = []
        errors = []

        if len(expected) == 0:
            return data[:]

        elif len(expected) == 1:
            for i, value in enumerate(data):
                try:
                    clean.append(self.expect(expected[0], value,
                        depth=depth + [str(i)]
                    ))
                except self.ValueIssue as exc:
                    errors.extend(exc.args)

        elif len(expected) == len(data):
            for i, (cleaner, d) in enumerate(zip(expected, data)):
                try:
                    clean.append(self.expect(cleaner, d,
                        depth=depth + [str(i)]
                    ))
                except self.ValueIssue as exc:
                    errors.extend(exc.args)

        else:
            errors.append('%s: Expected list of length %s, saw %s' % (
                self.depthstr(depth),
                len(expected),
                len(data),
            ))

        if errors:
            raise self.ValueIssue(*errors)

        return clean

    def expect_tuple(self, expected, data, depth, opts):
        '''
        Tuple data structure handling with expect().

        You probably dont want to use this directly.
        '''
        return tuple(self.expect_list(expected, data, depth, opts))

    def options(self, opts, defaults):
        '''
        Validate and set default options.
        '''
        return util.valid(
            util.defaults(self.shortcuts(opts), defaults),
            self.defaults.keys()
        )

    def shortcuts(self, opts):
        '''
        Handle option shortcuts like `strict_dict`.
        '''
        if 'strict_dict' in opts:
            strict_dict = opts.pop('strict_dict')
            opts['ignore_extra_keys'] = not strict_dict
            opts['ignore_missing_keys'] = not strict_dict
        return opts

#
# validator function markers
#

def expecterfunction(function):
    '''
    Expose the expecter to the validator.

        @expecterfunction
        def validator(expecter, data, depth, opts):
            ...

    '''
    function.needs_expecter = True
    return function

#
# validator helpers
#

def or_none(validator):
    '''or_none(__builtins__.int) -> int_or_none_validator

    Given a function that returns ValueError when the given value is invalid,
    wrap it in such a way that it will properly handle being given None and
    return None.
    '''
    new = lambda value: None if value is None else validator(value)
    new.__name__ = validator.__name__ + '_or_none'
    return new

def no_none(validator):
    '''or_none(__builtins__.int) -> int_no_none_validator

    Given a function that returns ValueError when the given value is invalid,
    wrap it in such a way that it will properly handle being given None and
    raise ValueError.
    '''
    def new(value):
        if value is None:
            raise ValueError('%s does not accept None' % validator.__name__)
        return validator(value)
    new.__name__ = validator.__name__ + '_no_none'
    return new

#
# validator factories
#

def range(validator, low, high):
    '''range(valid.int, 0, 10) -> int_range_0_to_10

    Wrap validator that also validates the returned value lies within a given
    range.
    '''
    def range_validator(value):
        value = validator(value)
        if value is not None and not (low <= value <= high):
            raise ValueError(
                'The value is not within the range %s <= %s <= %s'
                % (low, value, high)
            )
        return value

    range_validator.__name__ = validator.__name__ + '_range_%s_to_%s' \
        % (low, high)

    return range_validator

def list_x_or_more(validator, n):
    '''list_x_or_more(valid.int, 1) -> list_1_or_more_int

    Wrap a validator that also validates the returned list has one or more
    members.
    '''
    if n < 1:
        raise KrankshaftError(
            'list_x_or_more only accepts values >= 1, not %s' % n
        )

    @expecterfunction
    def list_x_or_more_validator(expecter, data, depth, opts):
        clean = None
        errors = []
        try:
            clean = expecter.expect([validator], data, depth=depth, **opts)
        except expecter.ValueIssue as exc:
            errors.extend(exc.args)

        if clean is not None and len(clean) < n:
            errors.append(
                '%s: Expected list with %s or more elements, saw %s'
                % (expecter.depthstr(depth), n, len(data))
            )

        if errors:
            raise expecter.ValueIssue(*errors)

        return clean

    list_x_or_more_validator.__name__ = 'list_%s_or_more_%s' % (
        n, validator.__name__
    )
    return list_x_or_more_validator

def max_length(validator, n):
    '''max_length(valid.str, 20) -> str_max_length_20

    Wrap a validator that also validates the returned value is less than the
    given max length.
    '''
    def max_length_validator(value):
        value = validator(value)
        if value is not None and len(value) > n:
            raise ValueError(
                'The value is greater than max length %s: %s' % (n, len(value))
            )
        return value

    max_length_validator.__name__ = '%s_max_length_%s' \
        % (validator.__name__, n)

    return max_length_validator

int_range = lambda low, high: range(int, low, high)
int_or_none_range = lambda low, high: range(int_or_none, low, high)

str_max_length = lambda n: max_length(str, n)
str_or_none_max_length = lambda n: max_length(str_or_none, n)

unicode_max_length = lambda n: max_length(unicode, n)
unicode_or_none_max_length = lambda n: max_length(unicode_or_none, n)

#
# validators
#

int = no_none(int)
int_or_none = or_none(int)

str = no_none(str)
str_or_none = or_none(str)

unicode = no_none(unicode)
unicode_or_none = or_none(unicode)

# TODO helpful validators
#   - email
#   - every django field needs a validator
