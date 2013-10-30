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
      secret: '',
      username: ''
    },
    authn_header: 'Authorization',
    authn_method: 'APIToken',
    authn_method_value: function(method, username, secret) {
      return method + ' ' + username + ':' + secret;
    },
    authn_update: function(opts) {
      var authn = _.defaults({}, bb.ks.authn, opts.authn);

      if (authn.username && authn.secret) {
        var headers = {};
        headers[bb.ks.authn_header] = bb.ks.authn_method_value(
          bb.ks.authn_method,
          authn.username,
          authn.secret
        );

        opts.headers = _.extend(headers, opts.headers);
      }

      return opts;
    }
  };

  bb.ks_old_sync = bb.sync;
  bb.sync = function(method, model, opts) {
    opts = bb.ks.authn_update(opts);

    return bb.ks_old_sync(method, model, opts);
  };
}(jQuery, Backbone, _));
