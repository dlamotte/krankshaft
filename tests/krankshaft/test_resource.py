from __future__ import absolute_import

from datetime import datetime
from django.db import models
from krankshaft.api import API as APIBase
from krankshaft.auth import Auth as AuthBase
from krankshaft.authn import Authn
from krankshaft.authz import Authz as AuthzBase
from krankshaft.resource import DjangoModelResource
from tests.base import TestCaseNoDB
import json
import pytest

class Authz(AuthzBase):
    def is_authorized_obj(self, request, authned, obj):
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

class ModelForeignNoResource(models.Model):
    name = models.CharField(max_length=20, db_index=True)

class ModelForeignNoResourceForeign(models.Model):
    foreign = models.ForeignKey(ModelForeignNoResource)

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
    foreign = models.ForeignKey(ModelForeign)
    manytomany = models.ManyToManyField(ModelMany)

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
        class ModelForeignNoResourceForeignResource(DjangoModelResource):
            model = ModelForeignNoResourceForeign
            name = 'modelforeignnoresourceforeign'

        @api
        class ModelManyResource(DjangoModelResource):
            model = ModelMany
            name = 'modelmany'

        @api
        class ModelOtherResource(DjangoModelResource):
            model = ModelOther
            name = 'modelother'

            def deserialize_seconds(self, instance, field, data):
                return data['seconds'] / 10

            def serialize_seconds(self, instance, field):
                return instance.seconds * 10

        @api
        class ModelUnauthorizedResource(DjangoModelResource):
            model = ModelUnauthorized
            name = 'modelunauthorized'

        @api
        class ModelResource(DjangoModelResource):
            model = Model
            name = 'model'

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

    def test_fetch_invalid_id(self):
        resource, ids = self.api.resolve([
            self.api.reverse('modelother_single', args=('invalid',)),
        ])
        self.assertRaises(
            self.api.ValueIssue,
            resource.fetch,
            *ids
        )

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
                    'resource_uri': '/api/v1/modelforeign/1/'
                },
                {
                    'id': 2,
                    'char_indexed': 'value2',
                    'resource_uri': '/api/v1/modelforeign/2/'
                },
                {
                    'id': 3,
                    'char_indexed': 'value3',
                    'resource_uri': '/api/v1/modelforeign/3/'
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
                    'resource_uri': '/api/v1/modelforeign/1/'
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
                    'resource_uri': '/api/v1/modelforeign/2/'
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
                    'resource_uri': '/api/v1/modelforeign/1/'
                },
                {
                    'id': 3,
                    'char_indexed': 'value3',
                    'resource_uri': '/api/v1/modelforeign/3/'
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
            'resource_uri': '/api/v1/modelforeign/1/'
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
            'resource_uri': '/api/v1/modelforeignnoresourceforeign/1/'
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
            'resource_uri': '/api/v1/modelforeign/1/'
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
            'resource_uri': '/api/v1/modelforeign/1/'
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
            'resource_uri': '/api/v1/modelother/1/'
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
            'resource_uri': '/api/v1/modelother/1/'
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
            'resource_uri': '/api/v1/model/1/'
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
            'resource_uri': '/api/v1/model/1/'
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
            'resource_uri': '/api/v1/modelforeign/1/'
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
            'resource_uri': '/api/v2/modelforeign2/1/'
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
                    'resource_uri': '/api/v1/modelforeign/1/'
                },
                {
                    'id': 2,
                    'char_indexed': 'massupdate',
                    'resource_uri': '/api/v1/modelforeign/2/'
                },
                {
                    'id': 3,
                    'char_indexed': 'massupdate',
                    'resource_uri': '/api/v1/modelforeign/3/'
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
                    'resource_uri': '/api/v2/modelforeign2/1/'
                },
                {
                    'id': 2,
                    'char_indexed': 'massupdate',
                    'resource_uri': '/api/v2/modelforeign2/2/'
                },
                {
                    'id': 3,
                    'char_indexed': 'massupdate',
                    'resource_uri': '/api/v2/modelforeign2/3/'
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
                    'resource_uri': '/api/v1/modelforeign/1/'
                },
                {
                    'id': 3,
                    'char_indexed': 'setupdate3',
                    'resource_uri': '/api/v1/modelforeign/3/'
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

        assert response.status_code == 415
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'error': 'Data format was invalid',
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
                    'resource_uri': '/api/v2/modelforeign2/1/'
                },
                {
                    'id': 3,
                    'char_indexed': 'setupdate3',
                    'resource_uri': '/api/v2/modelforeign2/3/'
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
            'resource_uri': '/api/v1/modelforeign/1/'
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
            'resource_uri': '/api/v2/modelforeign2/1/'
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
        assert response.status_code == 415
        assert response['Content-Type'] == 'application/json; charset=utf-8'
        assert json.loads(response.content) == {
            'error': 'Supplied data was invalid',
            'invalid': {
                'manytomany': ["Unable to resolve related: [u'invalid'], Unexpected resource found: modelforeign (expected modelmany)"]
            },
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
            'resource_uri': '/api/v1/modelmany/1/',
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
            'resource_uri': '/api/v1/modelforeign/1/',
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
            'resource_uri': '/api/v1/model/1/',
        }

    def test_resource_deserialize_invalid_resource_uri(self):
        ModelForeign.objects.create(id=1, char_indexed='value')
        Model.objects.create(id=1, char_indexed='value', foreign_id=1)
        response = self.client.put(
            self.api.reverse('model_single', args=(1,)),
            json.dumps({
                'foreign': '/api/v1/model/1/',
            }),
            content_type='application/json'
        )

        assert response.status_code == 415
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
            'resource_uri': '/api/v1/model/1/',
        }

    @property
    def urls(self):
        from django.conf.urls import include, url

        return self.make_urlconf(
            url('^api/', include(self.api.urls)),
            url('^api/', include(self.api2.urls)),
        )
