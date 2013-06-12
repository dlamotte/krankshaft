krankshaft
==========

A Web API Framework (with Django, ...).

[![Build Status](https://secure.travis-ci.org/dlamotte/krankshaft.png)](http://travis-ci.org/dlamotte/krankshaft)
[![pypi version](https://pypip.in/v/krankshaft/badge.png)](https://pypi.python.org/pypi/krankshaft)

purpose
=======

krankshaft was designed to make the frustrating and unnecessarily complicated
parts of Web APIs simple and beautiful by default.  It's built in layers that
allow the programmer to easily opt-in/out of.  From "Expose this model via
a web api and handle all the details" to "hands off my API, I'll opt-into the
basics as I need them".

krankshaft is meant to be a framework to build Web APIs and grow with your
application.

Goals:

* simple and concise
* keep the simple things simple
* enable complex APIs without getting in the way
* HTTP return codes are important, dont abstract them away
* fail early
* performance
* no global state
* easily extendable
* suggests a pattern, but doesnt restrict you to it

example
=======

This is just a suggested file structure, there is no limitation here.

In `app/apiv1.py`:

    from django.conf import settings
    from krankshaft import API

    apiv1 = API('v1', debug=settings.DEBUG)

In `app/views.py`:

    from app.apiv1 import apiv1 as api

    @api
    def view(request):
        return api.serialize(request, 200, {
            'key': 'value'
        })

At this point, you'll still need to wire up the common routing for your
framework.  In Django, it looks something like this:

In `app/urls.py`:

    from django.conf.urls import patterns, include, url

    urlpatterns += patterns('app.views',
        url('^view/$', 'view'),
    )

What more did you expect?

notes about sub-classing
========================
The main API class along with other classes reference the classes they use
internally, directly on the class definition.  So you can override part of
the API by simply sub-classing it and assigning a new class.

For example:

    class MyAPI(API):
        Serializer = MySerializer

In some cases, the initializer will take parameters to configure its behavior.
However, the API will initialize the class later (either in its initializer or
on demand).  So to pass options in the class definition, you'll need to use
a partial.

Example:

    from functools import partial

    class MyAPI(API):
        Serializer = partial(MySerializer, option='value')

Then the Serializer will later be passed the option when it's initialized.

what works
==========

* simple authentication/authorization schemes
* serialization of primitive types (complex types require sub-classing)
  respecting HTTP Accept Header
* abort (raise-like http response return)
* throttling

TODO
====

* auto-documenting based on doc strings (plus bootstrap interactive UI)
* caching
* class/resource-like routing (similar to Django Tastypie and Piston)
* easy-etag support
* flask support
* model serialization (but first, some helpers)
* pagination
