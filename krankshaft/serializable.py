from .exceptions import KrankshaftError

class Serializable(object):
    '''
    Base definition of how to serialize a custom object.  Sub-class this
    to define a specific behavior for your object.

    Must be sub-classed in order to be used.
    '''
    class SkipField(KrankshaftError): pass
    class UpdateInvalidFields(KrankshaftError):
        def __init__(self, invalid):
            self.invalid = invalid
    class UpdateValueError(KrankshaftError): pass

    opts = {}

    def __init__(self, klass, **opts):
        self.klass = klass
        self.opts = self.defaults(opts)

    def convert(self, obj, **opts):
        raise NotImplementedError

    def convert_list(self, obj, **opts):
        raise NotImplementedError

    def defaults(self, opts):
        new = self.opts.copy()
        new.update(opts)
        return new

    def update(self, obj, data, **opts):
        raise NotImplementedError

# TODO apparently this is kind of hard...
#   - URI's for foreign keys implies understanding routing... need to change
#     strategy for this
#   - instead of 'configuration', subclass this and set a class variable
#     "model = MyModel" and configure/override methods as necessary, cleaner
#     and more flexible
#   - collection of helper methods for serialization instead of something that
#     "just works"... maybe we can build on top of that something that
#     "just works"
class SerializableDjangoModel(Serializable):
    '''
    Default Django Model Serialization behavior.

    Options:
        ignore_extra_fields: dont error if extra fields found during update
        query_many_to_many: query many to many relations that arent prefetched
        skip_deferred: skip converting deferred fields
    '''
    opts = {
        'ignore_extra_fields': True,
        'query_many_to_many': False,
        'skip_deferred': True,
    }
    def __init__(self, *args, **opts):
        super(SerializableDjangoModel, self).__init__(*args, **opts)

        meta = self.klass._meta
        self.fields = \
            [field for field, model in meta.get_fields_with_model()] \
            + [field for field, model in meta.get_m2m_with_model()]
        self.fields = tuple(self.fields)
        self.field_byname = {
            field.name: field
            for field in self.fields
        }

    def convert(self, obj, **opts):
        opts = self.defaults(opts)
        data = {}
        for field in self.fields:
            try:
                data[field.name] = self.get(obj, field, defaults=False, **opts)
            except self.SkipField:
                continue

        return data

    def convert_list(self, obj_list, **opts):
        opts = self.defaults(opts)
        # TODO

    def get(self, obj, field, defaults=True, **opts):
        from django.db import models
        from django.db.models.query_utils import DeferredAttribute

        if defaults:
            opts = self.defaults(opts)

        hook = lambda value: self.get_hook(value, obj, field)

        if isinstance(field, models.ManyToManyField):
            if not field.rel.through._meta.auto_created:
                raise self.SkipField

            manager = getattr(obj, field.attname)
            prefetched = getattr(obj, '_prefetched_objects_cache', {})
            if manager.prefetch_cache_name in prefetched \
               or opts['query_many_to_many']:
                return [
                    hook(model)
                    for model in manager.all()
                ]
            else:
                raise self.SkipField

        else:
            attr = field.name
            if isinstance(field, models.ForeignKey):
                attr = field.attname

            if obj._deferred \
               and isinstance(obj.__class__.__dict__.get(attr), DeferredAttribute) \
               and opts['skip_deferred']:
                raise self.SkipField

            else:
                return hook(getattr(obj, attr))

    def get_hook(self, value, obj, field):
        from django.db import models

        if isinstance(field, models.FileField):
            return value.url

        elif isinstance(field, models.ManyToManyField):
            return value.pk

        else:
            return value

    def set(self, obj, field, value):
        from django.db import models

        if isinstance(field, models.ManyToManyField):
            if not field.rel.through._meta.auto_created:
                return

            if not isinstance(value, (list, tuple)):
                raise self.UpdateValueError(
                    'Expected list/tuple for field "%s"' % field.name
                )
            manager = getattr(obj, field.attname)
            models = manager.model.objects.filter(pk__in=value)
            manager.clear()
            manager.add(*models)

        else:
            attr = field.name
            if isinstance(field, models.ForeignKey):
                attr = field.attname

            setattr(obj, attr, value)

    def update(self, obj, data, **opts):
        opts = self.defaults(opts)
        seen = {
            field.name: False
            for field in self.fields
        }

        items = data.items()
        if not opts['ignore_extra_fields']:
            invalid = []
            for field_name, value in items:
                if field_name not in seen:
                    invalid.append(field_name)

            if invalid:
                raise self.UpdateInvalidFields(invalid)

        for field_name, value in items:
            try:
                field = self.field_byname[field_name]
            except KeyError:
                continue
            self.set(obj, field, value)
