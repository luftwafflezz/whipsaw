# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
# test-case-name: whipsaw.test.test_common_providers_art

import requests

from whipsaw.common import http
from whipsaw.common.providers.base import ProviderTransientError
from whipsaw.common.providers.art.base import ArtProvider, ArtResult

import logging
logger = logging.getLogger(__name__)

API_URL = 'https://ws.audioscrobbler.com/2.0/'

_RATE_LIMITER = http.RateLimiter(1.0)

# Last.fm's own size ordering, smallest to largest.
_SIZE_ORDER = ['small', 'medium', 'large', 'extralarge', 'mega']


class LastFmArtProvider(ArtProvider):
    """
    Last.fm's album.getInfo image field. Weakest signal of any provider
    here -- user-uploaded, frequently blank or a placeholder for anything
    less than very popular. Off by default even with an api_key
    configured; requires an explicit `enabled = true` too, so a user
    doesn't get surprised by low-quality art just from adding a key.
    """

    name = 'lastfm'

    @property
    def enabled(self):
        if self.config.getboolean('art:lastfm', 'enabled') is not True:
            return False
        return bool(self.config.get_provider_credential(
            'art:lastfm', 'api_key'))

    def fetch(self, metadata):
        artist = getattr(metadata, 'artist', None)
        title = getattr(metadata, 'releaseTitle', None) or \
            getattr(metadata, 'title', None)
        if not artist or not title:
            return None

        api_key = self.config.get_provider_credential(
            'art:lastfm', 'api_key')

        session = http.get_session()
        _RATE_LIMITER.wait()
        try:
            resp = session.get(API_URL, params={
                'method': 'album.getinfo',
                'artist': artist,
                'album': title,
                'api_key': api_key,
                'format': 'json',
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
            data = resp.json()
        except ValueError:
            return None

        images = data.get('album', {}).get('image', [])
        image_url = self._best_image_url(images)
        if not image_url:
            return None

        try:
            img_resp = session.get(image_url, timeout=http.DEFAULT_TIMEOUT)
        except requests.RequestException as e:
            raise ProviderTransientError(str(e))
        if img_resp.status_code >= 500:
            raise ProviderTransientError('HTTP %d' % img_resp.status_code)
        if img_resp.status_code != 200 or not img_resp.content:
            return None

        mime_type = img_resp.headers.get('Content-Type', 'image/jpeg')
        return ArtResult(img_resp.content, mime_type, self.name)

    @staticmethod
    def _best_image_url(images):
        by_size = {img.get('size'): img.get('#text')
                   for img in images if img.get('#text')}
        for size in reversed(_SIZE_ORDER):
            if by_size.get(size):
                return by_size[size]
        return None
