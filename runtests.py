#!/usr/bin/env python

import pytest
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

def runtests(args=None):
    if not args:
        args = ['--cov=krankshaft', '--tb=line', 'tests']
    sys.exit(pytest.main(args=args))

if __name__ == '__main__':
    runtests(sys.argv[1:])
