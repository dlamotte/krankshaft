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

    _.defaults(opts, {
      promise: true
    });

    if (model.api) {
      opts = model.api.auth.update(opts);
    }

    var xhr = bb.sync(method, model, opts);
    if (opts.promise) {
      return bb.ks.sync_xhr_to_promise(xhr);
    }
    else {
      return xhr;
    }
  };

  bb.ks.sync_xhr_to_promise = function(xhr) {
    return ks.deferred_to_promise(xhr)
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

    destroy: function(options) {
      if (this.size() === 0) {
        return false;
      }

      options = options ? _.clone(options) : {};
      var collection = this;
      var success = options.success;

      var destroy = function(model) {
        model.trigger('destroy', model, model.collection, options);
      };

      options.success = function(resp) {
        if (options.wait) {
          collection.each(destroy);
        }

        if (success) {
          success(collection, resp, options);
        }

        collection.each(function(model) {
          if (! model.isNew()) {
            model.trigger('sync', model, resp, options);
          }
        });
      };

      var error = options.error;
      options.error = function(resp) {
        if (error) {
          error(collection, resp, options);
        }
        collection.each(function(model) {
          model.trigger('error', model, resp, options);
        });
      };

      var xhr = this.sync('delete', this, options);
      if (! options.wait) {
        collection.each(destroy);
      }
      return xhr;
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

    save: function(key, val, options) {
      var attrs, method, xhr, tmpattributes;

      if (this.size() === 0) {
        return false;
      }

      tmpattributes = this.reduce(function(memo, model) {
        memo[model.id] = model.attributes;
        return memo;
      }, {});

      // Handle both `"key", value` and `{key: value}` -style arguments.
      if (key == null || typeof key === 'object') {
        attrs = key;
        options = val;
      } else {
        (attrs = {})[key] = val;
      }

      options = _.extend({validate: true}, options);

      var invalid = false;
      this.each(function(model) {
        if (! model._validate(attrs, options)) {
          invalid = true;
        }
      });

      if (invalid) {
        return false;
      }

      if (attrs) {
        if (options.wait) {
          // Set temporary attributes if `{wait: true}`.
          this.each(function(model) {
            model.attributes = _.extend({}, model.attributes, attrs);
          });
        }
        else {
          // If we're not waiting and attributes exist, save acts as
          // `set(attr).save(null, opts)` with validation. Otherwise, check if
          // the model will be valid when the attributes, if any, are set.
          this.each(function(model) {
            if (! model.set(attrs, options)) {
              throw new Error('Unhandled issue setting attrs');
            }
          });
        }
      }

      // After a successful server-side save, the client is (optionally)
      // updated with the server-side state.
      if (options.parse === void 0) options.parse = true;

      var collection = this;
      var success = options.success;
      options.success = function(resp) {
        var serverAttrsByID = _.reduce(
          collection.parse(resp, options),
          function(memo, attrs) {
            memo[attrs[collection.model.prototype.idAttribute]] = attrs;
            return memo;
          },
          {}
        );

        collection.each(function(model) {
          // Ensure attributes are restored during synchronous saves.
          model.attributes = tmpattributes[model.id];

          var serverAttrs = model.parse(serverAttrsByID[model.id], options);
          if (options.wait) {
            serverAttrs = _.extend({}, attrs, serverAttrs);
          }
          if (_.isObject(serverAttrs)) {
            model.set(serverAttrs, options);
          }
        });

        if (success) success(collection, resp, options);

        collection.each(function(model) {
          model.trigger('sync', model, resp, options);
        });
      };

      var error = options.error;
      options.error = function(resp) {
        if (error) {
          error(collection, resp, options);
        }
        collection.each(function(model) {
          model.trigger('error', model, resp, options);
        });
      };

      var isNew = this.at(0).isNew();
      var allSameNewness = this.every(function(model) {
        return model.isNew() === isNew;
      });

      if (! allSameNewness) {
        throw new Error('All models must have same isNew() state');
      }

      method = isNew ? 'create' : (options.patch ? 'patch' : 'update');
      if (method === 'patch') options.attrs = attrs;
      xhr = this.sync(method, this, options);

      // Restore attributes.
      if (attrs && options.wait) {
        this.each(function(model) {
          model.attributes = tmpattributes[model.id];
        });
      }

      return xhr;
    },

    url: function(models) {
      var uri = this.urlRoot;

      if (models === undefined) {
        models = this.models;
      }

      if (! models.length) {
        return uri;
      }

      uri = this.api.reverse(this.resource + ':set',
        _.map(models, function(model) { return model.get('_id'); }).join(';')
      );

      return uri;
    }
  });
}(jQuery, Backbone, _));
