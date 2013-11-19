from . import util, valid
from .exceptions import KrankshaftError, QueryIssues

class Query(object):
    '''
    Encapsulate a parsed query string to allow for application to a specific
    ORM.
    '''
    Error = KrankshaftError
    Issues = QueryIssues

    defaults = {}

    def __init__(self, qs, opts=None):
        self.opts = self.options(opts or {}, self.defaults)
        self.qs = qs

    def apply(self, query, **opts):
        raise NotImplementedError('Unable to apply query')

    def copy(self):
        '''copy() -> new Query

        Create a copy of the current query.
        '''
        return self.__class__(self.qs.copy(), self.opts.copy())

    def options(self, opts, defaults):
        '''options({}, self.defaults) -> opts

        Setup options using defaults.
        '''
        return util.valid(
            util.defaults(opts, defaults),
            self.defaults.keys()
        )

    def without(self, *names):
        '''without('order_by') -> new Query

        Filter out aspects of a query.  A way to silently remove parts of a
        query.  If you'd prefer an error, disallow certain aspects of the query
        via the options on a Query or on the apply method.
        '''
        copy = self.copy()
        for name in names:
            if name in copy.qs:
                del copy.qs[name]

        return copy

class DjangoQuery(Query):
    '''
    Allow application of a query to a Django QuerySet.

    Options:

    The following options are default False, but if set to True allow queries
    to cross relations (ie: name__other_relation_name) in that specific field.

        defer_allow_related
        filter_allow_related
        only_allow_related
        ordering_allow_related

    The following options are default None, but if set are the default value
    if not specified in the request.  You can use this to specify a default
    ordering, limit, ...

        default_defer
        default_limit
        default_only
        default_order_by

    These options control which fields may be used during filtering or ordering.
    By default, they're set to the value of Indexed (a special value on this
    class).  The Indexed value's behavior is to require at least one specified
    field in the request must be indexed (for performance reasons).  You may
    also specify the Any special value on this class which allows any of the
    fields available to be used.  Lastly, you can specify a list/tuple of the
    fields you wish to only allow to be used.

        filter
        ordering

    Filter lookups are called "Field Lookups" in Django's documentation.  They
    look like this: field__startswith=...  It's value is default to the Any
    special value allowing any lookups to be used.  However, you can specify
    a list/tuple if you wish to only allow specific lookups.

        filter_lookups

    The max_limit option defines a maximum limit that can be specified.  If the
    request asks for a larger limit, it will be an error.  If the request uses
    the limit=0 option, the max_limit will be used.  By default, the max_limit
    is None.

        max_limit

    '''

    Any = object()
    Indexed = object()

    lookups_all = (
        'exact',
        'iexact',
        'contains',
        'icontains',
        'in',
        'gt',
        'gte',
        'lt',
        'lte',
        'startswith',
        'istartswith',
        'endswith',
        'iendswith',
        'range',
        'year',
        'month',
        'day',
        'week_day',
        'isnull',
        'search',
        'regex',
        'iregex',
    )

    values_bool_true = ('1', 'yes', 'true')
    values_bool_false = ('0', 'no', 'false', 'null')
    values_bool_all = values_bool_true + values_bool_false

    defaults = {
        'defer_allow_related': False,
        'filter': Indexed,
        'filter_allow_related': False,
        'filter_lookups': Any,
        'default_defer': None,
        'default_limit': None,
        'default_only': None,
        'default_order_by': None,
        'max_limit': None,
        'max_offset': None,
        'only_allow_related': False,
        'ordering': Indexed,
        'ordering_allow_related': False,
    }

    def apply(self, query, **opts):
        '''apply(queryset) -> new queryset with query, meta

        Apply query to queryset.

        Options may be specified to change the defaults set with this class.

            query.apply(queryset, default_limit=20)

        '''
        errors = []
        opts = self.options(opts, self.opts)

        model = query.model

        filter_uses_index = False
        used_filter = False
        for name, value in self.qs.iteritems():
            if name in ('defer', 'limit', 'offset', 'only', 'order_by'):
                continue

            used_filter = True

            accessor, lookup = self.parse_field(name)
            accessor_name = '__'.join(accessor)
            field = self.get_field(model, accessor)

            if not filter_uses_index:
                filter_uses_index = self.is_indexed(field)

            if opts['filter'] is not self.Any \
               and opts['filter'] is not self.Indexed \
               and accessor_name not in opts['filter']:
                errors.append('Unallowed filter used: %s' % name)
                continue

            if not opts['filter_allow_related'] and len(accessor) > 1:
                errors.append('Cross relation filters not allowed: %s' % name)
                continue

            if lookup \
               and opts['filter_lookups'] is not self.Any \
               and lookup not in opts['filter_lookups']:
                errors.append('Unallowed filter lookup used: %s' % name)
                continue

            if lookup == 'in':
                value = value.split(',')

            elif lookup == 'range':
                value = value.split(',')
                if len(value) != 2:
                    errors.append(
                        'A range lookup requires exactly 2 params: %s' % name
                    )
                    continue

            elif lookup == 'isnull':
                try:
                    value = valid.bool(value, None)
                except ValueError as exc:
                    errors.append(
                        'An isnull lookup requires a truthy/falsey value: %s'
                        % name
                    )

            query = query.filter(**{name: value})

        if used_filter \
           and opts['filter'] is self.Indexed \
           and not filter_uses_index:
            errors.append(
                'You are required to use an indexed field in the filter'
            )


        defer = self.qs.get('defer', opts['default_defer'])
        limit = self.qs.get('limit', opts['default_limit'])
        offset = self.qs.get('offset', 0)
        only = self.qs.get('only', opts['default_only'])
        order_by = self.qs.get('order_by', opts['default_order_by'])

        if defer:
            if isinstance(defer, basestring):
                defer = defer.split(',')

            for name in defer:
                accessor, lookup = self.parse_field(name)

                if not opts['defer_allow_related'] and len(accessor) > 1:
                    errors.append(
                        'Cross relation defer not allowed: %s' % name
                    )

            query = query.defer(*defer)

        if only:
            if isinstance(only, basestring):
                only = only.split(',')

            for name in only:
                accessor, lookup = self.parse_field(name)

                if not opts['only_allow_related'] and len(accessor) > 1:
                    errors.append(
                        'Cross relation only not allowed: %s' % name
                    )

            query = query.only(*only)

        if order_by:
            if isinstance(order_by, basestring):
                order_by = order_by.split(',')

            ordering_uses_index = False
            for name in order_by:
                accessor, lookup = self.parse_field(
                    name[1:] if name.startswith('-') else name
                )
                accessor_name = '__'.join(accessor)
                field = self.get_field(model, accessor)

                if not ordering_uses_index:
                    ordering_uses_index = self.is_indexed(field)

                if opts['ordering'] is not self.Any \
                   and opts['ordering'] is not self.Indexed \
                   and accessor_name not in opts['ordering']:
                    errors.append('Unallowed ordering used: %s' % name)

                if not opts['ordering_allow_related'] and len(accessor) > 1:
                    errors.append(
                        'Cross relation ordering not allowed: %s' % name
                    )

            if opts['ordering'] is self.Indexed and not ordering_uses_index:
                errors.append(
                    'You are required to use an indexed field in the order_by'
                )

            query = query.order_by(*order_by)

        if limit:
            try:
                limit = int(limit)
                if offset:
                    offset = int(offset)
            except ValueError:
                errors.append('You must specify an integer for limit/offset')
            else:
                if offset:
                    if opts['max_offset'] and offset > opts['max_offset']:
                        errors.append(
                            'Your offset is above the maximum allowed: %s '
                            % opts['max_offset']
                        )
                        offset = 0

                    elif offset < 0:
                        errors.append('A offset must be positive')
                        offset = 0

                if opts['max_limit'] and limit > opts['max_limit']:
                    errors.append(
                        'Your limit is above the maximum allowed: %s'
                        % opts['max_limit']
                    )

                elif limit == 0:
                    limit = opts['max_limit']
                    if limit:
                        query = query[offset : offset + limit]

                elif limit < 0:
                    errors.append('A limit must be positive')

                else:
                    query = query[offset : offset + limit]

        if errors:
            raise self.Issues(*errors)

        return query, self.make_meta(limit, offset)

    def get_field(self, model, accessor):
        field = None
        first = True
        for attr in accessor:
            if first:
                field = model._meta.get_field_by_name(attr)[0]

            else:
                field = field.rel.to._meta.get_field_by_name(attr)[0]
            first = False

        return field

    def is_indexed(self, field):
        return field.db_index or field.primary_key

    def make_meta(self, limit, offset):
        meta = {
            'limit': limit,
            'next': None,
            'offset': offset,
            'previous': None,
        }

        if limit is None or offset is None:
            return meta

        base = ''
        for name, value in self.qs.iteritems():
            if name in ('limit', 'offset'):
                continue

            base += '&' if base else '?'
            base += name + '=' + value

        base += '&' if base else '?'

        meta['next'] = base + 'limit=%s&offset=%s' % (limit, offset + limit)
        if offset >= limit:
            meta['previous'] = \
                base + 'limit=%s&offset=%s' % (limit, offset - limit)

        return meta

    def parse_field(self, name):
        parsed = []
        lookup = None

        for part in name.split('__'):
            if part in self.lookups_all:
                if lookup:
                    raise self.Error(
                        'Multiple lookups found for field: %s' % name
                    )
                lookup = part

            else:
                parsed.append(part)

        return tuple(parsed), lookup

    def without(self, *names):
        copy = super(DjangoQuery, self).without(*names)

        if 'defer' in names:
            copy.opts['default_defer'] = None

        if 'limit' in names:
            copy.opts['default_limit'] = None
            copy.opts['max_limit'] = None

        if 'only' in names:
            copy.opts['default_only'] = None

        if 'order_by' in names:
            copy.opts['default_order_by'] = None

        if 'offset' in names:
            copy.opts['max_offset'] = None

        return copy
