krankshaft
==========

A Web API Framework.

Currently only supports Django, but designed to work for
other frameworks with some modification.  At some point, other framework support
will be built in directly.

krankshaft was designed to make the frustrating and unnecessarily complicated
parts of Web APIs simple and beautiful by default.  It's built in layers that
allow the programmer to easily opt-in/out of.  From "Expose this model via
a web api and handle all the details" to "hands off my API, I'll opt-into the
basics as I need them".

krankshaft is meant to be a framework to build Web APIs and grow with your
application.

.. note::

   These docs are still very young and need a lot of work.  I'll be giving it
   some much needed attention in the future.

Guide
-----

.. toctree::
   :maxdepth: 2

   quickstart/index

API
---

.. toctree::
   :maxdepth: 2

   api/api
   api/auth
   api/authn
   api/authz
   api/models
   api/query
   api/resource
   api/serializer
   api/throttle
   api/util
   api/valid

Resources
---------

- `Code <https://github.com/dlamotte/krankshaft>`_
- `Docs <http://krankshaft.readthedocs.org/en/latest/>`_
- `Issues <https://github.com/dlamotte/krankshaft/issues>`_
