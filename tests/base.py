from __future__ import absolute_import

from django.test import TestCase

class TestCaseBase(TestCase):
    def make_urlconf(self, *args, **kwargs):
        from django.conf.urls import patterns

        class Helper(object):
            pass

        module = Helper()
        module.urlpatterns = patterns('', *args, **kwargs)
        return module

class TestCaseNoDB(TestCaseBase):
    def _pre_setup(self):
        self.client = self.client_class()
        self._urlconf_setup()

    def _post_teardown(self):
        self._urlconf_teardown()
