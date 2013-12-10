/*
 * backbone-krankshaft.js 0.1
 *
 * Copyright 2013 Dan LaMotte <lamotte85@gmail.com>
 *
 * This software may be used and distributed according to the terms of the
 * MIT License.
 *
 * Depends on: krankshaft.js
 */
(function($, bb, _, undefined) {
  'use strict';

  bb.ks = {};

  bb.ks.cache = {
    add: function(inst) {
      this.get_or_create_collection(inst.constructor)
            .set([inst], {remove: false});
    },
    cached: [],
    clear: function(model) {
      if (model) {
        this.get_or_create_collection(model).reset();
      }
      else {
        this.cached = [];
      }
    },
    get: function(model, id) {
      return this.get_or_create_collection(model).get(id);
    },
    get_or_create_collection: function(model) {
      var collection = _.find(this.cached, function(collection) {
        return collection.model == model;
      });

      if (! collection) {
        var Collection = bb.ks.Collection.extend({
          model: model
        });
        collection = new Collection();
        this.cached.push(collection);
      }

      return collection;
    }
  };

  bb.ks.sync = function(method, model, opts) {
    opts = opts || {};

    if (model.api) {
      opts = model.api.auth.update(opts);
    }

    return ks.deferred_to_promise(bb.sync(method, model, opts))
    .then(function(xhr) {
      var location = xhr.getResponseHeader('Location');
      if (! xhr.data
          && location
          && (
            xhr.status === 201
            || xhr.status === 202
            || xhr.status === 204
          )
      ) {
        return ks.deferred_to_promise(bb.sync('read', model, {
          url: location,
          headers: opts.headers
        }));
      }

      return xhr;
    });
  };

  /*
   * Ideally, once you have a krankshaft js API object, you attach it to a
   * Model like:
   *
   *  var MyModel = Backbone.ks.Model.extend({
   *   api: api,
   *   resource: 'mymodel'
   *  });
   *
   * This will automatically construct your `urlRoot` for the model as well
   * as its required for some methods overwritten in this module.
   */

  bb.ks.Model = bb.Model.extend({
    idAttribute: '_uri',
    sync: bb.ks.sync,

    constructor: function() {
      this.urlRoot = this.api.reverse(this.resource);

      bb.Model.apply(this, arguments);
    },

    fetch: function(opts) {
      var me = this;
      var request = bb.Model.prototype.fetch.call(this, opts);

      if (this.cached === true) {
        request.done(function() {
          bb.ks.cache.add(me);
        });
      }

      return request;
    },

    url: function() {
      return this.id || this.urlRoot || null;
    }
  }, {
    cached: function(uri, opts) {
      opts = opts || {};

      var cache = opts.ks_cache === undefined ? true : opts.ks_cache;

      if (this.prototype.cached === true && cache) {
        var instance = bb.ks.cache.get(this, uri);
        if (instance) {
          return instance;
        }
      }

      return null;
    },

    fetch: function(uri, opts) {
      opts = opts || {};

      var cached = this.cached(uri, opts);
      if (cached) {
        return Q.resolve(cached);
      }

      var ctor = this;
      return ks.deferred_to_promise($.ajax(_.extend({
        url: uri
      }, opts)))
      .then(function(xhr) {
        return new ctor(xhr.data);
      });
    }
  });

  bb.ks.Collection = bb.Collection.extend({
    sync: bb.ks.sync,

    constructor: function() {
      var model = this.model.prototype;

      if (! this.api) {
        this.api = model.api;
      }
      if (! this.resource) {
        this.resource = model.resource;
      }
      if (! this.urlRoot) {
        if (model.urlRoot) {
          this.urlRoot = model.urlRoot;
        }
        else if (this.api) {
          this.urlRoot = this.api.reverse(this.resource);
        }
      }

      bb.Collection.apply(this, arguments);
    },

    fetch: function(opts) {
      var me = this;
      var request = bb.Collection.prototype.fetch.call(this, opts);

      if (this.model.prototype.cached === true) {
        request.done(function() {
          bb.ks.cache.get_or_create_collection(me.model)
            .set(me.models, {remove: false});
        });
      }

      return request;
    },

    parse: function(data) {
      if (! data) {
        return;
      }

      if (data.meta) {
        this.meta = data.meta;
      }

      return data.objects;
    },

    url: function(models) {
      var uri = this.urlRoot;

      if (! models || ! models.length) {
        return uri;
      }

      uri = this.api.reverse(this.resource + ':set',
        _.map(models, function(model) { return model.get('id'); }).join(';')
      );

      return uri || null;
    }
  });
}(jQuery, Backbone, _));
