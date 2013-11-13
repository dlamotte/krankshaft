from __future__ import absolute_import

from django.db import models
from krankshaft.exceptions import InvalidOptions
from krankshaft.query import DjangoQuery, Query
from tests.base import TestCaseNoDB
import pytest

class FakeForeign(models.Model):
    char_indexed = models.CharField(max_length=20, db_index=True)
    char_unindexed = models.CharField(max_length=20)

class Fake(models.Model):
    char_indexed = models.CharField(max_length=20, db_index=True)
    char_unindexed = models.CharField(max_length=20)
    foreign = models.ForeignKey(FakeForeign)

class QueryTest(TestCaseNoDB):
    def setUp(self):
        self.Query = Query

    def test_apply_not_implemented(self):
        self.assertRaises(NotImplementedError, self.Query({}).apply, None)

    def test_copy(self):
        a = self.Query({})
        b = a.copy()
        self.assertNotEqual(a, b)
        self.assertEqual(a.qs, b.qs)
        self.assertEqual(a.opts, b.opts)

    def test_default(self):
        query = self.Query({})
        self.assertEqual(query.opts, self.Query.defaults)

    def test_invalid_options(self):
        self.assertRaises(InvalidOptions, self.Query, {}, {
            'not_a_valid_option': True
        })

    def test_without(self):
        query = self.Query({'order_by': 'something'})
        without = query.without('order_by')
        qs = query.qs.copy()
        del qs['order_by']
        self.assertEqual(qs, without.qs)

class DjangoQueryTest(QueryTest):
    def apply_assert(self, qs, **opts):
        queryset, meta = self.Query(qs, opts).apply(Fake.objects.all())
        self.assertNotEqual(queryset, None)
        return queryset

    def apply_raises(self, qs, **opts):
        self.assertRaises(
            self.Query.Issues,
            self.Query(qs, opts).apply, Fake.objects.all()
        )

    def setUp(self):
        self.Query = DjangoQuery

    def test_apply_not_implemented(self):
        pass # its implemented on the DjangoQuery subclass

    def test_default_with_options(self):
        query = self.Query({}, {'default_limit': 20})
        opts = self.Query.defaults.copy()
        opts['default_limit'] = 20
        self.assertEqual(query.opts, opts)

    def test_apply_defer(self):
        queryset = self.apply_assert({'defer': 'char_unindexed,char_indexed'})
        assert queryset.query.deferred_loading[1]
        assert 'char_indexed' in queryset.query.deferred_loading[0]
        assert 'char_unindexed' in queryset.query.deferred_loading[0]

    def test_apply_defer_disallow_cross_relation(self):
        self.apply_raises({'defer': 'foreign__char_unindexed'})

    def test_apply_defer_disallow_cross_relation_override(self):
        self.assertRaises(
            self.Query.Issues,
            self.Query(
                {'defer': 'foreign__char_unindexed'},
                {'defer_allow_related': True}
            ).apply,
            Fake.objects.all(),
            defer_allow_related=False
        )

    def test_apply_defer_allow_cross_relation(self):
        queryset = self.apply_assert({'defer': 'foreign__char_unindexed'}, defer_allow_related=True)
        assert queryset.query.deferred_loading[1]
        assert 'foreign__char_unindexed' in queryset.query.deferred_loading[0]

    def test_apply_filter(self):
        self.apply_assert({'char_indexed': 'value'})

    def test_apply_filter_any(self):
        self.apply_assert({'char_indexed': 'value'}, filter=self.Query.Any)

    def test_apply_filter_specified(self):
        self.apply_assert({'char_indexed': 'value'}, filter=('char_indexed', ))

    def test_apply_filter_allow_cross_relation(self):
        self.apply_assert({'foreign__char_indexed': 'value'}, filter_allow_related=True)

    def test_apply_filter_disallow_cross_relation(self):
        self.apply_raises({'foreign__char_indexed': 'value'})

    def test_apply_filter_specified_but_not_used(self):
        self.apply_raises({'char_unindexed': 'value'}, filter=('char_indexed', ))

    def test_apply_filter_unindexed(self):
        self.apply_raises({'char_unindexed': 'value'})

    def test_apply_filter_at_least_one_indexed(self):
        self.apply_assert({'char_indexed': 'value', 'char_unindexed': 'value'})

    def test_apply_filter_lookup_any(self):
        self.apply_assert({'char_indexed__exact': 'value'}, filter_lookups=self.Query.Any)

    def test_apply_filter_lookup_specified(self):
        self.apply_assert({'char_indexed__exact': 'value'}, filter_lookups=('exact', ))

    def test_apply_filter_lookup_specified_but_not_used(self):
        self.apply_raises({'char_indexed__in': 'v1,v2'}, filter_lookups=('exact', ))

    def test_apply_filter_lookup_exact(self):
        self.apply_assert({'char_indexed__exact': 'v1'})

    def test_apply_filter_lookup_in(self):
        self.apply_assert({'char_indexed__in': 'v1,v2,v3'})

    def test_apply_filter_lookup_range(self):
        self.apply_assert({'char_indexed__range': 'v1,v2'})

    def test_apply_filter_lookup_range_more_than_2_params(self):
        self.apply_raises({'char_indexed__range': 'v1,v2,v3'})

    def test_apply_filter_lookup_isnull_truthy(self):
        self.apply_assert({'char_indexed__isnull': 'true'})

    def test_apply_filter_lookup_isnull_falsey(self):
        self.apply_assert({'char_indexed__isnull': 'false'})

    def test_apply_filter_lookup_isnull_invalid_param(self):
        self.apply_raises({'char_indexed__isnull': 'a'})

    def test_apply_limit(self):
        queryset = self.apply_assert({'limit': '1'})
        self.assertEqual(queryset.query.low_mark, 0)
        self.assertEqual(queryset.query.high_mark, 1)

    def test_apply_limit_default_limit(self):
        queryset = self.apply_assert({}, default_limit=1)
        self.assertEqual(queryset.query.low_mark, 0)
        self.assertEqual(queryset.query.high_mark, 1)

    def test_apply_limit_invalid(self):
        self.apply_raises({'limit': 'a'})

    def test_apply_limit_invalid_negative(self):
        self.apply_raises({'limit': '-1'})

    def test_apply_limit_gt_max(self):
        self.apply_raises({'limit': '21'}, max_limit=20)

    def test_apply_limit_is_zero(self):
        queryset = self.apply_assert({'limit': '0'})
        self.assertEqual(queryset.query.low_mark, 0)
        self.assertEqual(queryset.query.high_mark, None)

    def test_apply_limit_is_zero_with_max_limit(self):
        queryset = self.apply_assert({'limit': '0'}, max_limit=20)
        self.assertEqual(queryset.query.low_mark, 0)
        self.assertEqual(queryset.query.high_mark, 20)

    def test_apply_meta_page_0(self):
        queryset, meta = \
            self.Query({'limit': '10', 'char_indexed': 'value'}) \
            .apply(Fake.objects.all())

        assert meta['next'] == '?char_indexed=value&limit=10&offset=10'
        assert meta['previous'] is None

    def test_apply_meta_page_1(self):
        queryset, meta = \
            self.Query({'offset': '10', 'limit': '10', 'char_indexed': 'value'}) \
            .apply(Fake.objects.all())

        assert meta['next'] == '?char_indexed=value&limit=10&offset=20'
        assert meta['previous'] == '?char_indexed=value&limit=10&offset=0'

    def test_apply_offset(self):
        queryset = self.apply_assert({'limit': '1', 'offset': '1'})
        self.assertEqual(queryset.query.low_mark, 1)
        self.assertEqual(queryset.query.high_mark, 2)

    def test_apply_offset_invalid(self):
        self.apply_raises({'limit': '1', 'offset': 'a'})

    def test_apply_offset_invalid_negative(self):
        self.apply_raises({'limit': '1', 'offset': '-1'})

    def test_apply_offset_gt_max(self):
        self.apply_raises({'limit': '1', 'offset': '21'}, max_offset=20)

    def test_apply_only(self):
        queryset = self.apply_assert({'only': 'char_unindexed,char_indexed'})
        assert not queryset.query.deferred_loading[1]
        assert 'char_indexed' in queryset.query.deferred_loading[0]
        assert 'char_unindexed' in queryset.query.deferred_loading[0]

    def test_apply_only_disallow_cross_relation(self):
        self.apply_raises({'only': 'foreign__char_unindexed'})

    def test_apply_only_allow_cross_relation(self):
        queryset = self.apply_assert({'only': 'foreign__char_unindexed'}, only_allow_related=True)
        assert not queryset.query.deferred_loading[1]
        assert 'foreign__char_unindexed' in queryset.query.deferred_loading[0]

    def test_apply_order_by_indexed(self):
        self.apply_assert({'order_by': 'char_indexed'})

    def test_apply_order_by_at_least_one_indexed(self):
        self.apply_assert({'order_by': 'char_unindexed,char_indexed'})

    def test_apply_order_by_not_indexed(self):
        self.apply_raises({'order_by': 'char_unindexed'})

    def test_apply_order_by_disallow_cross_relation(self):
        self.apply_raises({'order_by': 'foreign__char_unindexed'})

    def test_apply_order_by_allow_cross_relation_indexed(self):
        self.apply_assert({'order_by': 'foreign__char_indexed'}, ordering_allow_related=True)

    def test_apply_order_by_allow_cross_relation_unindexed(self):
        self.apply_raises({'order_by': 'foreign__char_unindexed'}, ordering_allow_related=True)

    def test_apply_order_by_allow_specific_fields(self):
        self.apply_assert({'order_by': 'char_unindexed'}, ordering=('char_unindexed', ))

    def test_apply_order_by_allow_specific_fields_not_used(self):
        self.apply_raises({'order_by': 'char_indexed'}, ordering=('char_unindexed', ))

    def test_apply_order_by_allow_any_fields(self):
        self.apply_assert({'order_by': 'char_unindexed'}, ordering=self.Query.Any)

    def test_apply_order_by_allow_specific_fields_cross_relation_disallowed(self):
        self.apply_raises({'order_by': 'foreign__char_unindexed'}, ordering=('foreign__char_unindexed', ))

    def test_apply_order_by_allow_specific_fields_cross_relation_allowed(self):
        self.apply_assert({'order_by': 'foreign__char_unindexed'}, ordering_allow_related=True, ordering=('foreign__char_unindexed', ))

    def test_parse_field_multiple_lookups(self):
        self.assertRaises(self.Query.Error, self.Query({}).parse_field, 'field__in__in')
