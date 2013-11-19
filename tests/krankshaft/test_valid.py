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

class ValidForeign(models.Model):
    name = models.CharField(max_length=20)

class ValidForeign2(models.Model):
    name = models.CharField(max_length=20)

class ValidForeign3(models.Model):
    foreign2 = models.ForeignKey(ValidForeign2, primary_key=True)

class ValidOneToOne(models.Model):
    name = models.CharField(max_length=20)

class ValidManyToMany(models.Model):
    name = models.CharField(max_length=20)

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
    decimal = models.DecimalField(decimal_places=1, max_digits=1)
    email = models.EmailField()
    file = models.FileField(max_length=300, upload_to='file/')
    file_path = models.FilePathField(max_length=300)
    float = models.FloatField()
    generic_ip_address = models.GenericIPAddressField()
    ip_address = models.IPAddressField()
    image = models.ImageField(max_length=300, upload_to='image/')
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

    foreign = models.ForeignKey(ValidForeign)
    foreign_nullable = models.ForeignKey(ValidForeign2, null=True)
    foreign3 = models.ForeignKey(ValidForeign3)
    one_to_one = models.OneToOneField(ValidOneToOne)
    many_to_many = models.ManyToManyField(ValidManyToMany)
    many_to_many_blank = models.ManyToManyField(ValidManyToMany, blank=True, related_name='many_to_many_blank')

class BaseExpecterTest(TestCaseNoDB):
    def expect(self, expected, data, clean=None, **opts):
        if clean is None:
            clean = data
        assert clean == self.expecter.expect(expected, data, **opts)

    def expect_raises(self, expected, data, errors=None, **opts):
        with self.assertRaises(valid.ValueIssue) as cm:
            self.expecter.expect(expected, data, **opts)

        if errors is not None:
            assert errors == cm.exception.errors

    def setUp(self):
        self.expecter = valid.Expecter()

class ExpecterTest(BaseExpecterTest):
    def test_expect_simple(self):
        self.expect(valid.int, 1)

    def test_expect_simple_coerce(self):
        self.expect(valid.int, '1', 1)

    def test_expect_simple_issue(self):
        self.expect_raises(valid.int, 'a', errors=["invalid literal for int() with base 10: 'a'"])

    def test_expect_dict(self):
        self.expect({'key': valid.int}, {'key': 1})

    def test_expect_dict_coerce(self):
        self.expect({'key': valid.int}, {'key': '1'}, {'key': 1})

    def test_expect_dict_data_issue(self):
        self.expect_raises({'key': valid.int}, {'key': 'a'}, errors={
            'key': ["invalid literal for int() with base 10: 'a'"]
        })

    def test_expect_dict_type_issue(self):
        self.expect_raises({}, [], errors=["Unexpected type, expected <type 'dict'>: <type 'list'>"])

    def test_expect_dict_missing_keys(self):
        self.expect_raises({'key': valid.int}, {}, errors={
            '__nonkeyerrors__': ['Missing keys: key'],
        })

    def test_expect_dict_extra_keys(self):
        self.expect_raises({'key': valid.int}, {'key': 0, 'other': 0}, errors={
            '__nonkeyerrors__': ['Extra keys: other'],
        })

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
        self.expect_raises([valid.int], ['a', None, 1], errors={
            0: ["invalid literal for int() with base 10: 'a'"],
            1: ['int does not accept None'],
        })

    def test_expect_list_exact_multiple_validation_errors(self):
        self.expect_raises([valid.int, valid.int, valid.int], ['a', None, 1], errors={
            0: ["invalid literal for int() with base 10: 'a'"],
            1: ['int does not accept None'],
        })

    def test_expect_list_unbalanced_lists(self):
        self.expect_raises([valid.int, valid.int, valid.int], [1], errors={
            '__nonindexerrors__': ['Expected list of length 3, saw 1']
        })

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
        self.expect_raises(valid.bool, None,
            errors=['bool_or_none does not accept None']
        )

    def test_bool_or_none_with_none(self):
        self.expect(valid.bool_or_none, None)

    def test_choices(self):
        self.expect(valid.choice(valid.string, ('a', 'b', 'c')), 'a')

    def test_choices_not_valid_choice(self):
        self.expect_raises(valid.choice(valid.string, ('a', 'b', 'c')), 'd',
            errors=['The value is not a valid choice: d']
        )

    def test_date(self):
        self.expect(valid.date, '2013-11-06', date(2013, 11, 06))

    def test_date_with_none(self):
        self.expect_raises(valid.date, None,
            errors=['date_or_none does not accept None']
        )

    def test_date_invalid_date(self):
        self.expect_raises(valid.date, '2013-11-99',
            errors=['day is out of range for month']
        )

    def test_date_or_none_with_none(self):
        self.expect(valid.date_or_none, None)

    def test_datetime(self):
        self.expect(valid.datetime, '2013-11-06 15:51:20', datetime(2013, 11, 06, 15, 51, 20))

    def test_datetime_iso(self):
        dt = datetime.now()
        self.expect(valid.datetime, dt.isoformat(), dt)

    def test_datetime_with_none(self):
        self.expect_raises(valid.datetime, None,
            errors=['datetime_or_none does not accept None']
        )

    def test_datetime_invalid_datetime(self):
        self.expect_raises(valid.datetime, '2013-11-99 15:51:20',
            errors=['day is out of range for month']
        )

    def test_datetime_or_none_with_none(self):
        self.expect(valid.datetime_or_none, None)

    def test_django_file(self):
        self.expect(valid.django_file, File(StringIO('hello world')))

    def test_django_file_with_none(self):
        self.expect_raises(valid.django_file, None,
            errors=['django_file_or_none does not accept None']
        )

    def test_django_file_or_none_with_none(self):
        self.expect(valid.django_file_or_none, None)

    def test_django_file_invalid_file(self):
        self.expect_raises(valid.django_file, StringIO('hello world'),
            errors=['No django file found']
        )

    def test_django_file_invalid_input(self):
        self.expect_raises(valid.django_file, 'hello world',
            errors=['No django file found']
        )

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_jpg(self):
        self.expect(valid.django_image, IMAGE_JPG)

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_jpg_invalid(self):
        self.expect_raises(valid.django_image, IMAGE_JPG_INVALID,
            errors=['No valid django image (file) found']
        )

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_png(self):
        self.expect(valid.django_image, IMAGE_PNG)

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_png_invalid(self):
        self.expect_raises(valid.django_image, IMAGE_PNG_INVALID,
            errors=['No valid django image (file) found']
        )

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_with_none(self):
        self.expect_raises(valid.django_image, None,
            errors=['django_image_or_none does not accept None']
        )

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_or_none_with_none(self):
        self.expect(valid.django_image_or_none, None)

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_invalid_image(self):
        self.expect_raises(valid.django_image, StringIO('hello world'),
            errors=['No django file found']
        )

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_django_image_invalid_input(self):
        self.expect_raises(valid.django_image, 'hello world',
            errors=['No django file found']
        )

    def test_django_validator(self):
        from django.core.validators import validate_email
        validator = valid.django_validator(valid.string, validate_email)
        self.expect(validator, 'me@somewhere.com')

    def test_django_validator_invalid(self):
        from django.core.validators import validate_email
        validator = valid.django_validator(valid.string, validate_email)
        self.expect_raises(validator, 'mesomewhere.com',
            errors=['Enter a valid e-mail address.']
        )

    def test_email(self):
        self.expect(valid.email, 'me@somewhere.com')

    def test_email_with_none(self):
        self.expect_raises(valid.email, None,
            errors=['string_or_none does not accept None']
        )

    def test_email_invalid(self):
        self.expect_raises(valid.email, 'mesomewhere.com',
            errors=['Enter a valid e-mail address.']
        )

    def test_email_or_none_with_none(self):
        self.expect(valid.email_or_none, None)

    def test_float(self):
        self.expect(valid.float, '1', 1)
        self.expect(valid.float, '1.1', 1.1)
        self.expect(valid.float, '.1', .1)
        self.expect(valid.float, '0.1', .1)

    def test_float_with_none(self):
        self.expect_raises(valid.float, None, errors=['float does not accept None'])

    def test_float_invalid(self):
        self.expect_raises(valid.float, 'a', errors=['could not convert string to float: a'])
        self.expect_raises(valid.float, '1.a', errors=['invalid literal for float(): 1.a'])
        self.expect_raises(valid.float, '.a', errors=['could not convert string to float: .a'])
        self.expect_raises(valid.float, 'a.1', errors=['could not convert string to float: a.1'])

    def test_float_or_none_with_none(self):
        self.expect(valid.float_or_none, None)

    def test_int(self):
        self.expect(valid.int, 1)

    def test_int_with_invalid(self):
        self.expect_raises(valid.int, 'a', errors=["invalid literal for int() with base 10: 'a'"])

    def test_int_with_none(self):
        self.expect_raises(valid.int, None, errors=['int does not accept None'])

    def test_int_or_none(self):
        self.expect(valid.int_or_none, 1)

    def test_int_or_none_with_invalid(self):
        self.expect_raises(valid.int_or_none, 'a', errors=["invalid literal for int() with base 10: 'a'"])

    def test_int_or_none_with_none(self):
        self.expect(valid.int_or_none, None)

    def test_int_range(self):
        self.expect(valid.int_range(0, 10), 5)

    def test_int_range_unbounded_high(self):
        self.expect(valid.int_range(0, None), 5)

    def test_int_range_unbounded_high_too_low(self):
        self.expect_raises(valid.int_range(0, None), -1, errors=['The value is not within the range 0 <= -1 <= None'])

    def test_int_range_unbounded_low(self):
        self.expect(valid.int_range(None, 10), 5)

    def test_int_range_unbounded_low_too_high(self):
        self.expect_raises(valid.int_range(None, 10), 11, errors=['The value is not within the range None <= 11 <= 10'])

    def test_int_range_invalid_value(self):
        self.expect_raises(valid.int_range(0, 10), None, errors=['int does not accept None'])

    def test_int_range_invalid_range_high(self):
        self.expect_raises(valid.int_range(0, 10), 11, errors=['The value is not within the range 0 <= 11 <= 10'])

    def test_int_range_invalid_range_low(self):
        self.expect_raises(valid.int_range(0, 10), -1, errors=['The value is not within the range 0 <= -1 <= 10'])

    def test_int_range_invalid_range_coerce_high(self):
        self.expect_raises(valid.int_range(0, 10), '11', errors=['The value is not within the range 0 <= 11 <= 10'])

    def test_int_range_invalid_range_coerce_low(self):
        self.expect_raises(valid.int_range(0, 10), '-1', errors=['The value is not within the range 0 <= -1 <= 10'])

    def test_int_range_invalid_range_invalid_data(self):
        self.expect_raises(valid.int_range(0, 10), 'a', errors=["invalid literal for int() with base 10: 'a'"])

    def test_int_or_none_range(self):
        self.expect(valid.int_or_none_range(0, 10), 5)

    def test_int_or_none_range_invalid_value(self):
        self.expect(valid.int_or_none_range(0, 10), None)

    def test_int_or_none_range_invalid_range_high(self):
        self.expect_raises(valid.int_or_none_range(0, 10), 11, errors=['The value is not within the range 0 <= 11 <= 10'])

    def test_int_or_none_range_invalid_range_low(self):
        self.expect_raises(valid.int_or_none_range(0, 10), -1, errors=['The value is not within the range 0 <= -1 <= 10'])

    def test_int_or_none_range_invalid_range_coerce_high(self):
        self.expect_raises(valid.int_or_none_range(0, 10), '11', errors=['The value is not within the range 0 <= 11 <= 10'])

    def test_int_or_none_range_invalid_range_coerce_low(self):
        self.expect_raises(valid.int_or_none_range(0, 10), '-1', errors=['The value is not within the range 0 <= -1 <= 10'])

    def test_int_or_none_range_invalid_range_invalid_data(self):
        self.expect_raises(valid.int_or_none_range(0, 10), 'a', errors=["invalid literal for int() with base 10: 'a'"])

    def test_int_csv(self):
        self.expect(valid.int_csv, '1,2,3')
        self.expect(valid.int_csv, '1,2,', '1,2')
        self.expect(valid.int_csv, ',2,', '2')
        self.expect(valid.int_csv, '2')

    def test_int_csv_invalid(self):
        self.expect_raises(valid.int_csv, 'a,2,3', errors={0: ["invalid literal for int() with base 10: 'a'"]})

    def test_int_csv_with_none(self):
        self.expect_raises(valid.int_csv, None, errors=['int_no_none_csv does not accept None'])

    def test_int_csv_or_none_with_none(self):
        self.expect(valid.int_csv_or_none, None)

    def test_list_n_or_more_zero(self):
        self.expect_raises(valid.list_n_or_more(valid.int, 1), [], errors={'__nonindexerrors__': ['Expected list with 1 or more elements, saw 0']})

    def test_list_n_or_more_one(self):
        self.expect(valid.list_n_or_more(valid.int, 1), [1])

    def test_list_n_or_more_more(self):
        self.expect(valid.list_n_or_more(valid.int, 1), [1,2])

    def test_list_n_or_more_invalid_data(self):
        self.expect_raises(valid.list_n_or_more(valid.int, 1), ['a',2], errors={0: ["invalid literal for int() with base 10: 'a'"]})

    def test_list_n_or_more_invalid_n(self):
        self.assertRaises(valid.KrankshaftError, valid.list_n_or_more, valid.int, 0)

    def test_slug(self):
        self.expect(valid.slug, 'HELLO WORLD', 'hello-world')

    def test_slug_with_none(self):
        self.expect_raises(valid.slug, None, errors=['slug_or_none does not accept None'])

    def test_slug_or_none_with_none(self):
        self.expect(valid.slug_or_none, None)

    def test_string(self):
        self.expect(valid.string, 'key')

    def test_string_fail_dict(self):
        self.expect_raises(valid.string, {}, errors=["Expected string, saw: <type 'dict'>"])

    def test_string_fail_integer(self):
        self.expect_raises(valid.string, 1, errors=["Expected string, saw: <type 'int'>"])

    def test_string_fail_list(self):
        self.expect_raises(valid.string, [], errors=["Expected string, saw: <type 'list'>"])

    def test_string_with_none(self):
        self.expect_raises(valid.string, None, errors=['string_or_none does not accept None'])

    def test_string_max_length(self):
        self.expect(valid.string_max_length(1), '')

    def test_string_max_length_over_limit(self):
        self.expect_raises(valid.string_max_length(1), 'aa', errors=['The value is greater than max length 1: 2'])

    def test_string_max_length_with_none(self):
        self.expect_raises(valid.string_max_length(1), None, errors=['string_or_none does not accept None'])

    def test_string_or_none_with_none(self):
        self.expect(valid.string_or_none, None)

    def test_string_or_none_max_length(self):
        self.expect(valid.string_or_none_max_length(1), '')

    def test_string_or_none_max_length_over_limit(self):
        self.expect_raises(valid.string_or_none_max_length(1), 'aa', errors=['The value is greater than max length 1: 2'])

    def test_string_or_none_max_length_with_none(self):
        self.expect(valid.string_or_none_max_length(1), None)

    def test_time(self):
        self.expect(valid.time, '15:53:21', time(15, 53, 21))

    def test_time_with_none(self):
        self.expect_raises(valid.time, None, errors=['time_or_none does not accept None'])

    def test_time_invalid_time(self):
        self.expect_raises(valid.time, '15:53:99', errors=['second must be in 0..59'])

    def test_time_or_none_with_none(self):
        self.expect(valid.time_or_none, None)


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
        self.expect_raises(self.field('id'), 'a', errors=["invalid literal for int() with base 10: 'a'"])

    def test_field_id_invalid_low(self):
        self.expect_raises(self.field('id'), 0, errors=['The value is not within the range 1 <= 0 <= 2147483647'])

    def test_field_big_integer(self):
        self.expect(self.field('big_integer'), 0)

    def test_field_big_integer_invalid(self):
        self.expect_raises(self.field('big_integer'), 'a', errors=["invalid literal for int() with base 10: 'a'"])

    def test_field_big_integer_invalid_high(self):
        self.expect_raises(self.field('big_integer'), 9223372036854775808, errors=['The value is not within the range -9223372036854775808 <= 9223372036854775808 <= 9223372036854775807'])

    def test_field_big_integer_invalid_low(self):
        self.expect_raises(self.field('big_integer'), -9223372036854775809, errors=['The value is not within the range -9223372036854775808 <= -9223372036854775809 <= 9223372036854775807'])

    def test_field_boolean_0(self):
        self.expect(self.field('boolean'), 0, False)

    def test_field_boolean_1(self):
        self.expect(self.field('boolean'), 1, True)

    def test_field_boolean_no(self):
        self.expect(self.field('boolean'), 'no', False)

    def test_field_boolean_yes(self):
        self.expect(self.field('boolean'), 'yes', True)

    def test_field_boolean_with_none(self):
        self.expect_raises(self.field('boolean'), None, errors=['bool_or_none does not accept None'])

    def test_field_char_max_20_empty(self):
        self.expect(self.field('char_max_20'), '')

    def test_field_char_max_20_max(self):
        self.expect(self.field('char_max_20'), 'a' * 20)

    def test_field_char_max_20_invalid_high(self):
        self.expect_raises(self.field('char_max_20'), 'a' * 21, errors=['The value is greater than max length 20: 21'])

    def test_field_char_max_20_invalid_with_none(self):
        self.expect_raises(self.field('char_max_20'), None, errors=['string_or_none does not accept None'])

    def test_field_char_max_20_choices_empty(self):
        self.expect_raises(self.field('char_max_20_choices'), '', errors=['The value is not a valid choice: '])

    def test_field_char_max_20_choices(self):
        self.expect(self.field('char_max_20_choices'), 'a')

    def test_field_char_max_20_choices_invalid(self):
        self.expect_raises(self.field('char_max_20_choices'), 'd', errors=['The value is not a valid choice: d'])

    def test_field_char_max_20_choices_invalid_with_none(self):
        self.expect_raises(self.field('char_max_20_choices'), None, errors=['string_or_none does not accept None'])

    def test_field_csv_integer_integer(self):
        self.expect_raises(self.field('csv_integer'), 1, errors=["Expected string, saw: <type 'int'>"])

    def test_field_csv_integer_string_integer(self):
        self.expect(self.field('csv_integer'), '1')

    def test_field_csv_integer_csv_int(self):
        self.expect(self.field('csv_integer'), '1,1')

    def test_field_csv_integer_invalid(self):
        self.expect_raises(self.field('csv_integer'), '1,1,a', errors={2: ["invalid literal for int() with base 10: 'a'"]})

    def test_field_csv_integer_invalid_with_none(self):
        self.expect_raises(self.field('csv_integer'), None, errors=['int_no_none_csv does not accept None'])

    def test_field_date(self):
        self.expect(self.field('date'), '2013-10-07', date(2013, 10, 7))

    def test_field_date_invalid(self):
        self.expect_raises(self.field('date'), 'aaa', errors=['Could not parse date: aaa'])

    def test_field_date_invalid_date(self):
        self.expect_raises(self.field('date'), '2013-10-99', errors=['day is out of range for month'])

    def test_field_date_with_none(self):
        self.expect_raises(self.field('date'), None, errors=['date_or_none does not accept None'])

    def test_field_datetime(self):
        self.expect(self.field('datetime'), '2013-10-07 15:21:22', datetime(2013, 10, 7, 15, 21, 22))

    def test_field_datetime_invalid(self):
        self.expect_raises(self.field('datetime'), 'aaa', errors=['Could not parse datetime: aaa'])

    def test_field_datetime_invalid_datetime(self):
        self.expect_raises(self.field('datetime'), '2013-10-99 15:21:22', errors=['day is out of range for month'])

    def test_field_datetime_with_none(self):
        self.expect_raises(self.field('datetime'), None, errors=['datetime_or_none does not accept None'])

    def test_field_decimal(self):
        self.expect(self.field('decimal'), '1.1')

    def test_field_decimal_with_none(self):
        self.expect_raises(self.field('decimal'), None, errors=['string_or_none does not accept None'])

    def test_field_email(self):
        self.expect(self.field('email'), 'me@somewhere.com')

    def test_field_email_invalid(self):
        self.expect_raises(self.field('email'), 'mesomewhere.com', errors=['Enter a valid e-mail address.'])

    def test_field_email_with_none(self):
        self.expect_raises(self.field('email'), None, errors=['string_or_none_django_validator does not accept None'])

    def test_field_file(self):
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write('hello world')
            tmp.seek(0)
            self.expect(self.field('file'), File(tmp))

    def test_field_file_invalid(self):
        self.expect_raises(self.field('file'), StringIO('hello world'), errors=['No django file found'])

    def test_field_file_with_none(self):
        self.expect_raises(self.field('file'), None, errors=['django_file_or_none does not accept None'])

    def test_field_file_path(self):
        self.expect(self.field('file_path'), '/a/path/')

    def test_field_float(self):
        self.expect(self.field('float'), '1.1', 1.1)

    def test_field_foreign(self):
        self.expect(self.field('foreign'), 1)

    def test_field_foreign_with_none(self):
        self.expect_raises(self.field('foreign'), None, errors=['int_or_none_range_1_to_2147483647 does not accept None'])

    def test_field_foreign_nullable(self):
        self.expect(self.field('foreign_nullable'), None)

    def test_field_foreign3(self):
        self.expect(self.field('foreign3'), 1)

    def test_field_generic_ip_address(self):
        self.expect(self.field('generic_ip_address'), '192.168.1.1')

    def test_field_many_to_many(self):
        self.expect(self.field('many_to_many'), [1, 2, 3])

    def test_field_many_to_many_at_least_one(self):
        self.expect_raises(self.field('many_to_many'), [], errors={'__nonindexerrors__': ['Expected list with 1 or more elements, saw 0']})

    def test_field_many_to_many_invalid(self):
        self.expect_raises(self.field('many_to_many'), ['a', 'b', 'c'], errors={
            0: ["invalid literal for int() with base 10: 'a'"],
            1: ["invalid literal for int() with base 10: 'b'"],
            2: ["invalid literal for int() with base 10: 'c'"]})

    def test_field_many_to_many_blank(self):
        self.expect(self.field('many_to_many_blank'), [])

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
        self.expect_raises(self.field('integer'), -2147483649, errors=['The value is not within the range -2147483648 <= -2147483649 <= 2147483647'])

    def test_field_integer_invalid_high(self):
        self.expect_raises(self.field('integer'), 21474836471, errors=['The value is not within the range -2147483648 <= 21474836471 <= 2147483647'])

    def test_field_integer_with_none(self):
        self.expect_raises(self.field('integer'), None, errors=['int_or_none_range_-2147483648_to_2147483647 does not accept None'])

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

    def test_field_one_to_one(self):
        self.expect(self.field('one_to_one'), 1)

    def test_field_positive_integer_0(self):
        self.expect(self.field('positive_integer'), 0)

    def test_field_positive_integer_1(self):
        self.expect(self.field('positive_integer'), 1)

    def test_field_positive_integer_minus_1(self):
        self.expect_raises(self.field('positive_integer'), -1, errors=['The value is not within the range 0 <= -1 <= 2147483647'])

    def test_field_positive_integer_with_none(self):
        self.expect_raises(self.field('positive_integer'), None, errors=['int_or_none_range_0_to_2147483647 does not accept None'])

    def test_field_positive_integer_invalid_high(self):
        self.expect_raises(self.field('positive_integer'), 2147483648, errors=['The value is not within the range 0 <= 2147483648 <= 2147483647'])

    def test_field_positive_small_integer(self):
        self.expect(self.field('positive_small_integer'), 0)

    def test_field_positive_small_integer_minus_1(self):
        self.expect_raises(self.field('positive_small_integer'), -1, errors=['The value is not within the range 0 <= -1 <= 32767'])

    def test_field_positive_small_integer_with_none(self):
        self.expect_raises(self.field('positive_small_integer'), None, errors=['int_or_none_range_0_to_32767 does not accept None'])

    def test_field_positive_small_integer_invalid_high(self):
        self.expect_raises(self.field('positive_small_integer'), 32768, errors=['The value is not within the range 0 <= 32768 <= 32767'])

    def test_field_slug(self):
        self.expect(self.field('slug'), 'HELLO WORLD', 'hello-world')

    def test_field_small_integer(self):
        self.expect(self.field('small_integer'), 0)

    def test_field_small_integer_invalid_high(self):
        self.expect_raises(self.field('small_integer'), 32768, errors=['The value is not within the range -32768 <= 32768 <= 32767'])

    def test_field_small_integer_invalid_low(self):
        self.expect_raises(self.field('small_integer'), -32769, errors=['The value is not within the range -32768 <= -32769 <= 32767'])

    def test_field_small_integer_invalid_with_none(self):
        self.expect_raises(self.field('small_integer'), None, errors=['int_or_none_range_-32768_to_32767 does not accept None'])

    def test_field_text(self):
        self.expect(self.field('text'), 'hello world')

    def test_field_text_with_none(self):
        self.expect_raises(self.field('text'), None, errors=['string_or_none does not accept None'])

    def test_field_time(self):
        self.expect(self.field('time'), '15:38:21', time(15, 38, 21))

    def test_field_time_invalid(self):
        self.expect_raises(self.field('time'), '15:99:21', errors=['minute must be in 0..59'])

    def test_field_time_invalid_non_date(self):
        self.expect_raises(self.field('time'), 'aa', errors=['Could not parse time: aa'])

    def test_field_time_with_none(self):
        self.expect_raises(self.field('time'), None, errors=['time_or_none does not accept None'])

    def test_field_url(self):
        self.expect(self.field('url'), 'https://google.com/')
