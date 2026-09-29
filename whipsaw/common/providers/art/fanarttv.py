# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
# test-case-name: whipsaw.test.test_common_providers_art

import requests

from whipsaw.common import http
from whipsaw.common.providers.base import ProviderTransientError
from whipsaw.common.providers.art.base import ArtProvider, ArtResult

import logging
logger = logging.getLogger(__name__)

ALBUMS_URL = 'https://webservice.fanart.tv/v3/music/albums/%s'

_RATE_LIMITER = http.RateLimiter(1.0)


class FanartTvProvider(ArtProvider):
    """
    fanart.tv, keyed by MusicBrainz release-group MBID. Community-
    uploaded; strong for popular releases, weak long-tail coverage.
    Optional: off by default until an api_key is configured.
    """

    name = 'fanarttv'

    @property
    def enabled(self):
        if not super().enabled:
            return False
        return bool(self.config.get_provider_credential(
            'art:fanarttv', 'api_key'))

    def fetch(self, metadata):
        release_group_id = getattr(metadata, 'mbidReleaseGroup', None)
        if not release_group_id:
            return None

        api_key = self.config.get_provider_credential(
            'art:fanarttv', 'api_key')

        session = http.get_session()
        _RATE_LIMITER.wait()
        try:
            resp = session.get(ALBUMS_URL % release_group_id,
                               params={'api_key': api_key},
                               timeout=http.DEFAULT_TIMEOUT)
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

        albums = data.get('albums', {})
        album = albums.get(release_group_id, {})
        covers = album.get('albumcover', [])
        if not covers:
            return None

        image_url = covers[0].get('url')
        if not image_url:
            return None

        try:
            img_resp = session.get(image_url, timeout=http.DEFAULT_TIMEOUT)
        except requests.RequestException as e:
            raise ProviderTransientError(str(e))
        if img_resp.status_code >= 500:
            raise ProviderTransientError('HTTP %d' % img_resp.status_code)
        if img_resp.status_code != 200:
            return None

        mime_type = img_resp.headers.get('Content-Type', 'image/jpeg')
        return ArtResult(img_resp.content, mime_type, self.name)
