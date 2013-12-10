/*
 * krankshaft.js 0.1
 *
 * Copyright 2013 Dan LaMotte <lamotte85@gmail.com>
 *
 * This software may be used and distributed according to the terms of the
 * MIT License.
 *
 * Depends on: q.js (https://github.com/kriskowal/q)
 */
(function($, window, undefined) {
  'use strict';

  var ks = window.ks = {};

  ks.API = function(schema, auth) {
    this.auth = auth;
    this.schema = schema;
  };
  $.extend(ks.API.prototype, {
    clean: function(resource, data) {
      // TODO
      // clean data based on schema fields for resource
    },

    clean_field: function(resource, name, value) {
      // TODO
    },

    reverse: function(name) {
      var parts = name.split(':');
      var name = parts[0];
      var endpoint = parts[1];

      if (! name) {
        throw new Error('You must specify a resource name');
      }

      var resource = this.schema.resources[name];
      if (! resource) {
        throw new Error('Unable to find resource: ' + name);
      }

      var url;
      var meta;
      if (endpoint) {
        if (! resource.endpoint[endpoint]) {
          throw new Error(
            'Endpoint '
            + endpoint
            + ' for resource '
            + name
            + ' does not exist'
          );
        }

        meta = resource.endpoint[endpoint];
        url = resource.endpoint[endpoint].url;
      }
      else {
        meta = resource;
        url = resource.url;
      }

      if (! url) {
        throw new Error(
          (endpoint ? ('Endpoint ' + endpoint) : 'Resource ')
          + ' has no url associated with it'
        );
      }

      var kws = typeof arguments[1] === 'object' ? arguments[1] : undefined;
      var args = kws === undefined ? Array.prototype.slice.call(arguments, 1) : undefined;

      var needed = meta.params;
      if (! needed) {
        // discover params
        var m;
        var re = /:([a-zA-Z0-9_-]+)/g;
        needed = [];
        while (m = re.exec(url)) {
          needed.push(m[1]);
        }
      }

      if (kws === undefined) {
        if (args.length !== needed.length) {
          throw new Error(
            'No reverse for "' + name + '" with args "' + args.join(', ') +
            '", need args: ' + needed.join(', ')
          );
        }

        for (var i = 0; i < args.length; i += 1) {
          url = url.replace(new RegExp(':' + needed[i]), args[i]);
        }
      }
      else {
        var set = {};

        for (var i = 0; i < needed.length; i += 1) {
          set[needed[i]] = 1;
        }

        for (var key in kws) {
          if (! kws.hasOwnProperty(key)) {
            continue;
          }

          if (! set.hasOwnProperty(key)) {
            set[key] = 0;
          }

          set[key] += 2;
        }

        var unmatched = false;
        for (var key in set) {
          if (! set.hasOwnProperty(key)) {
            continue;
          }

          if (set[key] != 3) {
            unmatched = true;
            break;
          }
        }

        if (unmatched) {
          throw new Error(
            'No reverse for "' + name + '" with ' + JSON.stringify(kws) +
            ', need keys: ' + needed.join(', ')
          );
        }

        for (var key in kws) {
          if (! kws.hasOwnProperty(key)) {
            continue;
          }

          url = url.replace(new RegExp(':' + key), kws[key]);
        }
      }

      if (! url) {
        throw new Error('Issue during reverse of "' + name + '"');
      }

      return url;
    }
  });

  // TODO client-side valid library?

  // TODO test update method
  ks.Auth = function(authn, authz) {
    this.authn = authn;
    this.authz = authz;
  };
  $.extend(ks.Auth.prototype, {
    update: function() {
      return this.authn.update.apply(this.authn, arguments);
    }
  });

  ks.Authn = function(username, secret, opts) {
    opts = opts || {};
    this.header = opts.header || 'Authorization';
    this.method = opts.method || 'APIToken';
    this.secret = secret;
    this.username = username;
  };
  $.extend(ks.Authn.prototype, {
    make_method_value: function(method, username, secret) {
      return method + ' ' + username + ':' + secret;
    },

    update: function(opts) {
      var authn = $.extend({
        header: this.header,
        method: this.method,
        secret: this.secret,
        username: this.username
      }, opts.authn);

      if (authn.username && authn.secret) {
        var headers = {};
        headers[authn.header] = this.make_method_value(
          authn.method,
          authn.username,
          authn.secret
        );

        opts.headers = $.extend(headers, opts.headers);
      }

      return opts;
    }
  });

  ks.deferred_to_promise = function(dfd) {
    var promise = Q.promise(function(resolve, reject) {
      dfd.then(
        function(data, textStatus, jqXHR) {
          var oldthen = jqXHR.then;
          delete jqXHR.then; // treat xhr as a non-promise
          jqXHR.data = data;
          resolve(jqXHR);
          jqXHR.then = oldthen;
        },
        function(jqXHR, textStatus, errorThrown) {
          var oldthen = jqXHR.then;
          delete jqXHR.then; // treat xhr as a non-promise
          reject(jqXHR);
          jqXHR.then = oldthen;
        }
      );
    });

    return promise;
  };

  ks.make_api = function(schema, username, secret) {
    var authn = new ks.Authn(username, secret);
    var auth = new ks.Auth(authn, null);
    var api = new ks.API(schema, auth);
    return api;
  };
}(jQuery, this));
