#!/usr/bin/env python
# Copyright (c) 2009 David Cramer and individual contributors.
# All rights reserved.

# modified from https://github.com/getsentry/sentry runtests.py

import os
import sys
from os import path
from optparse import OptionParser

sys.path.insert(0, path.dirname(path.abspath(__file__)))

os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.settings'
from django.conf import settings

settings.INSTALLED_APPS = tuple(settings.INSTALLED_APPS) + (
    'tests',
)

from django_nose import NoseTestSuiteRunner

def runtests(*test_args, **kwargs):
    if 'south' in settings.INSTALLED_APPS:
        from south.management.commands import patch_for_test_db_setup
        patch_for_test_db_setup()

    if not test_args:
        test_args = ['--with-cov', '--cov=krankshaft', 'tests']

    kwargs.setdefault('interactive', False)

    test_runner = NoseTestSuiteRunner(**kwargs)

    failures = test_runner.run_tests(test_args)
    sys.exit(failures)

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('--verbosity', dest='verbosity', action='store', default=1, type=int)
    parser.add_options(NoseTestSuiteRunner.options)
    (options, args) = parser.parse_args()

    runtests(*args, **options.__dict__)
