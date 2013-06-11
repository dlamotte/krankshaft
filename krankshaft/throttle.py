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

    The main goal of this implementation is to throttle requests in a constant
    time lookup so that the maximum number of requests doesnt define how long
    it takes to calculate if a request is allowed (which would be O(n)).  In
    this model, the lookup is constant time (which would be O(1)) based on the
    number of buckets (not the input number of requests).  This is required for
    a high preformance throttle.  The larger the bucket in comparison to the
    window, the fewer cache requests (the faster the lookup), but the longer it
    takes for a client over its quota to be able to make another request.
    '''
    bucket_ratio = 0.1
    format = 'throttle_%(id)s'
    rate = None
    timer = time.time

    def __init__(self, bucket=None, cache=None, rate=None):
        self.cache = cache or self.default_cache
        self.rate = rate or self.rate

        self.bucket = bucket
        if self.bucket and hasattr(self.bucket, 'total_seconds'):
            self.bucket = self.bucket.total_seconds()

        if self.rate:
            window = self.rate[1]
            if hasattr(window, 'total_seconds'):
                window = window.total_seconds()
            self.rate = (self.rate[0], int(window))

            if not self.bucket:
                self.bucket = int(self.rate[1] * self.bucket_ratio)
            self.nbuckets = int(self.rate[1] / self.bucket)

    def allow(self, auth, suffix=None):
        '''allow(auth) -> (bool, headers)

        Test if a request from a authenticated client is throttled.

        The headers returned should be added to the response when the request
        is not allowed.
        '''
        if not self.rate:
            return True

        key = self.key(auth, suffix)
        bsize = self.bucket
        nreq, nsec = self.rate
        now = int(self.timer())

        current = now - (now % bsize)
        buckets = [current]
        first = now - (now % nsec)
        for i in range(self.nbuckets):
            current -= bsize
            if current < first:
                break
            buckets.append(current)

        buckets = [
            (bucket, key + '_b' + str(bucket))
            for bucket in buckets
        ]

        cached = self.cache.get_many([bkey for bucket, bkey in buckets])
        buckets = [
            (bucket, bkey, cached[bkey])
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
                # ie: nsec = 10, bsize = 2, nreq = 1, now = 51
                # buckets = (
                #   (42, None), # outside window in 1 second
                #   (44, 1),    # outside window in 3 seconds
                #   (46, None),
                #   (48, None),
                #   (50, None)
                # )
                # needs to wait 3 seconds to fall off end
                # wait (3) = now (51) - bucket (44) + 2 * bsize (2)
                wait = now - bucket + (2 * bsize)
                break

            return (False, {
                'X-Throttled-For': wait
            })

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

    def key(self, auth, suffix=None):
        '''key(auth) -> key

        Construct a key for the authenticated client.
        '''
        return (self.format % auth.id) + (suffix or '')

    @property
    def timeout(self):
        # extra bucket of time accounts for lag/latency/skew in time
        #
        # 3, 2 second buckets for a total 6 second window
        #   | | | |  bucket markers
        #    ^     ^ first caret is beginning of window, second caret is now
        return self.rate[1] + self.bucket
