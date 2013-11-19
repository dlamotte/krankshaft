'''
valid - helper routines for validating/cleaning data from untrusted inputs

The pattern and reason for this module are quite simple.  Make it easy to
define an expected structure and clean incoming data based on that structure.

To write a validator, you need only be able to write a function that raises
ValueError with a valuable message on data that is not valid.  Then using
expect(), you can reuse that function to properly validate more complex data
structures.  If a value is valid, but needs transformation (ie: '1' -> 1,
convert from string 1 to integer 1) simply return the cleaned value from the
function.  A simple validator looks like this:

    def validator(value, expect):
        ... raise ValueError if there are issues
        ... if you need to recall expect on a new structure, then:
        ...     expect(expected, newvalue)
        return value

Ideally, you can simply use something like this:

    from krankshaft import valid

    try:
        clean = api.expect(
            {
                'count': valid.int,
                'name': valid.string_max_length(100),
                'text': valid.string,
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
from django.core import validators
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import models
from django.template.defaultfilters import slugify
from django.utils import dateparse

class ExpecterHelper(object):
    '''
    This helper encapsulates the ability to recursively call expect from within
    a validator.

    Meant to be used exactly like the except function but allows access to
    the entire expecter.

        expect = ExpecterHelper(self, opts)
        expect(expected, data)
    '''
    def __init__(self, expecter, opts):
        self.expecter = expecter
        self.opts = opts

    def __call__(self, expected, data):
        return self.expect(expected, data, **self.opts)

    def __getattr__(self, name):
        return getattr(self.expecter, name)

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
    there is a special validator for that.  The `list_n_or_more` is the
    validator you want:

        expecter.expect(valid.list_n_or_more(valid.int, 1), ['1', 2])

    The above will guarantee at least one member exists and that all members
    are `valid.int`s.

    As for tuple's, they behave just like lists.
    '''
    ExpectedIssue = ExpectedIssue
    ExpecterHelper = ExpecterHelper
    ValueIssue = ValueIssue

    defaults = {
        'ignore_extra_keys': False,
        'ignore_missing_keys': False,
    }

    field_to_validator = {} # setup at end of module

    def __init__(self, **opts):
        self.opts = self.options(opts, self.defaults)

    def expect(self, expected, data, **opts):
        '''expect({'key': valid.int}, {'key': '1'}) -> {'key': 1}

        Clean and validate a given data structure using an expected structure.

        You may pass valid options directly here via opts.
        '''
        opts = self.options(opts, self.opts)

        if hasattr(expected, '__call__'):
            try:
                data = expected(data, self.ExpecterHelper(self, opts))

            except ValueError as exc:
                raise self.ValueIssue([self.format_exc(exc)])

            else:
                return data

        if expected.__class__ is not data.__class__:
            raise self.ValueIssue([
                'Unexpected type, expected %s: %s'
                % (expected.__class__, data.__class__)
            ])

        method = getattr(self, 'expect_' + expected.__class__.__name__, None)
        if not method:
            raise self.ExpectedIssue(
                'Your expected data structure is unhandled for type: %s'
                % expected.__class__
            )

        return method(expected, data, opts=opts)

    def expect_dict(self, expected, data, opts):
        '''
        Dictionary data structure handling with expect().

        You probably dont want to use this directly.
        '''
        clean = {}
        data_keys = set(data.keys())
        errors = {}
        expected_keys = set(expected.keys())

        if (
            not (opts['ignore_extra_keys'] and opts['ignore_missing_keys'])
            and expected_keys != data_keys
        ):
            extra_keys = data_keys - expected_keys
            missing_keys = expected_keys - data_keys
            if not opts['ignore_extra_keys'] and extra_keys:
                errors.setdefault('__nonkeyerrors__', []) \
                    .append('Extra keys: %s' % ', '.join(list(extra_keys)))

            if not opts['ignore_missing_keys'] and missing_keys:
                errors.setdefault('__nonkeyerrors__', []) \
                    .append('Missing keys: %s' % ', '.join(list(missing_keys)))

        for key in (expected_keys & data_keys):
            try:
                clean[key] = self.expect(expected[key], data[key], **opts)

            except self.ValueIssue as exc:
                errors[key] = exc.errors

        if errors:
            raise self.ValueIssue(errors)

        return clean

    def expect_list(self, expected, data, opts):
        '''
        List data structure handling with expect().

        You probably dont want to use this directly.
        '''
        clean = []
        errors = {}

        if len(expected) == 0:
            return data[:]

        elif len(expected) == 1:
            for i, value in enumerate(data):
                try:
                    clean.append(self.expect(expected[0], value, **opts))
                except self.ValueIssue as exc:
                    errors[i] = exc.errors

        elif len(expected) == len(data):
            for i, (cleaner, d) in enumerate(zip(expected, data)):
                try:
                    clean.append(self.expect(cleaner, d, **opts))
                except self.ValueIssue as exc:
                    errors[i] = exc.errors

        else:
            errors['__nonindexerrors__'] = [
                'Expected list of length %s, saw %s' % (
                    len(expected),
                    len(data),
                )
            ]

        if errors:
            raise self.ValueIssue(errors)

        return clean

    def expect_tuple(self, expected, data, opts):
        '''
        Tuple data structure handling with expect().

        You probably dont want to use this directly.
        '''
        return tuple(self.expect_list(expected, data, opts))

    def format_exc(self, exc):
        '''format_exc(exception) -> '...'

        Format an exception to be encoded into the error data structure.
        '''
        return str(exc)

    def from_field(self, field):
        '''from_field(model.field.field) -> validator or expected data structure

        Return a validator or an expected data structure (passable to expect())
        given a django model field.
        '''
        if field.__class__ in (
            models.ForeignKey,
            models.OneToOneField,
            models.ManyToManyField
        ):
            other_field = field
            while hasattr(other_field, 'rel') and other_field.rel:
                other_field = other_field.rel.get_related_field()
            validator = self.field_to_validator[other_field.__class__]

        else:
            validator = self.field_to_validator[field.__class__]

        if not field.null:
            validator = no_none(validator)

        if field.choices:
            validator = choice(validator, tuple([
                value
                for value, display in field.choices
            ]))

        if hasattr(field, 'max_length') and field.max_length:
            validator = max_length(validator, field.max_length)

        if field.validators:
            validator = django_validator(validator, *field.validators)

        if field.__class__ is models.ManyToManyField:
            if field.blank:
                return [validator]

            else:
                return list_n_or_more(validator, 1)

        return validator

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
# validator helpers
#

def no_none(validator):
    '''or_none(__builtins__['int']) -> int_no_none_validator

    Given a function that returns ValueError when the given value is invalid,
    wrap it in such a way that it will properly handle being given None and
    raise ValueError.
    '''
    def no_none_validator(value, expect):
        if value is None:
            raise ValueError('%s does not accept None' % validator.__name__)
        return validator(value, expect)
    return wraps(no_none_validator, validator, '_no_none')

def or_none(validator):
    '''or_none(__builtins__['int']) -> int_or_none_validator

    Given a function that returns ValueError when the given value is invalid,
    wrap it in such a way that it will properly handle being given None and
    return None.
    '''
    def or_none_validator(value, expect):
        return None if value is None else validator(value, expect)
    return wraps(or_none_validator, validator, '_or_none')

def primitive(validator):
    '''primitive(int) -> int

    Upgrade a primitive validator to a validator that accepts the expect
    argument.
    '''
    def primitive_validator(value, expect):
        return validator(value)

    return wraps(primitive_validator, validator)

def wraps(wrapper, wrapped, suffix='', prefix=''):
    '''wraps(wrapper, validator)

    Wrap a validator in another validator.
    '''
    wrapper.__name__ = prefix + wrapped.__name__ + suffix

    return wrapper

#
# validator factories
#

def choice(validator, choices):
    '''choice(valid.string, ['a', 'b', 'c']) -> string_choices

    Wrap validator that also validates the returned value is in the list of
    valid choices.
    '''
    def choice_validator(value, expect):
        value = validator(value, expect)
        if value is not None and value not in choices:
            raise ValueError('The value is not a valid choice: %s' % value)
        return value

    return wraps(choice_validator, validator, '_choices')

def csv(validator, separator=','):
    '''csv(valid.int) -> int_csv

    Wrap validator so that it validates a list separated by commas.
    '''
    def csv_validator(data, expect):
        data = string_or_none(data, expect)

        if data is not None:
            clean = expect(
                [validator],
                [member for member in data.split(',') if member],
            )
            return ','.join([
                str(member)
                for member in clean
            ])

        return data

    return wraps(csv_validator, validator, '_csv')

def django_validator(validator, *validators):
    '''django_validator(valid.string, *field.validators) -> django_validator

    Use django validators as extra validation to a value.
    '''
    def django_validator_validator(value, expect):
        value = validator(value, expect)

        if value is not None:
            for django_is_valid in validators:
                try:
                    django_is_valid(value)
                except ValidationError as exc:
                    raise ValueError(exc.messages[0])

        return value

    return wraps(django_validator_validator, validator, '_django_validator')

def list_n_or_more(validator, n):
    '''list_n_or_more(valid.int, 1) -> list_1_or_more_int

    Wrap a validator that also validates the returned list has one or more
    members.
    '''
    if n < 1:
        raise KrankshaftError(
            'list_n_or_more only accepts values >= 1, not %s' % n
        )

    def list_n_or_more_validator(data, expect):
        clean = None
        errors = {}
        try:
            clean = expect([validator], data)
        except expect.ValueIssue as exc:
            errors = exc.errors

        if clean is not None and len(clean) < n:
            errors.setdefault('__nonindexerrors__', []) \
                .append(
                    'Expected list with %s or more elements, saw %s'
                    % (n, len(data))
                )

        if errors:
            raise expect.ValueIssue(errors)

        return clean

    return wraps(list_n_or_more_validator, validator,
        prefix='list_%s_or_more_' % n
    )

def max_length(validator, n):
    '''max_length(valid.string, 20) -> string_max_length_20

    Wrap a validator that also validates the returned value is less than the
    given max length.
    '''
    def max_length_validator(value, expect):
        value = validator(value, expect)
        if value is not None and len(value) > n:
            raise ValueError(
                'The value is greater than max length %s: %s' % (n, len(value))
            )
        return value

    return wraps(max_length_validator, validator, '_max_length_%s' % n)

def range(validator, low, high):
    '''range(valid.int, 0, 10) -> int_range_0_to_10

    Wrap validator that also validates the returned value lies within a given
    range.

    You can create an unbounded range by using None as either bound.
    '''
    def range_validator(value, expect):
        value = validator(value, expect)
        if value is not None and not (
            low <= value <= high
            if low is not None and high is not None
            else low <= value if low is not None
            else value <= high
        ):
            raise ValueError(
                'The value is not within the range %s <= %s <= %s'
                % (low, value, high)
            )
        return value

    return wraps(range_validator, validator, '_range_%s_to_%s' % (low, high))

float_range = lambda low, high: range(float, low, high)
float_or_none_range = lambda low, high: range(float_or_none, low, high)

int_range = lambda low, high: range(int, low, high)
int_or_none_range = lambda low, high: range(int_or_none, low, high)

string_max_length = lambda n: max_length(string, n)
string_or_none_max_length = lambda n: max_length(string_or_none, n)

#
# primitive validators
#

float = no_none(primitive(__builtins__['float']))
float_or_none = or_none(primitive(__builtins__['float']))

int = no_none(primitive(__builtins__['int']))
int_csv = no_none(csv(int))
int_or_none = or_none(primitive(__builtins__['int']))
int_csv_or_none = csv(int)

def string_or_none(value, expect):
    if value is not None:
        if not isinstance(value, basestring):
            raise ValueError('Expected string, saw: %s' % type(value))

    return value
string = no_none(string_or_none)

#
# complex validators
#

def bool_or_none(value, expect):
    '''bool_or_none('yes') -> True

    Take a truthy/falsey string and make it a boolean.
    '''
    truthy = ('1', 'true', 'yes')
    def str_or_none_lower(value, expect):
        return str(value).lower() if value is not None else None
    value = choice(
        str_or_none_lower,
        ('0', 'false', 'no', 'null') + truthy
    )(value, expect)

    if value is None:
        return None
    else:
        return value in truthy
bool = no_none(bool_or_none)

def date_or_none(value, expect):
    value = string_or_none(value, expect)

    if value is not None:
        clean = dateparse.parse_date(value)
        if clean is None:
            raise ValueError('Could not parse date: %s' % value)
        value = clean

    return value
date = no_none(date_or_none)

def datetime_or_none(value, expect):
    value = string_or_none(value, expect)

    if value is not None:
        clean = dateparse.parse_datetime(value)
        if clean is None:
            raise ValueError('Could not parse datetime: %s' % value)
        value = clean

    return value
datetime = no_none(datetime_or_none)

def django_file_or_none(value, expect):
    if value is not None and not isinstance(value, File):
        raise ValueError('No django file found')
    return value
django_file = no_none(django_file_or_none)

def django_image_or_none(value, expect):
    value = django_file_or_none(value, expect)

    if value is not None:
        try:
            from PIL import Image
            image = Image.open(value)
            image.load()

            value.seek(0)

            image = Image.open(value)
            image.verify()

            value.seek(0)

        except Exception:
            raise ValueError('No valid django image (file) found')

    return value
django_image = no_none(django_image_or_none)

email = django_validator(string, validators.validate_email)
email_or_none = django_validator(string_or_none, validators.validate_email)

def slug_or_none(value, expect):
    value = string_or_none(value, expect)
    if value is not None:
        value = slugify(value)
    return value
slug = no_none(slug_or_none)

def time_or_none(value, expect):
    value = string_or_none(value, expect)

    if value is not None:
        clean = dateparse.parse_time(value)
        if clean is None:
            raise ValueError('Could not parse time: %s' % value)
        value = clean

    return value
time = no_none(time_or_none)


Expecter.field_to_validator = {
    models.AutoField                    : int_or_none_range(1, 2147483647),
    models.BigIntegerField              : int_or_none_range(-9223372036854775808, 9223372036854775807),
    models.BooleanField                 : bool_or_none,
    models.CharField                    : string_or_none,
    models.CommaSeparatedIntegerField   : int_csv_or_none,
    models.DateField                    : date_or_none,
    models.DateTimeField                : datetime_or_none,
    models.DecimalField                 : string_or_none,
    models.EmailField                   : email_or_none,
    models.FileField                    : django_file_or_none,
    models.FilePathField                : string_or_none,
    models.FloatField                   : float_or_none,
    models.GenericIPAddressField        : string_or_none,
    models.IPAddressField               : string_or_none,
    models.ImageField                   : django_image_or_none,
    models.IntegerField                 : int_or_none_range(-2147483648, 2147483647),
    models.NullBooleanField             : bool_or_none,
    models.PositiveIntegerField         : int_or_none_range(0, 2147483647),
    models.PositiveSmallIntegerField    : int_or_none_range(0, 32767),
    models.SlugField                    : slug_or_none,
    models.SmallIntegerField            : int_or_none_range(-32768, 32767),
    models.TextField                    : string_or_none,
    models.TimeField                    : time_or_none,
    models.URLField                     : string_or_none,
}
