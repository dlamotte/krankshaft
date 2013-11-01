import time

class Throttle(object):
    '''
    Throttle requests based on authenticated client and a specified rate.

    The rate consists of the number of requests for a specific time period.

        rate = (number requests, time window/timedelta/seconds)

        ie: rate = (1000, timedelta(minutes=60))
            or rate = (1000, 300)

    The bucket determines the size of each "bucket" in which a request gets
    counted.  Instead of counting each request specifically, requests are
    grouped into bucket sized intervals (this is the minimum precision of when
    a request happened).  Bucket can be given as a timedelta() or seconds.
    Otherwise the bucket will default to the bucket_ratio of the time period
    of the rate.

    A suffix can be passed into various methods as a way to implement multiple
    throttles for a single authenticated user or for a single throttle per
    endpoint.

    There are also anon_bucket and anon_rate which are used for clients that
    are not authenticated.  By default, if only a rate is specified, the
    anonymous rate and bucket sizes are considerably smaller.  The reason being
    that by default, anonymous clients shouldn't have the same rate limits of
    an authenticated client or what would be the point of authenticating?

    The main goal of this implementation is to throttle requests in a constant
    time lookup so that the maximum number of requests doesnt define how long
    it takes to calculate if a request is allowed (which would be O(n)).  In
    this model, the lookup is constant time (which would be O(1)) based on the
    number of buckets (not the input number of requests).  This is required for
    a high preformance throttle.  The larger the bucket in comparison to the
    window, the fewer cache requests (the faster the lookup), but the longer it
    takes for a client over its quota to be able to make another request.
    '''
    anon_requests_ratio = 0.1
    anon_bucket_ratio = 0.1
    anon_rate = None
    bucket_ratio = 0.1
    format = 'throttle_%(id)s%(suffix)s'
    rate = None
    timer = time.time

    def __init__(self,
        request,
        auth,
        anon_bucket=None,
        anon_rate=None,
        bucket=None,
        cache=None,
        rate=None,
    ):
        self.auth = auth
        self.cache = cache or self.default_cache
        self.rate = rate or self.rate
        self.request = request

        self.bucket, self.rate = \
            self.make_bucket_rate(bucket, self.bucket_ratio, self.rate)

        anon_requests_ratio = self.anon_requests_ratio
        if anon_rate or self.anon_rate:
            anon_requests_ratio = 1
        self.anon_rate = anon_rate or self.anon_rate or self.rate
        self.anon_bucket, self.anon_rate = self.make_bucket_rate(
            anon_bucket,
            self.anon_bucket_ratio,
            self.anon_rate,
            anon_requests_ratio
        )

    def allow(self, suffix=None):
        '''allow() -> (bool, headers)

        Test if a request from a authenticated client is throttled.

        The headers returned should be added to the response when the request
        is not allowed.
        '''
        if self.auth.authned:
            bsize = self.bucket
            rate = self.rate
        else:
            bsize = self.anon_bucket
            rate = self.anon_rate

        if not rate:
            return (True, {})

        now = int(self.timer())
        key = self.key(suffix)
        nreq, nsec = rate

        current = now - (now % bsize)
        buckets = [current]
        first = now - nsec
        first = first - (first % bsize) # round down to previous bucket
        while current > first:
            current -= bsize
            buckets.append(current)

        buckets = [
            (bucket, key + '_b' + str(bucket))
            for bucket in buckets
        ]

        cached = self.cache.get_many([bkey for bucket, bkey in buckets])
        buckets = [
            (bucket, bkey, cached.get(bkey))
            for bucket, bkey in buckets
        ]

        requests_made = sum([
            bval
            for bucket, bkey, bval in buckets
            if bval
        ])
        bucket_current = buckets[0]

        if requests_made >= nreq:
            wait = None
            for bucket, bkey, bval in reversed(buckets):
                if not bval:
                    continue
                # ie: nsec = 10, bsize = 2, nreq = 1, now = 51, first = 42
                # buckets = (
                #   (40, None), # edge of window based on our bucket precision
                #   (42, None), # edge real window: 1 sec (42 - (now - nsec))
                #   (44, 1),    # edge real window: 3 sec (44 - (now - nsec))
                #   (46, None),
                #   (48, None),
                #   (50, None)
                # )
                # needs to wait 6 seconds to fall off end
                # wait(6) = bucket(44) - (now(51) - nsec(10)) + bsize(2) + 1
                #
                # need to wait the size of a single bucket on top of the
                # distance to the edge so that the bucket we're saying will
                # fall off actually falls off
                #
                # add one second to account for sub-second truncation,
                # otherwise, it's possible that a sub-second truncation error
                # will result in a client issuing a request after waiting for
                # the given seconds and being throttled
                #
                # however, to handle bucket's not being evenly disivible into
                # the nsec (rate time period) or that now minus nsec lands in
                # the middle of a bucket, we need to round down to the previous
                # bucket like:
                #
                # first = now - nsec               # edge of the real window
                # first = first - (first % bsize)  # round down to bucket
                #
                # so the formula becomes:
                # wait(7) = bucket(44) - first(40) + bsize(2) + 1
                # TODO this can be more accurate
                wait = bucket - first + bsize + 1
                break

            headers = {}
            if wait:
                headers['Retry-After'] = wait
            return (False, headers)

        else:
            try:
                self.cache.incr(bucket_current[1])
            except ValueError:
                # when incrementing a non-existant key on some cache backends
                self.cache.set(bucket_current[1], 1, self.timeout)
            return (True, {})

    @property
    def default_cache(self):
        from django.core.cache import cache
        return cache

    def make_bucket_rate(self, bucket, bucket_ratio, rate, requests_ratio=1):
        if bucket:
            if hasattr(bucket, 'total_seconds'):
                bucket = bucket.total_seconds()
            bucket = int(bucket)

        if rate:
            window = rate[1]
            if hasattr(window, 'total_seconds'):
                window = window.total_seconds()
            rate = (int(rate[0] * requests_ratio), int(window))

            if not bucket:
                bucket = int(rate[1] * bucket_ratio)

        return bucket, rate

    def key(self, suffix=None):
        '''key() -> key

        Construct a key for the authenticated client.
        '''
        return self.format % self.key_values(suffix)

    def key_values(self, suffix):
        return {
            'id': self.auth.id,
            'suffix': (suffix and ('_' + suffix) or ''),
        }

    @property
    def timeout(self):
        # its possible that if the current moment is exactly the same second
        # a bucket would be created, then the amount of buckets needed to
        # calculate is: (rate[1] / bucket) + 1
        #
        # extra bucket of time accounts for lag/latency/skew in time
        #
        # 3, 2 second buckets for a total 6 second window
        #   | | | | bucket markers
        #   ^     ^ first caret is beginning of window, second caret is now
        return self.rate[1] + (self.bucket * 2)
