# TODO helpful validators
#   - email
#   - every django field needs a validator

# TODO explain pattern:
#   raise ValueError when value is not accepted
#   return value otherwise (can value be transformed? yes, '1' -> 1 [string to int])

# TODO document everything

from . import util
from .exceptions import ExpectedIssue, KrankshaftError, ValueIssue

# TODO document how to write a data validator, ... validate data raise
# ValueError if it fails otherwise return cleaned value
# TODO document overall usage... this is a completely new concept and is somewhat
# complex
# TODO document specifically how expect_list() works
# TODO document 'strict_dict' shortcut

class Expecter(object):
    ExpectedIssue = ExpectedIssue
    ValueIssue = ValueIssue

    defaults = {
        'ignore_extra_keys': False,
        'ignore_missing_keys': False,
    }

    def __init__(self, **opts):
        self.opts = self.options(opts)

    def depthstr(self, depth):
        depthstr = 'depth@root'
        if depth:
            depthstr = 'depth@' + '.'.join(depth)

        return depthstr

    # TODO how does a ValueIssue exception look when it hits the top?
    #   do we need to override the __str__ method?
    def expect(self, expected, data, depth=None, **opts):
        if depth is None:
            opts = self.options(opts)

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
        return tuple(self.expect_list(expected, data, depth, opts))

    def options(self, opts):
        return util.valid(
            util.defaults(self.shortcuts(opts), self.defaults),
            self.defaults.keys()
        )

    def shortcuts(self, opts):
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
    new = lambda value: None if value is None else validator(value)
    new.__name__ = validator.__name__ + '_or_none'
    return new

def no_none(validator):
    def new(value):
        if value is None:
            raise ValueError('%s does not accept None' % validator.__name__)
        return validator(value)
    new.__name__ = validator.__name__ + '_no_none'
    return new

#
# validator factories
#

def int_range(validator, low, high):
    def int_range_validator(value):
        value = validator(value)
        if not (low <= value <= high):
            raise ValueError(
                'The value is not within the range %s <= %s <= %s'
                % (low, value, high)
            )
        return value

    int_range_validator.__name__ = validator.__name__ + '_range_%s_to_%s' \
        % (low, high)

    return int_range_validator

def list_x_or_more(validator, n):
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
