krankshaft
==========

A Web API Framework.

Currently only supports Django, but designed to work for
other frameworks with some modification.  At some point, other framework support
will be built in directly.

.. image:: https://secure.travis-ci.org/dlamotte/krankshaft.png
   :target: http://travis-ci.org/dlamotte/krankshaft

.. image:: https://coveralls.io/repos/dlamotte/krankshaft/badge.png
   :target: https://coveralls.io/r/dlamotte/krankshaft

.. image:: https://pypip.in/v/krankshaft/badge.png
   :target: https://pypi.python.org/pypi/krankshaft

.. image:: https://d2weczhvl823v0.cloudfront.net/dlamotte/krankshaft/trend.png
   :alt: Bitdeli badge
   :target: https://bitdeli.com/free

Purpose
-------

krankshaft was designed to make the frustrating and unnecessarily complicated
parts of Web APIs simple and beautiful by default.  It's built in layers that
allow the programmer to easily opt-in/out of.  From "Expose this model via
a web api and handle all the details" to "hands off my API, I'll opt-into the
basics as I need them".

krankshaft is meant to be a framework to build Web APIs and grow with your
application.

Goals:

- simple and concise
- keep the simple things simple
- enable complex APIs without getting in the way
- HTTP return codes are important, dont abstract them away
- fail early
- performance
- no global state
- easily extendable
- suggests a pattern, but doesnt restrict you to it
- secure by default

Example
-------

This is just a suggested file structure, there is no limitation here.

In ``app/apiv1.py``::

    from django.conf import settings
    from krankshaft import API

    apiv1 = API('v1', debug=settings.DEBUG)

In ``app/views.py``::

    from app.apiv1 import apiv1 as api

    @api
    def view(request):
        return api.serialize(request, 200, {
            'key': 'value'
        })

At this point, you'll still need to wire up the common routing for your
framework.  In Django, it looks something like this:

In ``app/urls.py``::

    from django.conf.urls import patterns, include, url

    urlpatterns += patterns('app.views',
        url('^view/$', 'view'),
    )

Resource example
----------------

In ``app/api.py``::

    from django.conf import settings

    api = API('v1', debug=settings.DEBUG)

    @api(url='^model/(?P<id>\d+)/$')
    class ModelResource(object):
        def get(self, request, id):
            ...

        def put(self, request, id):
            ...

        def delete(self, request, id):
            ...

In ``app/urls.py``::

    from django.conf.urls import patterns, include, url
    from .api import api

    urlpatterns = patterns('',
        url('^api/', include(api.urls)),
    )

This enables clients to make GET/PUT/DELETE requests to the endpoint::

    /api/v1/model/<id>/

If a POST is made, the client will receive the proper 405 response with the
Allow header set to GET, PUT, DELETE.

You can customize resources even more.  You can define your own routing scheme::

    class ModelResource(object):
        ...
        def route(self, request, id):
            # this is approximately the default
            try:
                view = getattr(self, request.method.lower())

            except AttributeError:
                return api.response(request, 405)

            else:
                return view(request, id)

Or setup urls and multiple routes::

    class ModelResource(object):
        ...

        def get_list(self, request):
            ...

        def post_list(self, request):
            ...

        def put_list(self, request):
            ...

        def delete_list(self, request):
            ...

        def query(self, request):
            if request.method != 'POST':
                return api.response(request, 405, Allow='POST')
            ...

        def route(self, suffix, request, *args, **kwargs):
            # this is approximately the default
            try:
                view = getattr(self, request.method.lower() + suffix)

            except AttributeError:
                return api.response(request, 405)

            else:
                return view(request, *args, **kwargs)

        def route_list(self, request):
            return self.route('_list', request)

        def route_object(self, request, id):
            return self.route('', request, id)

        @property
        def urls(self):
            from django.conf.urls import patterns, url
            return patterns('', [
                url(r'^model/$', api.wrap(self.route_list)),
                url(r'^model/query/$', api.wrap(self.query)),
                url(r'^model/(?P<id>\d+)/$', api.wrap(self.route_object)),
            ])

Or (instead of building your own) use the one built in::

    from krankshaft.resource import DjangoModelResource
    from app.models import Model
    from app.api import api

    @api
    class ModelResource(DjangoModelResource):
        model = Model

This resource implementation should be ideal for _most_ situations, but you're
free to reimplement parts or all of it.  It's meant only as a pattern you can
follow and is not required by the framework at all.

What works
----------

- simple authentication/authorization schemes (not OAuth at the moment)
- serialization of primitive types respecting HTTP Accept Header
- abort (raise-like http response return)
- throttling
- resource routing
- query application (ie: ``?field__startswith=something&order_by=field``)
  with pagination support
- deep data validation
- Django ORM based Model Resource (with model serialization/deserialization)
    - Optimistic Concurrency Control option (``version_field``)

Installation
------------

Add ``krankshaft`` to ``INSTALLED_APPS``::

    INSTALLED_APPS = (
        ...
        'krankshaft',
    )

Todo
----

- auto-documenting based on doc strings (plus bootstrap interactive UI)
- caching
- easy-etag support
- flask support
- OAuth (1 and 2)

Resources
---------

- `Code <https://github.com/dlamotte/krankshaft>`_
- `Docs <http://krankshaft.readthedocs.org/en/latest/>`_
- `Issues <https://github.com/dlamotte/krankshaft/issues>`_
