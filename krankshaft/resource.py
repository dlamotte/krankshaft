from .query import DjangoQuery
from django.core.urlresolvers import reverse
from django.db import models

try:
    from django.db.transaction import atomic
except ImportError:
    from .compat.xact import xact as atomic

class DjangoModelResource(object):
    '''
    Expose a Django Model as a RESTful resource.  Default implementation
    attempts to expose as much configurability throughout your app.  If you so
    choose, you can re-implement parts of this to trade flexibility for
    performance (ie: use `queryset.values(...)`).

    It's as simple as:

        from django.db.models import get_model
        from krankshaft.resource import DjangoModelResource

        @api
        class Object(DjangoModelResource):
            model = get_model('app', 'Object')

    Options:

        excludes        list/tuple of field names to exclude from
                        serialize/deserialize
        fields          list/tuple of field names to serialize/deserialize
        use_location    instead of returning a serialized payload on POST/PUT,
                        use a Location header to point to where you may get
                        the representation (default: False)

    '''
    Query = DjangoQuery
    excludes = None
    fields = None
    model = None
    use_location = False

    def __init__(self):
        self.fields = tuple([
            field
            for field in
                list(self.model._meta.fields)
                + [field for field, model in self.model._meta.get_m2m_with_model()]
            if self.fields is None or field.name in self.fields
        ])

        if self.excludes:
            self.fields = tuple([
                field
                for field in self.fields
                if field.name not in self.excludes
            ])

        self.expected = {}
        self.expected_pk = None
        self.loaded = False
        self.related_lookup_cache = {}

    def clean_id(self, request, id):
        '''clean_id(request, id) -> clean_id

        Useful in situations where the id may be in an improper format.

        For example:

            ids = [self.clean_id(request, id) for id in '1;2;3;4'.split(';')]

        Without `clean_id()`, the id would be a string.  So when we go to check
        to see if we fetched all the proper instances from the database, a check
        like:

            set(ids) == set([instance.pk for instance in instances])

        Would fail simply because '1' (string) != 1 (integer).

        The request argument can be given None, but in this case, you are
        responsible for handling any raised api.ValueIssue.  If a request is
        given, this will automatically call `abort()` with an error response.
        '''
        try:
            return self.api.expect(self.expected_pk, id)
        except self.api.ValueIssue as exc:
            if not request:
                raise

            self.api.abort(self.api.serialize(request, 400, {
                'error': 'Invalid ID for model %s' % self.model.__name__,
                'invalid': exc.errors,
            }))

    def deserialize(self, request, data, instance=None):
        '''deserialize(request, data, instance=instance) -> instance

        Deserialize a request payload (`data`) into an instance (either given
        instance or will construct a new one).

        No further saving is required after this has been called.
        '''
        if instance is None:
            instance = self.model()

        try:
            clean = self.api.expect(self.expected, data, strict_dict=False)
        except self.api.ValueIssue as exc:
            self.api.abort(self.api.serialize(request, 415, {
                'error': 'Supplied data was invalid',
                'invalid': exc.errors,
            }))

        manytomany = {}
        for field in self.fields:
            if field.name not in clean:
                # since its not strictly enforcing extra/missing keys, if
                # the client didn't supply the field, stick with model defaults
                continue

            method = getattr(self, 'deserialize_%s' % field.name, None)
            if method:
                setattr(instance, field.name, method(instance, field, data))

            else:
                if isinstance(field, models.ManyToManyField):
                    resource = self.related_lookup(field)
                    manytomany[field] = resource.fetch(*clean[field.name])

                elif isinstance(field, models.ForeignKey):
                    setattr(instance, field.name + '_id', clean[field.name])

                else:
                    setattr(instance, field.name, clean[field.name])

        instance.save()
        for field, instances in manytomany.iteritems():
            manager = getattr(instance, field.name)
            manager.clear()
            manager.add(*instances)

            if hasattr(instance, '_prefetched_objects_cache') \
               and field.name in instance._prefetched_objects_cache:
                instance._prefetched_objects_cache[field.name] = \
                    instances

        return instance

    def endpoint(self, name):
        '''endpoint('list') -> 'api_v1_resource_list'

        Construct a name to be used in Django's reverse() or url(..., name=...).
        '''
        return self.api.endpoint(self.name + '_' + name)

    def fetch(self, *ids):
        '''fetch(*ids) -> [instance, ...]

        Fetch given resource primary keys from the database.  This enables
        resources to request other resources to fetch their related instances.

        When a resource attempts to resolve a URI into an instance:

            resource, ids = api.resolve(['/path/to/resource/1/'])
            instances = resource.fetch(*ids)

        It's convention to use the `fetch()` on a resource to retrieve the
        corresponding instances from the database.

        Order of requested ids is preserved.

        Allows `clean_id()` to raise Exceptions if given ids are invalid.  You
        are responsible for handling api.ValueIssue being raised from this.

        Model.DoesNotExist is raised when a given id(s) does not exist in the
        database.
        '''

        ids = [self.clean_id(None, id) for id in ids]
        instances = list(self.get_query_set(None).filter(pk__in=ids))
        set_ids = set(ids)
        set_instance_pks = set([instance.pk for instance in instances])
        if set_ids != set_instance_pks:
            missing = set_ids - set_instance_pks
            raise self.model.DoesNotExist(
                'Could not find instances for: %s' % ', '.join([
                    str(id) for id in list(missing)
                ])
            )

        instances.sort(key=lambda instance: ids.index(instance.pk))
        return instances

    def fetch_list(self, request, query):
        '''fetch_list(request, query) -> instances

        Ideally, calling functions would do:

            query, data = self.api.deserialize(request)
            instances, meta = self.fetch_list(request, query)

        '''
        if not isinstance(query, self.Query):
            query = self.Query(query)
        qs, meta = query.apply(self.get_query_set(request))
        instances = list(qs)

        if meta['next']:
            meta['next'] = self.reverse('list') + meta['next']

        if meta['previous']:
            meta['previous'] = self.reverse('list') + meta['previous']

        for instance in instances:
            self.is_authorized(request, instance)

        return instances, meta

    def fetch_set(self, request, idset):
        '''fetch_set(request, idset) -> instances

        Fetch a set of instances given idset which is in the format of a string
        of semi-colon separated ids.  Handles ensuring all instances are found.
        '''
        idset = [self.clean_id(request, id) for id in idset.split(';')]
        instances = list(self.get_query_set(request).filter(pk__in=idset))

        set_ids = set(idset)
        set_instance_pks = set([instance.pk for instance in instances])
        if set_ids != set_instance_pks:
            self.api.abort(self.api.serialize(request, 404, {
                'error': 'Missing some requested objects',
                'missing': list(set_ids - set_instance_pks),
            }))

        for instance in instances:
            self.is_authorized(request, instance)

        return instances

    def fetch_single(self, request, query, id):
        '''fetch_single(request, query, id) -> instance

        Fetch a single instance from the database handling when an instance
        isn't found or multiple are found when only one was expected.
        '''
        if query and not isinstance(query, self.Query):
            query = self.Query(query)

        qs = self.get_query_set(request)
        meta = None
        if query:
            qs, meta = query.apply(qs)

        try:
            instance = qs.get(pk=id)

        except self.model.DoesNotExist:
            self.api.abort(self.api.response(request, 404))

        self.is_authorized(request, instance)

        return instance

    def get_query_set(self, request):
        '''get_query_set(request) -> queryset

        Request may be `None` if no request authorization need be done.

        Typically, an endpoint will pass in the current request to possibly
        limit the queryset based on how the authorization of the API is setup.

        This also automatically sets up prefetching of ManyToManyField's.
        '''
        qs = self.model.objects.all()

        for field in self.fields:
            if isinstance(field, models.ManyToManyField):
                qs = qs.prefetch_related(field.name)

        if request is None:
            return qs
        else:
            return request.auth.limit(qs)

    def is_authorized(self, request, instance):
        '''is_authorized(request, instance)

        Abort if the request is not authorized for the instance.
        '''
        if not request.auth.is_authorized_obj(instance):
            self.api.abort(self.api.challenge(request, request.auth))

    def load(self):
        '''load()

        Called once all resources are registered allowing resources to auto
        configure themselves with eachother because they're all guaranteed to
        be registered at this point.

        This is typically invoked automatically once the API its registered with
        has its `.urls` property accessed.
        '''
        if self.loaded:
            return

        # preload related resources
        for field in self.fields:
            if not isinstance(field, (models.ForeignKey, models.ManyToManyField)):
                continue

            self.related_lookup_cache[field] = self.related_lookup(field)

        self.loaded = True
        self.load_post()

    def load_post(self):
        '''load_post()

        Routines to be run after load() because they depend on what happens
        during load() and depend on a post load state.
        '''
        self.expected.update({
            field.name: self.api.expecter.from_field(field)
            for field in self.fields
        })
        for field in self.fields:
            is_many = isinstance(field, models.ManyToManyField)
            is_related = is_many or isinstance(field, models.ForeignKey)
            if not is_related:
                continue

            self.expected[field.name] = self.make_related_validator(
                field,
                self.expected[field.name],
                many=is_many
            )

        self.expected_pk = self.expected[self.pk_name]

    def make_related_validator(self, field, expected, many=False):
        def related_validator(value, expect):
            resource = self.related_lookup(field)
            if value is not None and resource:
                try:
                    resolved_resource, value = \
                        self.api.resolve(value if many else [value])

                    if resolved_resource != resource:
                        raise self.api.ResolveError(
                            'Unexpected resource found: %s (expected %s)'
                            % (resolved_resource.name, resource.name)
                        )

                except self.api.ResolveError as e:
                    raise ValueError(
                        'Unable to resolve related: %s, %s' % (value, str(e))
                    )

                if not many:
                    value = value[0]

            return expect(expected, value)

        return related_validator

    def make_view(self, name, methods):
        '''make_view(self.endpoint('list'), {...}) -> resource_view

        Make a view that can resolve back to this resource and is suitable for
        use.
        '''
        def view(request, *args, **kwargs):
            return self.api.route(methods, request, args, kwargs)

        view.__name__ = name

        # so resolve() can find its way back from the view to the resource
        view.resource = self

        return view

    @property
    def name(self):
        '''
        Return a default resource name based on the resources class name.
        Removes instances of "Resource" in the name.

        Override by simply assigning a name in the class definition.
        '''
        return self.__class__.__name__.lower().replace('resource', '')

    @property
    def pk_name(self):
        return self.model._meta.pk.name

    def related(self, field, id):
        '''related(field, 1) -> 1 or '/path/to/resource/1/'

        Handle serializing related fields.  Default implementation is to
        return a URI representing the path to the resource.
        '''
        resource = self.related_lookup(field)
        if resource:
            return resource.reverse_single(id)
        else:
            return id

    def related_lookup(self, field):
        '''related_lookup() -> resource

        Lookup a resource for a related field.

        Returns None if a resource cannot be found.
        '''
        if self.loaded:
            return self.related_lookup_cache[field]

        else:
            model = field.rel.to
            for resource in self.api.registered_resources:
                if model is getattr(resource, 'model', None):
                    if hasattr(resource, 'instance'):
                        # adjust for API Class Helper
                        resource = resource.instance
                    return resource
            return None

    def reverse(self, name, *args, **kwargs):
        '''reverse('list') -> '/api/v1/resource/'

        Shortcut for creating urls related to this resource.
        '''
        return reverse(self.endpoint(name), *args, **kwargs)

    def reverse_single(self, id):
        '''reverse_single(instance.pk) -> '/resource/1/'

        Shortcut for creating a resource_uri.
        '''
        return self.reverse('single', args=(id,))

    def serialize(self, instance):
        '''serialize(instance) -> {...}

        Returns a dictionary ready for serialization into a response.  Suitable
        for using `api.serialize(request, code, ...)`.
        '''
        from django.db.models.query_utils import DeferredAttribute

        data = {}
        for field in self.fields:
            if (
                instance._deferred \
                and isinstance(
                    instance.__class__.__dict__.get(field.attname),
                    DeferredAttribute
                )
            ):
                # skip deferred fields
                continue

            method = getattr(self, 'serialize_%s' % field.name, None)
            if method:
                data[field.name] = method(instance, field)

            else:
                if isinstance(field, models.ManyToManyField):
                    qs = getattr(instance, field.name).all()
                    data[field.name] = [
                        self.related(field, related.pk)
                        for related in qs
                    ]
                    data[field.name + '_id'] = [
                        related.pk
                        for related in qs
                    ]

                elif isinstance(field, models.ForeignKey):
                    data[field.name] = self.related(
                        field,
                        getattr(instance, field.name + '_id')
                    )
                    data[field.name + '_id'] = \
                        getattr(instance, field.name + '_id')

                else:
                    data[field.name] = getattr(instance, field.name)

        data['resource_uri'] = self.reverse_single(instance.pk)

        return data

    @property
    def routes(self):
        '''
        Return a map of HTTP Method routes under an endpoint.

        ie:
            prefix = r'^%s/' % self.name
            return (
                ('name_of_url', prefix + r'endpoint/$', {
                    'method': self.view,
                    ...
                }),
                ...
            )

        '''
        prefix = r'^%s/' % self.name
        return (
            (self.endpoint('list'), prefix + '$', {
                'delete': self.delete_list,
                'get': self.get_list,
                'post': self.post_list,
                'put': self.put_list,
            }),
            (self.endpoint('single'), prefix + '(?P<id>[^/]+)/$', {
                'delete': self.delete,
                'get': self.get,
                'put': self.put,
            }),
            (self.endpoint('set'), prefix + 'set/(?P<idset>[^/](?:[^/]|;)*)/$', {
                'delete': self.delete_set,
                'get': self.get_set,
                'put': self.put_set,
            }),
        )

    @property
    def urls(self):
        '''
        Return the Django URLs needed to hook up this resource to URL routing.

        Typically you do not need to use this as the `api.urls` call will
        automatically pull this in.
        '''
        from django.conf.urls import patterns, include, url

        return patterns('', *[
            url(regex, self.api.wrap(self.make_view(name, methods)), name=name)
            for name, regex, methods in self.routes
        ])


    def delete(self, request, id):
        '''
        Deletes the object pointed to by id.

            /resource/1/

        '''
        with atomic():
            instance = self.fetch_single(request, None, id=id)
            instance.delete()

        return self.api.response(request, 204)

    def delete_list(self, request):
        '''
        Deletes the instances pointed to by the given query (specified by
        the query string).

            /resource/?field=value

        '''
        query, data = self.api.deserialize(request)

        with atomic():
            instances, meta = self.fetch_list(request, query)
            for instance in instances:
                instance.delete()

        return self.api.response(request, 204)

    def delete_set(self, request, idset):
        '''
        Delete the given set of objects (specified in the path as an id list
        separated by a semi-colon).

            /resource/set/1;2;3/

        '''
        with atomic():
            instances = self.fetch_set(request, idset)
            for instance in instances:
                instance.delete()

        return self.api.response(request, 204)


    def get(self, request, id):
        '''
        Get the serialized value of an object.

            /resource/1/

        '''
        query, data = self.api.deserialize(request)
        instance = self.fetch_single(request, query, id=id)

        return self.api.serialize(request, 200, self.serialize(instance))

    def get_list(self, request):
        '''
        Get the serialized value of a list of objects of a given query
        (specified as the query string).

            /resource/?field=value

        '''
        query, data = self.api.deserialize(request)
        instances, meta = self.fetch_list(request, query)

        return self.api.serialize(request, 200, {
            'meta': meta,
            'objects': [
                self.serialize(instance)
                for instance in instances
            ]
        })

    def get_set(self, request, idset):
        '''
        Get the serialized value of a set of objects given by a list of ids
        separated by a semi-colon.

            /resource/set/1;2;3/

        '''
        instances = self.fetch_set(request, idset)

        return self.api.serialize(request, 200, {
            'objects': [
                self.serialize(instance)
                for instance in instances
            ]
        })


    def post_list(self, request):
        '''
        Create a new object.

            /resource/

        '''
        query, data = self.api.deserialize(request)

        with atomic():
            instance = self.deserialize(request, data)

        if self.use_location:
            return self.api.response(request, 204,
                Location=self.reverse_single(instance.pk)
            )
        else:
            return self.api.serialize(request, 200, self.serialize(instance))


    def put(self, request, id):
        '''
        Update an object.

            /resource/1/

        '''
        query, data = self.api.deserialize(request)

        with atomic():
            instance = self.fetch_single(request, query, id=id)
            instance = self.deserialize(request, data, instance)

        if self.use_location:
            return self.api.response(request, 204,
                Location=self.reverse_single(instance.pk)
            )
        else:
            return self.api.serialize(request, 200, self.serialize(instance))

    def put_list(self, request):
        '''
        Given a single dictionary of fields and values, update all the instances
        with the given field/values.

        Ideally, a subset of all fields is given.  Enables mass update to
        an unknown set of objects (those matching a query).

            /resource/?field=value

        '''
        query, data = self.api.deserialize(request)

        # dont modify only part of the query, modify the whole thing
        query = self.Query(query).without('defer', 'limit', 'offset', 'only')

        with atomic():
            instances, meta = self.fetch_list(request, query)
            for instance in instances:
                self.deserialize(request, data, instance)

        if self.use_location:
            idset = ';'.join([
                str(instance.pk)
                for instance in instances
            ])
            return self.api.response(request, 204,
                Location=self.reverse('set', args=(idset, ))
            )

        else:
            return self.api.serialize(request, 200, {
                'meta': meta,
                'objects': [
                    self.serialize(instance)
                    for instance in instances
                ]
            })

    def put_set(self, request, idset):
        '''
        Update a set of objects.

            /resource/set/1;2;3/

        '''
        query, data = self.api.deserialize(request)

        with atomic():
            instances = self.fetch_set(request, idset)

            try:
                clean = self.api.expect([self.expected], data, strict_dict=False)
            except self.api.ValueIssue as exc:
                return self.api.serialize(request, 415, {
                    'error': 'Data format was invalid',
                    'invalid': exc.errors,
                })

            try:
                ids = [self.clean_id(request, obj[self.pk_name]) for obj in clean]
            except KeyError:
                return self.api.serialize(request, 400, {
                    'error': 'You must supply the primary key with each object'
                })

            instance_lookup = {
                instance.pk: instance
                for instance in instances
            }
            for obj in clean:
                id = self.clean_id(request, obj[self.pk_name])
                instance = instance_lookup[id]
                self.deserialize(request, obj, instance)

        if self.use_location:
            return self.api.response(request, 204,
                Location=self.reverse('set', args=(idset,))
            )

        else:
            return self.api.serialize(request, 200, {
                'objects': [
                    self.serialize(instance)
                    for instance in instances
                ]
            })
