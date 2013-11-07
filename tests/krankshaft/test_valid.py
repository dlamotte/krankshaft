from __future__ import absolute_import

from cStringIO import StringIO
from datetime import date, datetime, time
from django.core.files import File
from django.db import models
from krankshaft import valid
from tests.base import TestCaseNoDB
import base64
import tempfile
import unittest

try:
    from PIL import Image
except ImportError:
    Image = None

IMAGE_JPG = File(StringIO(base64.decodestring(''.join('''
/9j/4AAQSkZJRgABAQEAAQABAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkI
CQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/2wBDAQMDAwQDBAgEBAgQCwkLEBAQEBAQ
EBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/wAARCAABAAEDASIA
AhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEB
AAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AKOgA//Z
'''.splitlines()))))

IMAGE_JPG_INVALID = File(StringIO(base64.decodestring(''.join('''
/9j/4AAQSkZJRgABAQEAAQABAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkI
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
EBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/wAARCAABAAEDASIA
AhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEB
AAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AKOgA//Z
'''.splitlines()))))

IMAGE_PNG = File(StringIO(base64.decodestring(''.join('''
iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAQMAAAAl21bKAAAABGdBTUEAALGPC/xhBQAAAAFzUkdC
AK7OHOkAAAAgY0hSTQAAeiYAAICEAAD6AAAAgOgAAHUwAADqYAAAOpgAABdwnLpRPAAAAAZQTFRF
6+vr////hyBEawAAAAFiS0dEAf8CLd4AAAAJdnBBZwAAAAIAAAACAGosfoAAAAAKSURBVAjXY2AA
AAACAAHiIbwzAAAAJXRFWHRkYXRlOmNyZWF0ZQAyMDEzLTExLTA3VDA5OjU5OjE3LTA2OjAw/JW+
VQAAACV0RVh0ZGF0ZTptb2RpZnkAMjAxMy0xMS0wN1QwOTo1OToxNy0wNjowMI3IBukAAAAASUVO
RK5CYII=
'''.splitlines()))))

IMAGE_PNG_INVALID = File(StringIO(base64.decodestring(''.join('''
iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAQMAAAAl21bKAAAABGdBTUEAALGPC/xhBQAAAAFzUkdC
AK7OHOkAAAAgY0hSTQAAeiYAAICEAAD6AAAAgOgAAHUwAADqYAAAOpgAABdwnLpRPAAAAAZQTFRF
6+vr////hyBEawAAAAFiS0dEAf8CLd4AAAAJdnBBZwAAAAIAAAACAGosfoAAAAAKSURBVAjXY2AA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
VQAAACV0RVh0ZGF0ZTptb2RpZnkAMjAxMy0xMS0wN1QwOTo1OToxNy0wNjowMI3IBukAAAAASUVO
RK5CYII=
'''.splitlines()))))

class Valid(models.Model):
    #id = models.AutoField()
    big_integer = models.BigIntegerField()
    boolean = models.BooleanField()
    char_max_20 = models.CharField(max_length=20)
    char_max_20_choices = models.CharField(max_length=20, choices=(
        ('a', 'A'),
        ('b', 'B'),
        ('c', 'C'),
    ))
    csv_integer = models.CommaSeparatedIntegerField(max_length=20)
    date = models.DateField()
    datetime = models.DateTimeField()
    decimal = models.DecimalField()
    email = models.EmailField()
    file = models.FileField(max_length=300)
    file_path = models.FilePathField(max_length=300)
    float = models.FloatField()
    generic_ip_address = models.GenericIPAddressField()
    ip_address = models.IPAddressField()
    image = models.ImageField(max_length=300)
    integer = models.IntegerField()
    integer_nullable = models.IntegerField(null=True)
    null_boolean = models.NullBooleanField()
    positive_integer = models.PositiveIntegerField()
    positive_small_integer = models.PositiveSmallIntegerField()
    slug = models.SlugField()
    small_integer = models.SmallIntegerField()
    text = models.TextField()
    time = models.TimeField()
    url = models.URLField()

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

    def test_django_file(self):
        self.expect(valid.django_file, File(StringIO('hello world')))

    def test_django_file_with_none(self):
        self.expect_raises(valid.django_file, None)

    def test_django_file_or_none_with_none(self):
        self.expect(valid.django_file_or_none, None)

    def test_django_file_invalid_file(self):
        self.expect_raises(valid.django_file, StringIO('hello world'))

    def test_django_file_invalid_input(self):
        self.expect_raises(valid.django_file, 'hello world')

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_jpg(self):
        self.expect(valid.django_image, IMAGE_JPG)

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_jpg_invalid(self):
        self.expect_raises(valid.django_image, IMAGE_JPG_INVALID)

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_png(self):
        self.expect(valid.django_image, IMAGE_PNG)

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_png_invalid(self):
        self.expect_raises(valid.django_image, IMAGE_PNG_INVALID)

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_with_none(self):
        self.expect_raises(valid.django_image, None)

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_or_none_with_none(self):
        self.expect(valid.django_image_or_none, None)

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_invalid_image(self):
        self.expect_raises(valid.django_image, StringIO('hello world'))

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_invalid_input(self):
        self.expect_raises(valid.django_image, 'hello world')

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

class ValidatorsFromFieldTest(BaseExpecterTest):
    def field(self, name, model=False):
        kws = {}
        if model:
            kws['model'] = Valid
        return self.expecter.from_field(
            Valid._meta.get_field_by_name(name)[0],
            **kws
        )

    def test_field_id(self):
        self.expect(self.field('id'), 1)

    def test_field_id_invalid(self):
        self.expect_raises(self.field('id'), 'a')

    def test_field_id_invalid_low(self):
        self.expect_raises(self.field('id'), 0)

    def test_field_big_integer(self):
        self.expect(self.field('big_integer'), 0)

    def test_field_big_integer_invalid(self):
        self.expect_raises(self.field('big_integer'), 'a')

    def test_field_big_integer_invalid_high(self):
        self.expect_raises(self.field('big_integer'), 9223372036854775808)

    def test_field_big_integer_invalid_low(self):
        self.expect_raises(self.field('big_integer'), -9223372036854775809)

    def test_field_boolean_0(self):
        self.expect(self.field('boolean'), 0, False)

    def test_field_boolean_1(self):
        self.expect(self.field('boolean'), 1, True)

    def test_field_boolean_no(self):
        self.expect(self.field('boolean'), 'no', False)

    def test_field_boolean_yes(self):
        self.expect(self.field('boolean'), 'yes', True)

    def test_field_boolean_with_none(self):
        self.expect_raises(self.field('boolean'), None)

    def test_field_char_max_20_empty(self):
        self.expect(self.field('char_max_20'), '')

    def test_field_char_max_20_max(self):
        self.expect(self.field('char_max_20'), 'a' * 20)

    def test_field_char_max_20_invalid_high(self):
        self.expect_raises(self.field('char_max_20'), 'a' * 21)

    def test_field_char_max_20_invalid_with_none(self):
        self.expect_raises(self.field('char_max_20'), None)

    def test_field_char_max_20_choices_empty(self):
        self.expect_raises(self.field('char_max_20_choices'), '')

    def test_field_char_max_20_choices(self):
        self.expect(self.field('char_max_20_choices'), 'a')

    def test_field_char_max_20_choices_invalid(self):
        self.expect_raises(self.field('char_max_20_choices'), 'd')

    def test_field_char_max_20_choices_invalid_with_none(self):
        self.expect_raises(self.field('char_max_20_choices'), None)

    def test_field_csv_integer_integer(self):
        self.expect(self.field('csv_integer'), 1, '1')

    def test_field_csv_integer_string_integer(self):
        self.expect(self.field('csv_integer'), '1')

    def test_field_csv_integer_csv_int(self):
        self.expect(self.field('csv_integer'), '1,1')

    def test_field_csv_integer_invalid(self):
        self.expect_raises(self.field('csv_integer'), '1,1,a')

    def test_field_csv_integer_invalid_with_none(self):
        self.expect_raises(self.field('csv_integer'), None)

    def test_field_date(self):
        self.expect(self.field('date'), '2013-10-07', date(2013, 10, 7))

    def test_field_date_invalid(self):
        self.expect_raises(self.field('date'), 'aaa')

    def test_field_date_invalid_date(self):
        self.expect_raises(self.field('date'), '2013-10-99')

    def test_field_date_with_none(self):
        self.expect_raises(self.field('date'), None)

    def test_field_datetime(self):
        self.expect(self.field('datetime'), '2013-10-07 15:21:22', datetime(2013, 10, 7, 15, 21, 22))

    def test_field_datetime_invalid(self):
        self.expect_raises(self.field('datetime'), 'aaa')

    def test_field_datetime_invalid_datetime(self):
        self.expect_raises(self.field('datetime'), '2013-10-99 15:21:22')

    def test_field_datetime_with_none(self):
        self.expect_raises(self.field('datetime'), None)

    def test_field_decimal(self):
        self.expect(self.field('decimal'), '1.1')

    def test_field_decimal_with_none(self):
        self.expect_raises(self.field('decimal'), None)

    def test_field_email(self):
        self.expect(self.field('email'), 'me@somewhere.com')

    def test_field_email_invalid(self):
        self.expect_raises(self.field('email'), 'mesomewhere.com')

    def test_field_email_with_none(self):
        self.expect_raises(self.field('email'), None)

    def test_field_file(self):
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write('hello world')
            tmp.seek(0)
            self.expect(self.field('file'), File(tmp))

    def test_field_file_invalid(self):
        self.expect_raises(self.field('file'), StringIO('hello world'))

    def test_field_file_with_none(self):
        self.expect_raises(self.field('file'), None)

    def test_field_file_path(self):
        self.expect(self.field('file_path'), '/a/path/')

    def test_field_float(self):
        self.expect(self.field('float'), '1.1', 1.1)

    def test_field_generic_ip_address(self):
        self.expect(self.field('generic_ip_address'), '192.168.1.1')

    def test_field_ip_address(self):
        self.expect(self.field('ip_address'), '192.168.1.1')

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_field_image(self):
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(IMAGE_PNG.read())
            IMAGE_PNG.seek(0)
            tmp.seek(0)
            self.expect(self.field('image'), File(tmp))

    def test_field_integer(self):
        self.expect(self.field('integer'), 0)

    def test_field_integer_invalid_low(self):
        self.expect_raises(self.field('integer'), -2147483649)

    def test_field_integer_invalid_high(self):
        self.expect_raises(self.field('integer'), 21474836471)

    def test_field_integer_with_none(self):
        self.expect_raises(self.field('integer'), None)

    def test_field_integer_nullable_with_none(self):
        self.expect(self.field('integer_nullable'), None)

    def test_field_null_boolean_0(self):
        self.expect(self.field('null_boolean'), 0, False)

    def test_field_null_boolean_1(self):
        self.expect(self.field('null_boolean'), 1, True)

    def test_field_null_boolean_no(self):
        self.expect(self.field('null_boolean'), 'no', False)

    def test_field_null_boolean_yes(self):
        self.expect(self.field('null_boolean'), 'yes', True)

    def test_field_null_boolean_with_none(self):
        self.expect(self.field('null_boolean'), None)

    def test_field_positive_integer_0(self):
        self.expect(self.field('positive_integer'), 0)

    def test_field_positive_integer_1(self):
        self.expect(self.field('positive_integer'), 1)

    def test_field_positive_integer_minus_1(self):
        self.expect_raises(self.field('positive_integer'), -1)

    def test_field_positive_integer_with_none(self):
        self.expect_raises(self.field('positive_integer'), None)

    def test_field_positive_integer_invalid_high(self):
        self.expect_raises(self.field('positive_integer'), 2147483648)

    def test_field_positive_small_integer(self):
        self.expect(self.field('positive_small_integer'), 0)

    def test_field_positive_small_integer_minus_1(self):
        self.expect_raises(self.field('positive_small_integer'), -1)

    def test_field_positive_small_integer_with_none(self):
        self.expect_raises(self.field('positive_small_integer'), None)

    def test_field_positive_small_integer_invalid_high(self):
        self.expect_raises(self.field('positive_small_integer'), 32768)

    def test_field_slug(self):
        self.expect(self.field('slug'), 'HELLO WORLD', 'hello-world')

    def test_field_small_integer(self):
        self.expect(self.field('small_integer'), 0)

    def test_field_small_integer_invalid_high(self):
        self.expect_raises(self.field('small_integer'), 32768)

    def test_field_small_integer_invalid_low(self):
        self.expect_raises(self.field('small_integer'), -32769)

    def test_field_small_integer_invalid_with_none(self):
        self.expect_raises(self.field('small_integer'), None)

    def test_field_text(self):
        self.expect(self.field('text'), 'hello world')

    def test_field_text_with_none(self):
        self.expect_raises(self.field('text'), None)

    def test_field_time(self):
        self.expect(self.field('time'), '15:38:21', time(15, 38, 21))

    def test_field_time_invalid(self):
        self.expect_raises(self.field('time'), '15:99:21')

    def test_field_time_invalid_non_date(self):
        self.expect_raises(self.field('time'), 'aa')

    def test_field_time_with_none(self):
        self.expect_raises(self.field('time'), None)

    def test_field_url(self):
        self.expect(self.field('url'), 'https://google.com/')
