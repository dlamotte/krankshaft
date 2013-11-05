from __future__ import absolute_import

from krankshaft import valid
from tests.base import TestCaseNoDB

class BaseExpecterTest(TestCaseNoDB):
    def expect(self, expected, data, clean=None):
        if clean is None:
            clean = data
        assert clean == self.expecter.expect(expected, data)

    def expect_raises(self, expected, data):
        self.assertRaises(valid.ValueIssue, self.expecter.expect, expected, data)

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

    def test_expect_tuple_is_like_list(self):
        self.expect((valid.int, valid.int, valid.int), (1, 1, 1))

    def test_expect_tuple_is_like_list_zero_or_more(self):
        self.expect((valid.int,), (1, 1, 1))

    def test_expect_unhandled_type(self):
        self.assertRaises(self.expecter.ExpectedIssue, self.expecter.expect, set(), set())

class ValidatorsTest(BaseExpecterTest):
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
        self.expect(valid.int_range(valid.int, 0, 10), 5)

    def test_int_range_invalid_range_high(self):
        self.expect_raises(valid.int_range(valid.int, 0, 10), 11)

    def test_int_range_invalid_range_low(self):
        self.expect_raises(valid.int_range(valid.int, 0, 10), -1)

    def test_int_range_invalid_range_coerce_high(self):
        self.expect_raises(valid.int_range(valid.int, 0, 10), '11')

    def test_int_range_invalid_range_coerce_low(self):
        self.expect_raises(valid.int_range(valid.int, 0, 10), '-1')

    def test_int_range_invalid_range_invalid_data(self):
        self.expect_raises(valid.int_range(valid.int, 0, 10), 'a')

    def test_list_x_or_more_zero(self):
        self.expect_raises(valid.list_x_or_more(1, valid.int), [])

    def test_list_x_or_more_one(self):
        self.expect(valid.list_x_or_more(1, valid.int), [1])

    def test_list_x_or_more_more(self):
        self.expect(valid.list_x_or_more(1, valid.int), [1,2])

    def test_list_x_or_more_invalid_data(self):
        self.expect_raises(valid.list_x_or_more(1, valid.int), ['a',2])

    def test_list_x_or_more_invalid_n(self):
        self.assertRaises(valid.KrankshaftError, valid.list_x_or_more, 0, valid.int)

    def test_str(self):
        self.expect(valid.str, 'key')

    def test_str_with_none(self):
        self.expect_raises(valid.str, None)

    def test_str_or_none_with_none(self):
        self.expect(valid.str_or_none, None)

    def test_unicode(self):
        self.expect(valid.unicode, 'key')

    def test_unicode_with_none(self):
        self.expect_raises(valid.unicode, None)

    def test_unicode_or_none_with_none(self):
        self.expect(valid.unicode_or_none, None)
