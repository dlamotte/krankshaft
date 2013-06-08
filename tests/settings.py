from dj_database_url import config as config_url
from django.core.urlresolvers import reverse_lazy
from os import path

PROJECT_ROOT = path.dirname(path.abspath(__file__))

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

DATABASES = {
    'default': config_url(default='postgres://localhost/krankshaft'),
}
DATABASES['default'].update({
    'OPTIONS': {
        'autocommit': True,
    }
})

TEMPLATE_DEBUG = DEBUG = True

ADMINS = MANAGERS = ()
APPEND_SLASH = False
LANGUAGE_CODE = 'en-us'
MEDIA_ROOT = path.join(PROJECT_ROOT, 'media')
MEDIA_URL = '/media/'
ROOT_URLCONF = 'tests.urls'
SECRET_KEY = 'a'
SITE_ID = 1
STATIC_ROOT = path.join(PROJECT_ROOT, '_static')
STATIC_URL = '/static/'
TIME_ZONE = 'America/Chicago'
USE_I18N = False
USE_L10N = False
USE_TZ = True
WSGI_APPLICATION = 'tests.wsgi.application'

STATICFILES_DIRS = (
    path.join(PROJECT_ROOT, 'static'),
)
TEMPLATE_DIRS = (
    path.join(PROJECT_ROOT, 'templates'),
)

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',

    'krankshaft',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    #'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.static',
    'django.core.context_processors.tz',
    'django.core.context_processors.request',
    'django.contrib.messages.context_processors.messages',
)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}
