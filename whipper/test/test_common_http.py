# -*- Mode: Python; test-case-name: whipper.test.test_common_http -*-
# vi:si:et:sw=4:sts=4:ts=4

import time
import unittest

from whipper.common import http


class GetSessionTestCase(unittest.TestCase):

    def testUserAgentIsSet(self):
        session = http.get_session()
        self.assertIn('whipper', session.headers['User-Agent'])


class RateLimiterTestCase(unittest.TestCase):

    def testFirstCallDoesNotWait(self):
        limiter = http.RateLimiter(1.0)
        start = time.monotonic()
        limiter.wait()
        self.assertLess(time.monotonic() - start, 0.1)

    def testSecondCallWaitsOutRemainingInterval(self):
        limiter = http.RateLimiter(0.2)
        limiter.wait()
        start = time.monotonic()
        limiter.wait()
        self.assertGreaterEqual(time.monotonic() - start, 0.15)


if __name__ == '__main__':
    unittest.main()
