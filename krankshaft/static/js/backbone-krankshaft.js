/*
 * backbone-krankshaft.js 0.1
 *
 * Copyright 2013 Dan LaMotte <lamotte85@gmail.com>
 *
 * This software may be used and distributed according to the terms of the
 * MIT License.
 */
(function($, bb, _, undefined) {
  'use strict';

  bb.ks = {
    authn: {
      header: 'Authorization',
      method: 'APIToken',
      method_value: function(method, username, secret) {
        return method + ' ' + username + ':' + secret;
      },
      secret: '',
      update: function(opts) {
        var authn = _.defaults({}, bb.ks.authn, opts.authn);

        if (authn.username && authn.secret) {
          var headers = {};
          headers[authn.header] = authn.method_value(
            authn.method,
            authn.username,
            authn.secret
          );

          opts.headers = _.extend(headers, opts.headers);
        }

        return opts;
      },
      username: ''
    },
    cache: {
      add: function(inst) {
        bb.ks.get_or_create_collection(inst.constructor)
              .set([inst], {remove: false});
      },
      cached: [],
      clear: function(model) {
        if (model) {
          bb.ks.cache.get_or_create_collection(model).reset();
        }
        else {
          bb.ks.cached = [];
        }
      },
      get: function(model, id) {
        return
          bb.ks.get_or_create_collection(model)
                .get(id);
      },
      get_or_create_collection: function(model) {
        var collection = _.find(bb.ks.cache.cached, function(collection) {
          return collection.model == model;
        });

        if (! collection) {
          collection = new bb.Collection();
          collection.model = model;
          bb.ks.cache.cached.push(collection);
        }

        return collection;
      }
    },
    no_conflict: function() {
      bb.sync = bb.sync_ks_old;
      bb.Model.prototype.fetch = bb.Model.prototype.fetch_ks_old;
      bb.Collection.prototype.fetch = bb.Collection.prototype.fetch_ks_old;
    }
  };

  bb.sync_ks_old = bb.sync;
  bb.sync_ks = bb.sync = function(method, model, opts) {
    var update = bb.ks.authn.update;

    if (opts.authn && opts.authn.update) {
      update = opts.authn.update;
    }

    return bb.ks_old_sync(method, model, update(opts));
  };

  bb.Model.prototype.fetch_ks_old = bb.Model.prototype.fetch;
  bb.Model.prototype.fetch_ks = bb.Model.prototype.fetch = function(opts) {
    var me = this;
    var request = bb.Model.prototype.fetch_ks_old.call(this, opts);

    if (this.constructor.cached === true) {
      request.done(function() {
        bb.ks.cache.add(me);
      });
    }

    return request;
  };

  bb.Collection.prototype.fetch_ks_old = bb.Collection.prototype.fetch;
  bb.Collection.prototype.fetch_ks = bb.Collection.prototype.fetch = function(opts) {
    var me = this;
    var request = bb.Collection.prototype.fetch_ks_old.call(this, opts);

    if (this.model.cached === true) {
      request.done(function() {
        bb.ks.cache.get_or_create_collection(me.model)
          .set(me.models, {remove: false});
      });
    }

    return request;
  };
}(jQuery, Backbone, _));
