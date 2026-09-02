# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
# test-case-name: whipper.test.test_common_providers_art

import requests

from whipper.common import http
from whipper.common.providers.base import ProviderTransientError
from whipper.common.providers.art.base import ArtProvider, ArtResult

import logging
logger = logging.getLogger(__name__)

SEARCH_URL = 'https://api.discogs.com/database/search'

# Discogs: ~60 req/min authenticated; stay well under that.
_RATE_LIMITER = http.RateLimiter(1.0)


class DiscogsArtProvider(ArtProvider):
    """
    Discogs, searched by barcode/catalog# rather than free text -- unlike
    a generic album-name search, this targets the *specific pressing* a
    disc's MusicBrainz metadata already identifies (DiscMetadata.barcode /
    .catalogNumbers), which is exactly what a CD ripper wants. Optional:
    off by default until a token is configured.
    """

    name = 'discogs'

    @property
    def enabled(self):
        if not super().enabled:
            return False
        return bool(self.config.get_provider_credential(
            'art:discogs', 'token'))

    def fetch(self, metadata):
        token = self.config.get_provider_credential('art:discogs', 'token')
        params = self._search_params(metadata)
        if not params:
            return None
        params['token'] = token

        session = http.get_session()
        _RATE_LIMITER.wait()
        try:
            resp = session.get(SEARCH_URL, params=params,
                               timeout=http.DEFAULT_TIMEOUT)
        except requests.RequestException as e:
            raise ProviderTransientError(str(e))

        if resp.status_code >= 500:
            raise ProviderTransientError('HTTP %d' % resp.status_code)
        if resp.status_code != 200:
            logger.debug('%s: search HTTP %d, no result', self.name,
                         resp.status_code)
            return None

        try:
            results = resp.json().get('results', [])
        except ValueError:
            return None
        if not results:
            return None

        image_url = results[0].get('cover_image') or results[0].get('thumb')
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

    @staticmethod
    def _search_params(metadata):
        barcode = getattr(metadata, 'barcode', None)
        if barcode:
            return {'barcode': barcode, 'type': 'release'}
        catalog_numbers = getattr(metadata, 'catalogNumbers', None)
        if catalog_numbers:
            return {'catno': catalog_numbers[0], 'type': 'release'}
        return None
