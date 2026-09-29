# -*- Mode: Python; test-case-name: whipsaw.test.test_common_http -*-
# vi:si:et:sw=4:sts=4:ts=4

"""Shared HTTP client plumbing for whipsaw's optional external providers."""

import threading
import time

import requests

import whipsaw

DEFAULT_TIMEOUT = 10  # seconds

USER_AGENT = "whipsaw/%s ( https://github.com/luftwafflezz/whipsaw )" % \
    whipsaw.__version__


def get_session():
    """Return a requests.Session configured with whipsaw's User-Agent."""
    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT
    return session


class RateLimiter:
    """
    Enforce a minimum interval between successive calls, thread-safe.

    A single rip only makes one request per enabled provider per disc, so
    this mostly matters for bulk/scripted re-tagging runs rather than
    normal single-disc ripping -- but it's cheap insurance either way
    against hammering a free, unauthenticated, informally-rate-limited
    third-party service.
    """

    def __init__(self, min_interval_seconds):
        self._min_interval = min_interval_seconds
        self._lock = threading.Lock()
        self._last_call = None

    def wait(self):
        with self._lock:
            now = time.monotonic()
            if self._last_call is not None:
                elapsed = now - self._last_call
                if elapsed < self._min_interval:
                    time.sleep(self._min_interval - elapsed)
            self._last_call = time.monotonic()
