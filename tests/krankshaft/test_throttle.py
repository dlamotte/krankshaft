from __future__ import absolute_import

from datetime import timedelta
from krankshaft.auth import Auth
from krankshaft.throttle import Throttle
from tests.base import TestCaseNoDB

class ThrottleBaseTest(TestCaseNoDB):
    def setUp(self):
        self.auth = Auth(self.make_request())
        self.throttle = Throttle()

    def test_allow(self):
        self.assertEquals(self.throttle.allow(self.auth), (True, {}))

    def test_allow_suffix(self):
        self.assertEquals(self.throttle.allow(self.auth, 'suffix'), (True, {}))

class ThrottleRateTest(TestCaseNoDB):
    def setUp(self):
        from django.core.cache import cache
        self.auth = Auth(self.make_request())
        self.cache = cache
        self.throttle = Throttle(
            bucket=timedelta(seconds=2),
            cache=self.cache,
            rate=(1, timedelta(seconds=10)),
        )

        # make sure cache is clear
        self.cache.clear()

    def test_allow(self):
        self.assertEquals(self.throttle.allow(self.auth), (True, {}))

        allowed, headers = self.throttle.allow(self.auth)
        self.assertEquals(allowed, False)

        nreq, nsec = self.throttle.rate
        print headers
        self.assertTrue(headers['X-Throttled-For'] < nsec)

    def test_allow_default(self):
        self.throttle = Throttle(
            cache=self.cache,
            rate=(1, timedelta(seconds=60)),
        )
        self.test_allow()
