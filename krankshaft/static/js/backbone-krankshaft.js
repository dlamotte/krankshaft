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
}(jQuery, Backbone, _));
