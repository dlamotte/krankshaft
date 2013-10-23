class Authz(object):
    '''
    Basic interface for any authorizor.  Always returns the request as
    authorized.

    Options:
        require_authned: require that clients are authenticated
    '''
    methods_create = ('post', )
    methods_read = (
        'get',
        'head',
        'options',
    )
    methods_update = ('put', )
    methods_delete = ('delete', )

    def __init__(self, require_authned=True):
        self.require_authned = require_authned

    def is_authorized_obj(self, request, authned, obj):
        return True

    def is_authorized_request(self, request, authned):
        if self.require_authned:
            return bool(authned)
        else:
            return True

    def limit(self, request, authned, query):
        return query

class AuthzDjango(Authz):
    '''
    Django specific authorization based on authenticated user permissions
    and if defined, passes authorization to model's is_authorized() method.
    This can be used to implement object-level authorization.

    Options:
        perms: enable model level permission checking (default: True)
    '''
    def __init__(self, default_if_no_method=False, perms=True, **kwargs):
        super(AuthzDjango, self).__init__(**kwargs)
        self.default_if_no_method = default_if_no_method
        self.perms = perms

    def is_authorized_obj(self, request, authned, obj):
        if self.perms:
            meta = obj._meta
            method = request.method.lower()
            perm = None
            if method in self.methods_read:
                pass

            elif method in self.methods_create:
                perm = '%s.%s' % (meta.app_label, meta.get_add_permission())

            elif method in self.methods_update:
                perm = '%s.%s' % (meta.app_label, meta.get_change_permission())

            elif method in self.methods_delete:
                perm = '%s.%s' % (meta.app_label, meta.get_delete_permission())

            else:
                # unhandled methods are not authorized
                return False

            # allow read methods through but verify authenticated has permission
            # to perform the given action on the object
            if perm and not authned.user.has_perm(perm):
                return False

        obj_authz = getattr(obj, 'is_authorized', None)
        if not obj_authz:
            return self.default_if_no_method

        return obj_authz(request, authned)

class AuthzDjangoAnonRead(AuthzDjango):
    '''
    Like AuthzDjango, but explicitly allows read requests through without
    authentication.
    '''
    def is_authorized_request(self, request, authned):
        if authned:
            return True

        else:
            return request.method.lower() in self.methods_read

class AuthzReadonly(Authz):
    '''
    Read only authorization.  Only HTTP methods considered to be read-only
    are authorized.
    '''
    def is_authorized_request(self, request, authned):
        return \
            super(AuthzReadonly, self).is_authorized_request(request, authned) \
            and request.method.lower() in self.methods_read

    def is_authorized_obj(self, request, authned, obj):
        return self.is_authorized_request(request, authned)
