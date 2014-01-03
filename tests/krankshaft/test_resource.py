from __future__ import absolute_import

from datetime import datetime
from django.db import models
from krankshaft.api import API as APIBase
from krankshaft.auth import Auth as AuthBase
from krankshaft.authn import Authn
from krankshaft.authz import Authz as AuthzBase
from krankshaft.resource import DjangoModelResource
from tests.base import TestCaseNoDB
import base64
import json
import os
import pytest
import shutil
import tempfile
import unittest

try:
    from PIL import Image
except ImportError:
    Image = None

IMAGE_JPG = base64.decodestring(''.join('''
/9j/4AAQSkZJRgABAQEAAQABAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkI
CQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/2wBDAQMDAwQDBAgEBAgQCwkLEBAQEBAQ
EBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/wAARCAABAAEDASIA
AhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEB
AAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AKOgA//Z
'''.splitlines()))

IMAGE_JPG_INVALID = base64.decodestring(''.join('''
/9j/4AAQSkZJRgABAQEAAQABAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkI
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
EBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/wAARCAABAAEDASIA
AhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEB
AAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AKOgA//Z
'''.splitlines()))

class Authz(AuthzBase):
    def is_authorized_object(self, request, authned, obj):
        return obj.__class__ is not ModelUnauthorized

class Auth(AuthBase):
    authn = Authn()
    authz = Authz(require_authned=False)

class API(APIBase):
    Auth = Auth

    def handler500(self, request, exc_info, error=None):
        raise

class ModelForeign(models.Model):
    char_indexed = models.CharField(max_length=20, db_index=True)
    created = models.DateTimeField(default=datetime.now)

class ModelForeign2(models.Model):
    char_indexed = models.CharField(max_length=20, db_index=True)

class ModelForeign3(models.Model):
    char_indexed = models.CharField(max_length=20, db_index=True)

class ModelForeignNoResource(models.Model):
    name = models.CharField(max_length=20, db_index=True)

class ModelForeignNoResourceForeign(models.Model):
    foreign = models.ForeignKey(ModelForeignNoResource)

class ModelHasForeign3(models.Model):
    foreign = models.ForeignKey(ModelForeign3)

class ModelMany(models.Model):
    char_indexed = models.CharField(max_length=20, db_index=True)

class ModelName(models.Model):
    name = models.CharField(max_length=20, db_index=True)

class ModelOther(models.Model):
    seconds = models.PositiveIntegerField(default=0)

class ModelUnauthorized(models.Model):
    name = models.CharField(max_length=20, db_index=True)

class Model(models.Model):
    char_indexed = models.CharField(max_length=20, db_index=True)
    foreign = models.ForeignKey(ModelForeign, null=True)
    manytomany = models.ManyToManyField(ModelMany)

class ModelAllowed(models.Model):
    name = models.CharField(max_length=20)

class ModelVersioned(models.Model):
    name = models.CharField(max_length=20)
    version = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        self.version += 1
        return super(ModelVersioned, self).save(*args, **kwargs)

class ModelFiles(models.Model):
    file = models.FileField(max_length=300, upload_to='files/')
    image = models.ImageField(max_length=300, upload_to='images/')

@pytest.mark.django_db
class ResourceTest(TestCaseNoDB):
    def _pre_setup(self):
        api = self.api = API('v1', debug=True)
        api2 = self.api2 = API('v2', debug=True)

        @api
        class NameResource(DjangoModelResource):
            model = ModelName

        @api
        class ModelForeignResource(DjangoModelResource):
            model = ModelForeign
            excludes = ('created',)

        @api2
        class ModelForeign2Resource(DjangoModelResource):
            model = ModelForeign2
            use_location = True

        @api
        class ModelForeign3Resource(DjangoModelResource):
            model = ModelForeign3

        @api
        class ModelForeignNoResourceForeignResource(DjangoModelResource):
            model = ModelForeignNoResourceForeign
            name = 'modelforeignnoresourceforeign'

        @api
        class ModelHasForeign3Resource(DjangoModelResource):
            model = ModelHasForeign3

            def serialize_foreign(self, instance, field):
                resource = self.related_lookup(field)
                return resource.serialize(getattr(instance, field.name))

        @api
        class ModelManyResource(DjangoModelResource):
            model = ModelMany

        @api
        class ModelOtherResource(DjangoModelResource):
            model = ModelOther

            def deserialize_seconds(self, instance, field, data):
                return data['seconds'] / 10

            def serialize_seconds(self, instance, field):
                return instance.seconds * 10

        @api
        class ModelUnauthorizedResource(DjangoModelResource):
            model = ModelUnauthorized

        @api
        class ModelResource(DjangoModelResource):
            model = Model

        @api
        class ModelAllowedResource(DjangoModelResource):
            model = ModelAllowed
            allowed_methods = ('get',)

        @api
        class ModelAllowed2Resource(DjangoModelResource):
            model = ModelAllowed
            allowed_methods_endpoint = {
                'list': ('get',),
                'single': ('get',),
                'set': ('get',),
            }

        @api
        class ModelVersionedResource(DjangoModelResource):
            model = ModelVersioned
            version_field = 'version'

        @api
        class ModelFilesResource(DjangoModelResource):
            model = ModelFiles

        # only to satisfy coverage (calling load() twice)
        for resource in self.api.registered_resources:
            resource.load()

        super(ResourceTest, self)._pre_setup()

    def tearDown(self):
        for model in [
            resource.model
            for resource in self.api.registered_resources
        ] + [
            resource.model
            for resource in self.api2.registered_resources
        ] + [
            ModelForeignNoResource,
        ]:
            model.objects.all().delete()

    def test_allowed(self):
        ModelAllowed.objects.create(id=1, name='allowed')
        ModelAllowed.objects.create(id=2, name='allowed2')

        for code, method in (
            (405, self.client.delete),
            (200, self.client.get),
            (405, self.client.post),
            (405, self.client.put),
        ):
            for endpoint, args in (
                ('list', ()),
                ('single', (1,)),
                ('set', ('1;2',)),
            ):
                response = method(
                    self.api.reverse('modelallowed_' + endpoint, args=args)
                )
                assert response.status_code == code

                response = method(
                    self.api.reverse('modelallowed2_' + endpoint, args=args)
                )
                assert response.status_code == code

    def test_delete_list(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        ModelForeign.objects.create(id=2, char_indexed='value1')
        ModelForeign.objects.create(id=3, char_indexed='value2')
        ModelForeign.objects.create(id=4, char_indexed='other')
        response = self.client.delete(
            self.api.reverse('modelforeign_list')
            + '?char_indexed__startswith=value'
        )

        assert response.status_code == 204
        assert response.content == ''
        assert ModelForeign.objects.count() == 1
        assert ModelForeign.objects.all()[0].id == 4

    def test_delete_set(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        ModelForeign.objects.create(id=2, char_indexed='value1')
        ModelForeign.objects.create(id=3, char_indexed='value2')
        ModelForeign.objects.create(id=4, char_indexed='other')
        response = self.client.delete(
            self.api.reverse('modelforeign_set', args=('1;3',))
        )

        assert response.status_code == 204
        assert response.content == ''
        assert ModelForeign.objects.count() == 2
        assert list(ModelForeign.objects.values_list('id', flat=True)) == [2, 4]

    def test_delete_single(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        response = self.client.delete(
            self.api.reverse('modelforeign_single', args=(1,))
        )

        assert response.status_code == 204
        assert response.content == ''

    def test_exclude_error(self):
        class ModelResource(DjangoModelResource):
            model = Model
            exclude = 'anything'

        self.assertRaises(ModelResource.Error, ModelResource)

    def test_fetch_invalid_id(self):
        resource, ids = self.api.resolve([
            self.api.reverse('modelother_single', args=('invalid',)),
        ])
        self.assertRaises(
            self.api.ValueIssue,
            resource.fetch,
            *ids
        )

    def test_files_file(self):
        tmpdir = tempfile.mkdtemp()
        try:
            with self.settings(MEDIA_ROOT=tmpdir), \
                 tempfile.NamedTemporaryFile() as tmp:
                tmp.write('hello world\n')
                tmp.seek(0)
                response = self.client.post(
                    self.api.reverse('modelfiles_list'),
                    {'file': tmp}
                )

                assert response.status_code == 200
                assert json.loads(response.content) == {
                    'file': 'files/' + os.path.basename(tmp.name),
                    'file_href': '/media/files/' + os.path.basename(tmp.name),
                    'id': 1,
                    'image': '',
                    'image_href': '',
                    '_id': 1,
                    '_pk': 'id',
                    '_uri': '/api/v1/modelfiles/1/',
                }

                response = self.client.put(
                    self.api.reverse('modelfiles_single', args=(1,)),
                    {'file': 'wont change anything'}
                )

                assert response.status_code == 422

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @unittest.skipIf(not Image, 'requires PIL/Pillow')
    def test_files_image(self):
        tmpdir = tempfile.mkdtemp()
        try:
            with self.settings(MEDIA_ROOT=tmpdir), \
                 tempfile.NamedTemporaryFile() as tmp:
                tmp.write(IMAGE_JPG)
                tmp.seek(0)
                response = self.client.post(
                    self.api.reverse('modelfiles_list'),
                    {'image': tmp}
                )

                assert response.status_code == 200
                assert json.loads(response.content) == {
                    'file': '',
                    'file_href': '',
                    'id': 2,
                    'image': 'images/' + os.path.basename(tmp.name),
                    'image_href': '/media/images/' + os.path.basename(tmp.name),
                    '_id': 2,
                    '_pk': 'id',
                    '_uri': '/api/v1/modelfiles/2/',
                }

                response = self.client.put(
                    self.api.reverse('modelfiles_single', args=(2,)),
                    {'image': 'wont change anything'}
                )

                assert response.status_code == 422

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_get_list(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        ModelForeign.objects.create(id=2, char_indexed='value2')
        ModelForeign.objects.create(id=3, char_indexed='value3')
        ModelForeign.objects.create(id=4, char_indexed='other')
        response = self.client.get(
            self.api.reverse('modelforeign_list')
            + '?char_indexed__startswith=value&order_by=id'
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'meta': {
                'limit': None,
                'next': None,
                'offset': 0,
                'previous': None
            },
            'objects': [
                {
                    'id': 1,
                    'char_indexed': 'value',
                    '_id': 1,
                    '_pk': 'id',
                    '_uri': '/api/v1/modelforeign/1/'
                },
                {
                    'id': 2,
                    'char_indexed': 'value2',
                    '_id': 2,
                    '_pk': 'id',
                    '_uri': '/api/v1/modelforeign/2/'
                },
                {
                    'id': 3,
                    'char_indexed': 'value3',
                    '_id': 3,
                    '_pk': 'id',
                    '_uri': '/api/v1/modelforeign/3/'
                },
            ]
        }

    def test_get_list_paginate(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        ModelForeign.objects.create(id=2, char_indexed='value2')
        ModelForeign.objects.create(id=3, char_indexed='value3')
        ModelForeign.objects.create(id=4, char_indexed='other')
        response = self.client.get(
            self.api.reverse('modelforeign_list')
            + '?char_indexed__startswith=value&order_by=id&limit=1'
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'meta': {
                'limit': 1,
                'next': '/api/v1/modelforeign/?order_by=id&char_indexed__startswith=value&limit=1&offset=1',
                'offset': 0,
                'previous': None
            },
            'objects': [
                {
                    'id': 1,
                    'char_indexed': 'value',
                    '_id': 1,
                    '_pk': 'id',
                    '_uri': '/api/v1/modelforeign/1/'
                },
            ]
        }

        response = self.client.get(
            '/api/v1/modelforeign/?order_by=id&char_indexed__startswith=value&limit=1&offset=1',
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'meta': {
                'limit': 1,
                'next': '/api/v1/modelforeign/?order_by=id&char_indexed__startswith=value&limit=1&offset=2',
                'offset': 1,
                'previous': '/api/v1/modelforeign/?order_by=id&char_indexed__startswith=value&limit=1&offset=0',
            },
            'objects': [
                {
                    'id': 2,
                    'char_indexed': 'value2',
                    '_id': 2,
                    '_pk': 'id',
                    '_uri': '/api/v1/modelforeign/2/'
                },
            ]
        }

    def test_get_set(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        ModelForeign.objects.create(id=2, char_indexed='value2')
        ModelForeign.objects.create(id=3, char_indexed='value3')
        ModelForeign.objects.create(id=4, char_indexed='other')
        response = self.client.get(
            self.api.reverse('modelforeign_set', args=('1;3',))
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'objects': [
                {
                    'id': 1,
                    'char_indexed': 'value',
                    '_id': 1,
                    '_pk': 'id',
                    '_uri': '/api/v1/modelforeign/1/'
                },
                {
                    'id': 3,
                    'char_indexed': 'value3',
                    '_id': 3,
                    '_pk': 'id',
                    '_uri': '/api/v1/modelforeign/3/'
                },
            ]
        }

    def test_get_set_invalid_id(self):
        response = self.client.get(
            self.api.reverse('modelforeign_set', args=('invalid',))
        )

        assert response.status_code == 400
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'error': 'Invalid ID for model ModelForeign',
            'invalid': [u"invalid literal for int() with base 10: 'invalid'"],
        }

    def test_get_set_missing(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        ModelForeign.objects.create(id=2, char_indexed='value2')
        ModelForeign.objects.create(id=4, char_indexed='other')
        response = self.client.get(
            self.api.reverse('modelforeign_set', args=('1;3',))
        )

        assert response.status_code == 404
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'error': 'Missing some requested objects',
            'missing': [3],
        }

    def test_get_set_trailing_separator(self):
        response = self.client.get(
            self.api.reverse('modelforeign_set', args=('1;2;',))
        )

        assert response.status_code == 400
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'error': 'Invalid ID for model ModelForeign',
            'invalid': [u"int_or_none_range_1_to_2147483647_no_none_blank_not does not accept blank values"],
        }

    def test_get_single(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        response = self.client.get(
            self.api.reverse('modelforeign_single', args=(1,))
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            'char_indexed': 'value',
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/modelforeign/1/'
        }

    def test_get_single_foreign_null(self):
        Model.objects.create(id=1, foreign=None)

        response = self.client.get(
            self.api.reverse('model_single', args=(1,)),
        )
        assert response.status_code == 200
        assert json.loads(response.content) == {
            'id': 1,
            'char_indexed': '',
            'foreign': None,
            'foreign_id': None,
            'manytomany': [],
            'manytomany_id': [],
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/model/1/',
        }

    def test_get_single_missing(self):
        response = self.client.get(
            self.api.reverse('modelforeign_single', args=(1,))
        )

        assert response.status_code == 404
        assert response.content == ''

    def test_get_single_no_foreign_resource(self):
        ModelForeignNoResource.objects.create(id=1, name='foreign')
        ModelForeignNoResourceForeign.objects.create(id=1, foreign_id=1)

        response = self.client.get(
            self.api.reverse('modelforeignnoresourceforeign_single', args=(1,))
        )
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            'foreign': 1,
            'foreign_id': 1,
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/modelforeignnoresourceforeign/1/'
        }

    def test_get_single_defer_char_indexed(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        response = self.client.get(
            self.api.reverse('modelforeign_single', args=(1,))
            + '?defer=char_indexed'
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/modelforeign/1/'
        }

    def test_get_single_only_id(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        response = self.client.get(
            self.api.reverse('modelforeign_single', args=(1,))
            + '?only=id'
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/modelforeign/1/'
        }

    def test_get_single_unauthorized(self):
        ModelUnauthorized.objects.create(id=1, name='notauthzed')
        response = self.client.get(
            self.api.reverse('modelunauthorized_single', args=(1,))
        )

        assert response.status_code == 401
        assert response.content == ''

    def test_hook_serialize_field(self):
        ModelOther.objects.create(id=1, seconds=10)
        response = self.client.get(
            self.api.reverse('modelother_single', args=(1,))
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            'seconds': 100,
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/modelother/1/'
        }

        response = self.client.put(
            self.api.reverse('modelother_single', args=(1,)),
            json.dumps({'seconds': 10}),
            content_type='application/json'
        )
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            'seconds': 10,
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/modelother/1/'
        }

        other = ModelOther.objects.get(id=1)
        assert other.seconds == 1

    def test_many_to_many_update(self):
        foreign = ModelForeign.objects.create(id=1, char_indexed='value')
        many = ModelMany.objects.create(id=1, char_indexed='value')
        many2 = ModelMany.objects.create(id=2, char_indexed='value2')
        instance = Model.objects.create(id=1, char_indexed='value', foreign=foreign)
        instance.manytomany.add(many)

        response = self.client.get(self.api.reverse('model_single', args=(1,)))
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            'char_indexed': 'value',
            'foreign': '/api/v1/modelforeign/1/',
            'foreign_id': 1,
            'manytomany': ['/api/v1/modelmany/1/'],
            'manytomany_id': [1],
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/model/1/'
        }

        response = self.client.put(
            self.api.reverse('model_single', args=(1,)),
            json.dumps({'manytomany': [
                '/api/v1/modelmany/2/',
            ]}),
            content_type='application/json'
        )
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            'char_indexed': 'value',
            'foreign': '/api/v1/modelforeign/1/',
            'foreign_id': 1,
            'manytomany': ['/api/v1/modelmany/2/'],
            'manytomany_id': [2],
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/model/1/'
        }

    def test_post_list(self):
        response = self.client.post(
            self.api.reverse('modelforeign_list'),
            json.dumps({'id': 1, 'char_indexed': 'posted'}),
            content_type='application/json'
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            'char_indexed': 'posted',
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/modelforeign/1/'
        }

        instance = ModelForeign.objects.get(id=1)
        assert instance.char_indexed == 'posted'
        assert instance.created is not None

    def test_post_list_location(self):
        response = self.client.post(
            self.api2.reverse('modelforeign2_list'),
            json.dumps({'id': 1, 'char_indexed': 'posted'}),
            content_type='application/json'
        )

        assert response.status_code == 204
        assert response.content == ''
        assert response['Location'].endswith(self.api2.reverse('modelforeign2_single', args=(1,)))

        response = self.client.get(response['Location'])
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            'char_indexed': 'posted',
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v2/modelforeign2/1/'
        }

        instance = ModelForeign2.objects.get(id=1)
        assert instance.char_indexed == 'posted'

    def test_put_list(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        ModelForeign.objects.create(id=2, char_indexed='value2')
        ModelForeign.objects.create(id=3, char_indexed='value3')
        ModelForeign.objects.create(id=4, char_indexed='other')
        response = self.client.put(
            self.api.reverse('modelforeign_list')
                + '?char_indexed__startswith=value&order_by=id',
            json.dumps({'char_indexed': 'massupdate'}),
            content_type='application/json'
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'meta': {
                'limit': None,
                'next': None,
                'offset': 0,
                'previous': None
            },
            'objects': [
                {
                    'id': 1,
                    'char_indexed': 'massupdate',
                    '_id': 1,
                    '_pk': 'id',
                    '_uri': '/api/v1/modelforeign/1/'
                },
                {
                    'id': 2,
                    'char_indexed': 'massupdate',
                    '_id': 2,
                    '_pk': 'id',
                    '_uri': '/api/v1/modelforeign/2/'
                },
                {
                    'id': 3,
                    'char_indexed': 'massupdate',
                    '_id': 3,
                    '_pk': 'id',
                    '_uri': '/api/v1/modelforeign/3/'
                },
            ],
        }

        id1 = ModelForeign.objects.get(id=1)
        id2 = ModelForeign.objects.get(id=2)
        id3 = ModelForeign.objects.get(id=3)
        id4 = ModelForeign.objects.get(id=4)
        assert id1.char_indexed == 'massupdate'
        assert id2.char_indexed == 'massupdate'
        assert id3.char_indexed == 'massupdate'
        assert id4.char_indexed == 'other'

    def test_put_list_location(self):
        ModelForeign2.objects.create(id=1, char_indexed='value')
        ModelForeign2.objects.create(id=2, char_indexed='value2')
        ModelForeign2.objects.create(id=3, char_indexed='value3')
        ModelForeign2.objects.create(id=4, char_indexed='other')
        response = self.client.put(
            self.api2.reverse('modelforeign2_list')
                + '?char_indexed__startswith=value&order_by=id',
            json.dumps({'char_indexed': 'massupdate'}),
            content_type='application/json'
        )

        assert response.status_code == 204
        assert response.content == ''
        assert response['Location'].endswith(
            self.api2.reverse('modelforeign2_set', args=('1;2;3', ))
        )

        response = self.client.get(response['Location'])
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'objects': [
                {
                    'id': 1,
                    'char_indexed': 'massupdate',
                    '_id': 1,
                    '_pk': 'id',
                    '_uri': '/api/v2/modelforeign2/1/'
                },
                {
                    'id': 2,
                    'char_indexed': 'massupdate',
                    '_id': 2,
                    '_pk': 'id',
                    '_uri': '/api/v2/modelforeign2/2/'
                },
                {
                    'id': 3,
                    'char_indexed': 'massupdate',
                    '_id': 3,
                    '_pk': 'id',
                    '_uri': '/api/v2/modelforeign2/3/'
                },
            ],
        }

        id1 = ModelForeign2.objects.get(id=1)
        id2 = ModelForeign2.objects.get(id=2)
        id3 = ModelForeign2.objects.get(id=3)
        id4 = ModelForeign2.objects.get(id=4)
        assert id1.char_indexed == 'massupdate'
        assert id2.char_indexed == 'massupdate'
        assert id3.char_indexed == 'massupdate'
        assert id4.char_indexed == 'other'

    def test_put_set(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        ModelForeign.objects.create(id=2, char_indexed='value2')
        ModelForeign.objects.create(id=3, char_indexed='value3')
        ModelForeign.objects.create(id=4, char_indexed='other')
        response = self.client.put(
            self.api.reverse('modelforeign_set', args=('1;3',)),
            json.dumps([
                {'id': 1, 'char_indexed': 'setupdate1'},
                {'id': 3, 'char_indexed': 'setupdate3'},
            ]),
            content_type='application/json'
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'objects': [
                {
                    'id': 1,
                    'char_indexed': 'setupdate1',
                    '_id': 1,
                    '_pk': 'id',
                    '_uri': '/api/v1/modelforeign/1/'
                },
                {
                    'id': 3,
                    'char_indexed': 'setupdate3',
                    '_id': 3,
                    '_pk': 'id',
                    '_uri': '/api/v1/modelforeign/3/'
                },
            ],
        }

        id1 = ModelForeign.objects.get(id=1)
        id3 = ModelForeign.objects.get(id=3)
        assert id1.char_indexed == 'setupdate1'
        assert id3.char_indexed == 'setupdate3'

    def test_put_set_invalid_format(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        ModelForeign.objects.create(id=3, char_indexed='value3')
        response = self.client.put(
            self.api.reverse('modelforeign_set', args=('1;3',)),
            json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 422
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'error': 'Supplied data was invalid',
            'invalid': ["Unexpected type, expected <type 'list'>: <type 'dict'>"],
        }

    def test_put_set_location(self):
        ModelForeign2.objects.create(id=1, char_indexed='value')
        ModelForeign2.objects.create(id=2, char_indexed='value2')
        ModelForeign2.objects.create(id=3, char_indexed='value3')
        ModelForeign2.objects.create(id=4, char_indexed='other')
        response = self.client.put(
            self.api2.reverse('modelforeign2_set', args=('1;3',)),
            json.dumps([
                {'id': 1, 'char_indexed': 'setupdate1'},
                {'id': 3, 'char_indexed': 'setupdate3'},
            ]),
            content_type='application/json'
        )

        assert response.status_code == 204
        assert response.content == ''
        assert response['Location'].endswith(
            self.api2.reverse('modelforeign2_set', args=('1;3', ))
        )

        response = self.client.get(response['Location'])
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'objects': [
                {
                    'id': 1,
                    'char_indexed': 'setupdate1',
                    '_id': 1,
                    '_pk': 'id',
                    '_uri': '/api/v2/modelforeign2/1/'
                },
                {
                    'id': 3,
                    'char_indexed': 'setupdate3',
                    '_id': 3,
                    '_pk': 'id',
                    '_uri': '/api/v2/modelforeign2/3/'
                },
            ],
        }

        id1 = ModelForeign2.objects.get(id=1)
        id3 = ModelForeign2.objects.get(id=3)
        assert id1.char_indexed == 'setupdate1'
        assert id3.char_indexed == 'setupdate3'

    def test_put_set_must_include_id_in_representation(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        ModelForeign.objects.create(id=2, char_indexed='value2')
        ModelForeign.objects.create(id=3, char_indexed='value3')
        ModelForeign.objects.create(id=4, char_indexed='other')
        response = self.client.put(
            self.api.reverse('modelforeign_set', args=('1;3',)),
            json.dumps([
                {'char_indexed': 'setupdate1'},
                {'char_indexed': 'setupdate3'},
            ]),
            content_type='application/json'
        )

        assert response.status_code == 400
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'error': 'You must supply the primary key with each object',
        }

    def test_put_single(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        response = self.client.put(
            self.api.reverse('modelforeign_single', args=(1,)),
            json.dumps({'char_indexed': 'updated'}),
            content_type='application/json'
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            'char_indexed': 'updated',
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/modelforeign/1/'
        }

        instance = ModelForeign.objects.get(id=1)
        assert instance.char_indexed == 'updated'
        assert instance.created is not None

    def test_put_single_location(self):
        ModelForeign2.objects.create(id=1, char_indexed='value')
        response = self.client.put(
            self.api2.reverse('modelforeign2_single', args=(1,)),
            json.dumps({'char_indexed': 'updated'}),
            content_type='application/json'
        )

        assert response.status_code == 204
        assert response.content == ''
        assert response['Location'].endswith(self.api2.reverse('modelforeign2_single', args=(1,)))

        response = self.client.get(response['Location'])
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            'char_indexed': 'updated',
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v2/modelforeign2/1/'
        }

        instance = ModelForeign2.objects.get(id=1)
        assert instance.char_indexed == 'updated'

    def test_put_single_invalid_manytomany(self):
        ModelForeign.objects.create(id=1)
        Model.objects.create(id=1, foreign_id=1)

        response = self.client.put(
            self.api.reverse('model_single', args=(1,)),
            json.dumps({
                'manytomany': [
                    '/api/v1/modelforeign/invalid/',
                ]
            }),
            content_type='application/json'
        )
        assert response.status_code == 422
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'error': 'Supplied data was invalid',
            'invalid': {
                'manytomany': ["Unable to resolve related: [u'invalid'], Unexpected resource found: modelforeign (expected modelmany)"]
            },
        }

    def test_query_issues(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        ModelForeign.objects.create(id=2, char_indexed='value1')
        ModelForeign.objects.create(id=3, char_indexed='value2')
        ModelForeign.objects.create(id=4, char_indexed='other')
        response = self.client.get(
            self.api.reverse('modelforeign_list')
            + '?order_by=created'
        )

        assert response.status_code == 403
        assert json.loads(response.content) == {
            'error': 'There are issues with your query',
            'invalid': [
                'You are required to use an indexed field in the order_by',
            ],
        }

    def test_query_issues_invalid_field(self):
        response = self.client.get(
            self.api.reverse('modelforeign_list')
            + '?notavalidfield=1'
        )

        assert response.status_code == 403
        assert json.loads(response.content) == {
            'error': 'There are issues with your query',
            'invalid': [
                "ModelForeign has no field named 'notavalidfield'",
            ],
        }

    def test_resource_deserialize(self):
        response = self.client.post(
            self.api.reverse('modelmany_list'),
            json.dumps({'char_indexed': 'value'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            'char_indexed': 'value',
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/modelmany/1/',
        }

        instance_many = ModelMany.objects.get(id=1)
        assert instance_many.id == 1
        assert instance_many.char_indexed == 'value'

        response = self.client.post(
            self.api.reverse('modelforeign_list'),
            json.dumps({'char_indexed': 'value'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            'char_indexed': 'value',
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/modelforeign/1/',
        }

        instance_foreign = ModelForeign.objects.get(id=1)
        assert instance_foreign.id == 1
        assert instance_foreign.char_indexed == 'value'

        response = self.client.post(
            self.api.reverse('model_list'),
            json.dumps({
                'char_indexed': 'value',
                'foreign': self.api.reverse('modelforeign_single', args=(1,)),
                'manytomany': [
                    self.api.reverse('modelmany_single', args=(1,)),
                ]
            }),
            content_type='application/json'
        )
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            'char_indexed': 'value',
            'foreign': '/api/v1/modelforeign/1/',
            'foreign_id': 1,
            'manytomany': [
                '/api/v1/modelmany/1/',
            ],
            'manytomany_id': [1],
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/model/1/',
        }

    def test_resource_deserialize_invalid_uri(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        Model.objects.create(id=1, char_indexed='value', foreign_id=1)
        response = self.client.put(
            self.api.reverse('model_single', args=(1,)),
            json.dumps({
                'foreign': '/api/v1/model/1/',
            }),
            content_type='application/json'
        )

        assert response.status_code == 422
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'error': 'Supplied data was invalid',
            'invalid': {
                'foreign': ["Unable to resolve related: [u'1'], Unexpected resource found: model (expected modelforeign)"]
            }
        }

    def test_resource_resolve(self):
        resource, ids = self.api.resolve([
            self.api.reverse('modelother_single', args=(1,)),
        ])
        self.assertRaises(
            ModelOther.DoesNotExist,
            resource.fetch,
            *ids
        )

    def test_resource_serialize(self):
        instance_foreign = ModelForeign.objects.create(id=1, char_indexed='value')
        instance = Model.objects.create(id=1, char_indexed='value', foreign=instance_foreign)
        instance.manytomany.add(*[
            ModelMany.objects.create(id=1, char_indexed='value'),
            ModelMany.objects.create(id=2, char_indexed='value2'),
            ModelMany.objects.create(id=3, char_indexed='value3'),
        ])

        response = self.client.get(self.api.reverse('model_single', args=(1,)))
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'id': 1,
            'char_indexed': 'value',
            'foreign': '/api/v1/modelforeign/1/',
            'foreign_id': 1,
            'manytomany': [
                '/api/v1/modelmany/1/',
                '/api/v1/modelmany/2/',
                '/api/v1/modelmany/3/',
            ],
            'manytomany_id': [1,2,3],
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/model/1/',
        }

    def test_serialize_foreign3(self):
        ModelForeign3.objects.create(id=1, char_indexed='value')
        ModelHasForeign3.objects.create(id=1, foreign_id=1)

        response = self.client.get(
            self.api.reverse('modelhasforeign3_single', args=(1,))
        )
        assert json.loads(response.content) == {
            'id': 1,
            'foreign': {
                'id': 1,
                'char_indexed': 'value',
                '_id': 1,
                '_pk': 'id',
                '_uri': '/api/v1/modelforeign3/1/',
            },
            '_id': 1,
            '_pk': 'id',
            '_uri': '/api/v1/modelhasforeign3/1/',
        }

    def test_version_field(self):
        ModelVersioned.objects.create(id=1, name='initial')

        _uri = self.api.reverse('modelversioned_single', args=(1,))
        response = self.client.put(
            _uri,
            json.dumps({
                'name': 'first',
                'version': 1,
            }),
            content_type='application/json'
        )
        assert response.status_code == 200
        assert json.loads(response.content) == {
            'id': 1,
            'name': 'first',
            'version': 2,
            '_id': 1,
            '_pk': 'id',
            '_uri': _uri,
        }

        response = self.client.put(
            _uri,
            json.dumps({
                'name': 'invalid',
                'version': 1,
            }),
            content_type='application/json'
        )
        assert response.status_code == 409
        assert response.content == ''

        response = self.client.put(
            _uri,
            json.dumps({
                'name': 'second',
                'version': 2,
            }),
            content_type='application/json'
        )
        assert response.status_code == 200
        assert json.loads(response.content) == {
            'id': 1,
            'name': 'second',
            'version': 3,
            '_id': 1,
            '_pk': 'id',
            '_uri': _uri,
        }

    def test_version_field_missing_version_field(self):
        ModelVersioned.objects.create(id=1, name='initial')

        _uri = self.api.reverse('modelversioned_single', args=(1,))
        response = self.client.put(
            _uri,
            json.dumps({
                'name': 'first',
            }),
            content_type='application/json'
        )
        assert response.status_code == 400
        assert json.loads(response.content) == {
            'error': 'The "version" field must be specified',
        }

    def test_version_field_put_set(self):
        ModelVersioned.objects.create(id=1, name='initial')
        ModelVersioned.objects.create(id=2, name='initial')

        response = self.client.put(
            self.api.reverse('modelversioned_set', args=('1;2',)),
            json.dumps([
                {
                    'id': 1,
                    'name': 'invalid',
                },
                {
                    'id': 2,
                    'name': 'invalid',
                },
            ]),
            content_type='application/json'
        )
        assert response.status_code == 400
        assert json.loads(response.content) == {
            'invalid': {
                '1': {'error': 'The "version" field must be specified'},
                '2': {'error': 'The "version" field must be specified'},
            }
        }

        response = self.client.put(
            self.api.reverse('modelversioned_set', args=('1;2',)),
            json.dumps([
                {
                    'id': 1,
                    'name': 'invalid',
                    'version': 2,
                },
                {
                    'id': 2,
                    'name': 'invalid',
                    'version': 2,
                },
            ]),
            content_type='application/json'
        )
        assert response.status_code == 409
        assert response.content == ''

        response = self.client.put(
            self.api.reverse('modelversioned_set', args=('1;2',)),
            json.dumps([
                {
                    'id': 1,
                    'name': 'invalid',
                },
                {
                    'id': 2,
                    'name': 'invalid',
                    'version': 2,
                },
            ]),
            content_type='application/json'
        )
        assert response.status_code == 400
        assert json.loads(response.content) == {
            'error': 'Mixed error codes',
            'invalid': {
                '1': {
                    'code': 400,
                    'error': 'The "version" field must be specified'
                },
                '2': {'code': 409},
            }
        }

    @property
    def urls(self):
        from django.conf.urls import include, url

        return self.make_urlconf(
            url('^api/', include(self.api.urls)),
            url('^api/', include(self.api2.urls)),
        )
