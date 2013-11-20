Quickstart
==========

krankshaft isn't limited to the given patterns, but it's helpful to see how it
was envisioned to be used so you can make some of your own.


Simple View
-----------

In ``app/api.py``::

    from django.conf import settings
    from krankshaft import API

    api = API('v1', debug=settings.DEBUG)

In ``app/views.py``::

    from app.api import api

    @api
    def view(request):
        return api.serialize(request, 200, {
            'key': 'value'
        })

In ``app/urls.py``::

    from django.conf.urls import patterns, include, url

    urlpatterns = patterns('app.views',
        url('^view/$', 'view'),
    )

Doesn't seem like we did a whole lot right?

Let's talk to this API::

    % curl http://localhost:8000/view/
    {"key": "value"}

How about protecting the API to only authenticated users?  Change
``app/api.py``::

    from django.conf import settings
    from krankshaft import API as APIBase, authn, authz
    from krankshaft.auth import Auth as AuthBase

    class Auth(AuthBase):
        authn = authn.AuthnDjango()
        authz = authz.AuthzDjango(require_authned=True)

    class API(APIBase):
        Auth = Auth

    api = API('v1', debug=settings.DEBUG)

So now we need to authenticate to our api::

    % curl -u user:password http://localhost:8000/view/
    {"key": "value"}


Resources
---------

Continuing from our above example, we can hook up a resource (which is simply
an class/object versus a simple function):

Append to ``app/api.py``::

    # optional arguments to pass when registering your endpoint
    @api(url='^model/(?P<id>\d+)/$')
    class ModelResource(object):
        def get(self, request, id):
            ...

        def put(self, request, id):
            ...

        def delete(self, request, id):
            ...

Append to ``app/urls.py`` (since we registered the endpoint using url, the api
takes care of pulling in all of those so we can register everything in one go)::

    urlpatterns += patterns('',
        url('^api/', include(api.urls)),
    )

This enables clients to make GET/PUT/DELETE requests to the endpoint::

    /api/v1/model/<id>/

If a ``POST`` is made, the client will receive a ``405`` response with the
``Allow`` header set to ``GET, PUT, DELETE``.

Model Resource
--------------

The model resource is simply a built in resource that has special handling for
Django models.  All that you need to do is subclass the resource, hook up the
model and register it:

Append to ``app/api.py``::

    from krankshaft.resource import DjangoModelResource
    from app.models import Model

    @api
    class ModelResource(DjangoModelResource):
        model = Model

Again, this is registered in ``app/urls.py`` automatically because this resource
defines a ``urls`` property (vs using the ``url=...`` option when decorating).

This resource implementation should be ideal for _most_ situations, but you're
free to reimplement parts or all of it.  It's meant only as a pattern you can
follow and is not required by the framework at all.
