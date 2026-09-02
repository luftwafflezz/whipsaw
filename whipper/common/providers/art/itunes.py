# -*- Mode: Python; test-case-name: whipper.test.test_common_providers_art -*-
# vi:si:et:sw=4:sts=4:ts=4

import requests

from whipper.common import http
from whipper.common.providers.base import ProviderTransientError
from whipper.common.providers.art.base import ArtProvider, ArtResult

import logging
logger = logging.getLogger(__name__)

SEARCH_URL = 'https://itunes.apple.com/search'

# iTunes publishes no rate limit; this is a conservative, defensive default.
_RATE_LIMITER = http.RateLimiter(3.0)


class ITunesArtProvider(ArtProvider):
    """
    iTunes Search API. Free, unauthenticated. Serves a 100x100 thumbnail
    by default; the artwork URL accepts a resolution substitution for a
    much larger image.
    """

    name = 'itunes'

    def fetch(self, metadata):
        artist = getattr(metadata, 'artist', None)
        title = getattr(metadata, 'releaseTitle', None) or \
            getattr(metadata, 'title', None)
        if not artist or not title:
            return None

        session = http.get_session()
        _RATE_LIMITER.wait()
        try:
            resp = session.get(SEARCH_URL, params={
                'term': '%s %s' % (artist, title),
                'entity': 'album',
                'limit': 5,
            }, timeout=http.DEFAULT_TIMEOUT)
        except requests.RequestException as e:
            raise ProviderTransientError(str(e))

        if resp.status_code >= 500:
            raise ProviderTransientError('HTTP %d' % resp.status_code)
        if resp.status_code != 200:
            logger.debug('%s: HTTP %d, no result', self.name,
                         resp.status_code)
            return None

        try:
            results = resp.json().get('results', [])
        except ValueError:
            return None
        if not results:
            return None

        artwork_url = results[0].get('artworkUrl100')
        if not artwork_url:
            return None
        large_url = artwork_url.replace('100x100bb', '1200x1200bb')

        try:
            img_resp = session.get(large_url, timeout=http.DEFAULT_TIMEOUT)
        except requests.RequestException as e:
            raise ProviderTransientError(str(e))
        if img_resp.status_code >= 500:
            raise ProviderTransientError('HTTP %d' % img_resp.status_code)
        if img_resp.status_code != 200:
            return None

        mime_type = img_resp.headers.get('Content-Type', 'image/jpeg')
        return ArtResult(img_resp.content, mime_type, self.name)
