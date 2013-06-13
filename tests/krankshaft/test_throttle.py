from __future__ import absolute_import

from datetime import timedelta
from django.core.cache import cache
from krankshaft.auth import Auth
from krankshaft.throttle import Throttle
from tests.base import TestCaseNoDB

class FakeUser(object):
    id = 1

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
        self.auth = Auth(self.make_request())
        self.auth.authned = FakeUser()

        self.cache = cache
        self.throttle = Throttle(
            bucket=timedelta(seconds=2),
            cache=self.cache,
            rate=(1, timedelta(seconds=10)),
        )
        self.now = self.throttle.timer()
        self.throttle.timer = lambda: self.now

        # make sure cache is clear
        self.cache.clear()

    def test_allow(self, wait=None):
        wait = wait or (13, )
        self.assertEquals(self.throttle.allow(self.auth), (True, {}))

        allowed, headers = self.throttle.allow(self.auth)
        self.assertEquals(allowed, False)

        nreq, nsec = self.throttle.rate
        self.assertTrue(headers['X-Throttled-For'] in wait)

        self.throttle.timer = lambda: self.now + headers['X-Throttled-For']
        allowed, headers = self.throttle.allow(self.auth)
        self.assertEquals(allowed, True)
        self.assertTrue(not headers)

    def test_allow_anon(self):
        auth = Auth(self.make_request())
        self.assertEquals(self.throttle.allow(auth), (False, {}))

    def test_allow_default(self):
        self.throttle = Throttle(
            cache=self.cache,
            rate=(1, timedelta(seconds=60)),
        )
        self.test_allow(wait=(67,))

    def test_allow_period_not_evenly_divisible(self):
        self.throttle = Throttle(
            bucket=timedelta(seconds=10),
            cache=self.cache,
            rate=(1, timedelta(seconds=61)),
        )
        self.test_allow(wait=(71, 81))

    def test_allow_suffix(self, wait=13):
        # no suffix
        self.assertEquals(self.throttle.allow(self.auth), (True, {}))

        allowed, headers = self.throttle.allow(self.auth)
        self.assertEquals(allowed, False)

        nreq, nsec = self.throttle.rate
        self.assertEquals(headers['X-Throttled-For'], wait)

        self.throttle.timer = lambda: self.now + wait
        allowed, headers = self.throttle.allow(self.auth)
        self.assertEquals(allowed, True)
        self.assertTrue(not headers)

        # suffix
        self.throttle.timer = lambda: self.now
        self.assertEquals(
            self.throttle.allow(self.auth, suffix='suffix'), (True, {})
        )

        allowed, headers = self.throttle.allow(self.auth, suffix='suffix')
        self.assertEquals(allowed, False)

        nreq, nsec = self.throttle.rate
        self.assertEquals(headers['X-Throttled-For'], wait)

        self.throttle.timer = lambda: self.now + wait
        allowed, headers = self.throttle.allow(self.auth, suffix='suffix')
        self.assertEquals(allowed, True)
        self.assertTrue(not headers)
