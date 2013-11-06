from __future__ import absolute_import

from datetime import date, datetime, time
from krankshaft import valid
from tests.base import TestCaseNoDB

class BaseExpecterTest(TestCaseNoDB):
    def expect(self, expected, data, clean=None, **opts):
        if clean is None:
            clean = data
        assert clean == self.expecter.expect(expected, data, **opts)

    def expect_raises(self, expected, data, **opts):
        self.assertRaises(valid.ValueIssue, self.expecter.expect, expected, data, **opts)

    def setUp(self):
        self.expecter = valid.Expecter()

class ExpecterTest(BaseExpecterTest):
    def test_expect_simple(self):
        self.expect(valid.int, 1)

    def test_expect_simple_coerce(self):
        self.expect(valid.int, '1', 1)

    def test_expect_simple_issue(self):
        self.expect_raises(valid.int, 'a')

    def test_expect_dict(self):
        self.expect({'key': valid.int}, {'key': 1})

    def test_expect_dict_coerce(self):
        self.expect({'key': valid.int}, {'key': '1'}, {'key': 1})

    def test_expect_dict_data_issue(self):
        self.expect_raises({'key': valid.int}, {'key': 'a'})

    def test_expect_dict_type_issue(self):
        self.expect_raises({}, [])

    def test_expect_dict_missing_keys(self):
        self.expect_raises({'key': valid.int}, {})

    def test_expect_dict_extra_keys(self):
        self.expect_raises({'key': valid.int}, {'key': 0, 'other': 0})

    def test_expect_list_anything(self):
        self.expect([], [1])

    def test_expect_list_zero_or_more(self):
        self.expect([valid.int], [1])

    def test_expect_list_zero_or_more_zero(self):
        self.expect([valid.int], [])

    def test_expect_list_zero_or_more_more(self):
        self.expect([valid.int], [1,2,3])

    def test_expect_list_zero_or_more_coerce(self):
        self.expect([valid.int], ['1'], [1])

    def test_expect_list_exact(self):
        self.expect([valid.int, valid.int, valid.int], [1,1,1])

    def test_expect_list_zero_or_more_multiple_validation_errors(self):
        self.expect_raises([valid.int], ['a', None, 1])

    def test_expect_list_exact_multiple_validation_errors(self):
        self.expect_raises([valid.int, valid.int, valid.int], ['a', None, 1])

    def test_expect_list_unbalanced_lists(self):
        self.expect_raises([valid.int, valid.int, valid.int], [1])

    def test_expect_options_ignore_extra_keys(self):
        self.expect({'key': valid.int}, {'key': 1, 'extra': 2}, {'key': 1}, ignore_extra_keys=True)

    def test_expect_options_ignore_missing_keys(self):
        self.expect({'key': valid.int}, {}, ignore_missing_keys=True)

    def test_expect_options_not_strict_dict(self):
        self.expect({'key': valid.int}, {'extra': 2}, {}, strict_dict=False)

    def test_expect_tuple_is_like_list(self):
        self.expect((valid.int, valid.int, valid.int), (1, 1, 1))

    def test_expect_tuple_is_like_list_zero_or_more(self):
        self.expect((valid.int,), (1, 1, 1))

    def test_expect_unhandled_type(self):
        self.assertRaises(self.expecter.ExpectedIssue, self.expecter.expect, set(), set())

class ValidatorsTest(BaseExpecterTest):
    def test_bool_false(self):
        self.expect(valid.bool, 'no', False)
        self.expect(valid.bool, '0', False)
        self.expect(valid.bool, 'false', False)
        self.expect(valid.bool, 'null', False)
        self.expect(valid.bool, 'NO', False)
        self.expect(valid.bool, '0', False)
        self.expect(valid.bool, 'FALSE', False)
        self.expect(valid.bool, 'NULL', False)

    def test_bool_true(self):
        self.expect(valid.bool, 'yes', True)
        self.expect(valid.bool, '1', True)
        self.expect(valid.bool, 'true', True)
        self.expect(valid.bool, 'YES', True)
        self.expect(valid.bool, '1', True)
        self.expect(valid.bool, 'TRUE', True)

    def test_bool_with_none(self):
        self.expect_raises(valid.bool, None)

    def test_bool_or_none_with_none(self):
        self.expect(valid.bool_or_none, None)

    def test_choices(self):
        self.expect(valid.choice(valid.str, ('a', 'b', 'c')), 'a')

    def test_choices_not_valid_choice(self):
        self.expect_raises(valid.choice(valid.str, ('a', 'b', 'c')), 'd')

    def test_date(self):
        self.expect(valid.date, '2013-11-06', date(2013, 11, 06))

    def test_date_with_none(self):
        self.expect_raises(valid.date, None)

    def test_date_invalid_date(self):
        self.expect_raises(valid.date, '2013-11-99')

    def test_date_or_none_with_none(self):
        self.expect(valid.date_or_none, None)

    def test_datetime(self):
        self.expect(valid.datetime, '2013-11-06 15:51:20', datetime(2013, 11, 06, 15, 51, 20))

    def test_datetime_iso(self):
        dt = datetime.now()
        self.expect(valid.datetime, dt.isoformat(), dt)

    def test_datetime_with_none(self):
        self.expect_raises(valid.datetime, None)

    def test_datetime_invalid_datetime(self):
        self.expect_raises(valid.datetime, '2013-11-99 15:51:20')

    def test_datetime_or_none_with_none(self):
        self.expect(valid.datetime_or_none, None)

    def test_django_validator(self):
        from django.core.validators import validate_email
        validator = valid.django_validator(valid.str, validate_email)
        self.expect(validator, 'me@somewhere.com')

    def test_django_validator_invalid(self):
        from django.core.validators import validate_email
        validator = valid.django_validator(valid.str, validate_email)
        self.expect_raises(validator, 'mesomewhere.com')

    def test_email(self):
        self.expect(valid.email, 'me@somewhere.com')

    def test_email_with_none(self):
        self.expect_raises(valid.email, None)

    def test_email_invalid(self):
        self.expect_raises(valid.email, 'mesomewhere.com')

    def test_email_or_none_with_none(self):
        self.expect(valid.email_or_none, None)

    def test_float(self):
        self.expect(valid.float, '1', 1)
        self.expect(valid.float, '1.1', 1.1)
        self.expect(valid.float, '.1', .1)
        self.expect(valid.float, '0.1', .1)

    def test_float_with_none(self):
        self.expect_raises(valid.float, None)

    def test_float_invalid(self):
        self.expect_raises(valid.float, 'a')
        self.expect_raises(valid.float, '1.a')
        self.expect_raises(valid.float, '.a')
        self.expect_raises(valid.float, 'a.1')

    def test_float_or_none_with_none(self):
        self.expect(valid.float_or_none, None)

    def test_int(self):
        self.expect(valid.int, 1)

    def test_int_with_invalid(self):
        self.expect_raises(valid.int, 'a')

    def test_int_with_none(self):
        self.expect_raises(valid.int, None)

    def test_int_or_none(self):
        self.expect(valid.int_or_none, 1)

    def test_int_or_none_with_invalid(self):
        self.expect_raises(valid.int_or_none, 'a')

    def test_int_or_none_with_none(self):
        self.expect(valid.int_or_none, None)

    def test_int_range(self):
        self.expect(valid.int_range(0, 10), 5)

    def test_int_range_unbounded_high(self):
        self.expect(valid.int_range(0, None), 5)

    def test_int_range_unbounded_high_too_low(self):
        self.expect_raises(valid.int_range(0, None), -1)

    def test_int_range_unbounded_low(self):
        self.expect(valid.int_range(None, 10), 5)

    def test_int_range_unbounded_low_too_high(self):
        self.expect_raises(valid.int_range(None, 10), 11)

    def test_int_range_invalid_value(self):
        self.expect_raises(valid.int_range(0, 10), None)

    def test_int_range_invalid_range_high(self):
        self.expect_raises(valid.int_range(0, 10), 11)

    def test_int_range_invalid_range_low(self):
        self.expect_raises(valid.int_range(0, 10), -1)

    def test_int_range_invalid_range_coerce_high(self):
        self.expect_raises(valid.int_range(0, 10), '11')

    def test_int_range_invalid_range_coerce_low(self):
        self.expect_raises(valid.int_range(0, 10), '-1')

    def test_int_range_invalid_range_invalid_data(self):
        self.expect_raises(valid.int_range(0, 10), 'a')

    def test_int_or_none_range(self):
        self.expect(valid.int_or_none_range(0, 10), 5)

    def test_int_or_none_range_invalid_value(self):
        self.expect(valid.int_or_none_range(0, 10), None)

    def test_int_or_none_range_invalid_range_high(self):
        self.expect_raises(valid.int_or_none_range(0, 10), 11)

    def test_int_or_none_range_invalid_range_low(self):
        self.expect_raises(valid.int_or_none_range(0, 10), -1)

    def test_int_or_none_range_invalid_range_coerce_high(self):
        self.expect_raises(valid.int_or_none_range(0, 10), '11')

    def test_int_or_none_range_invalid_range_coerce_low(self):
        self.expect_raises(valid.int_or_none_range(0, 10), '-1')

    def test_int_or_none_range_invalid_range_invalid_data(self):
        self.expect_raises(valid.int_or_none_range(0, 10), 'a')

    def test_int_csv(self):
        self.expect(valid.int_csv, '1,2,3')
        self.expect(valid.int_csv, '1,2,', '1,2')
        self.expect(valid.int_csv, ',2,', '2')
        self.expect(valid.int_csv, '2')

    def test_int_csv_invalid(self):
        self.expect_raises(valid.int_csv, 'a,2,3')

    def test_int_csv_with_none(self):
        self.expect_raises(valid.int_csv, None)

    def test_int_csv_or_none_with_none(self):
        self.expect(valid.int_csv_or_none, None)

    def test_list_n_or_more_zero(self):
        self.expect_raises(valid.list_n_or_more(valid.int, 1), [])

    def test_list_n_or_more_one(self):
        self.expect(valid.list_n_or_more(valid.int, 1), [1])

    def test_list_n_or_more_more(self):
        self.expect(valid.list_n_or_more(valid.int, 1), [1,2])

    def test_list_n_or_more_invalid_data(self):
        self.expect_raises(valid.list_n_or_more(valid.int, 1), ['a',2])

    def test_list_n_or_more_invalid_n(self):
        self.assertRaises(valid.KrankshaftError, valid.list_n_or_more, valid.int, 0)

    def test_slug(self):
        self.expect(valid.slug, 'HELLO WORLD', 'hello-world')

    def test_slug_with_none(self):
        self.expect_raises(valid.slug, None)

    def test_slug_or_none_with_none(self):
        self.expect(valid.slug_or_none, None)

    def test_str(self):
        self.expect(valid.str, 'key')

    def test_str_with_none(self):
        self.expect_raises(valid.str, None)

    def test_str_max_length(self):
        self.expect(valid.str_max_length(1), '')

    def test_str_max_length_over_limit(self):
        self.expect_raises(valid.str_max_length(1), 'aa')

    def test_str_max_length_with_none(self):
        self.expect_raises(valid.str_max_length(1), None)

    def test_str_or_none_with_none(self):
        self.expect(valid.str_or_none, None)

    def test_str_or_none_max_length(self):
        self.expect(valid.str_or_none_max_length(1), '')

    def test_str_or_none_max_length_over_limit(self):
        self.expect_raises(valid.str_or_none_max_length(1), 'aa')

    def test_str_or_none_max_length_with_none(self):
        self.expect(valid.str_or_none_max_length(1), None)

    def test_time(self):
        self.expect(valid.time, '15:53:21', time(15, 53, 21))

    def test_time_with_none(self):
        self.expect_raises(valid.time, None)

    def test_time_invalid_time(self):
        self.expect_raises(valid.time, '15:53:99')

    def test_time_or_none_with_none(self):
        self.expect(valid.time_or_none, None)

    def test_unicode(self):
        self.expect(valid.unicode, 'key')

    def test_unicode_with_none(self):
        self.expect_raises(valid.unicode, None)

    def test_unicode_max_length(self):
        self.expect(valid.unicode_max_length(1), '')

    def test_unicode_max_length_over_limit(self):
        self.expect_raises(valid.unicode_max_length(1), 'aa')

    def test_unicode_max_length_with_none(self):
        self.expect_raises(valid.unicode_max_length(1), None)

    def test_unicode_or_none_with_none(self):
        self.expect(valid.unicode_or_none, None)

    def test_unicode_or_none_max_length(self):
        self.expect(valid.unicode_or_none_max_length(1), '')

    def test_unicode_or_none_max_length_over_limit(self):
        self.expect_raises(valid.unicode_or_none_max_length(1), 'aa')

    def test_unicode_or_none_max_length_with_none(self):
        self.expect(valid.unicode_or_none_max_length(1), None)
