from __future__ import absolute_import

from django.test import TestCase

class TestCaseNoDB(TestCase):
    def _pre_setup(self):
        self.client = self.client_class()
        self._urlconf_setup()

    def _post_teardown(self):
        self._urlconf_teardown()
