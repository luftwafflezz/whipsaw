# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
# test-case-name: whipper.test.test_common_providers_metadata

"""
Discogs as a metadata fallback source.

Unlike MusicBrainz, Discogs has no disc-ID/TOC-based lookup -- its API is
search/barcode/catalog#-based, not TOC-based. So this can't identify a
disc blind the way MusicBrainz can; it only ever activates with an
explicit search hint (whipper's --search flag), used only once MusicBrainz
and FreeDB have both already failed to find a match.
"""

import requests

from whipper.common import http, mbngs
from whipper.common.providers.base import ProviderTransientError

import logging
logger = logging.getLogger(__name__)

SEARCH_URL = 'https://api.discogs.com/database/search'

# Discogs: ~60 req/min authenticated; stay well under that.
_RATE_LIMITER = http.RateLimiter(1.0)


def search(config, query):
    """
    Search Discogs by free-text query for a best-guess release match.

    :param config: consulted for the 'metadata:discogs' token
    :type config: whipper.common.config.Config
    :param query: free-text search string (e.g. "artist - title"),
                  typically from whipper's --search flag
    :type query: str or None
    :returns: a whipper.common.mbngs.DiscMetadata, or None if there's no
              query, no token configured, or no match
    :raises whipper.common.providers.base.ProviderTransientError: on a
            recoverable failure (network, 5xx)
    """
    if not query:
        return None

    token = config.get_provider_credential('metadata:discogs', 'token')
    if not token:
        logger.debug('discogs: no token configured, skipping')
        return None

    session = http.get_session()
    _RATE_LIMITER.wait()
    try:
        resp = session.get(SEARCH_URL, params={
            'q': query, 'type': 'release', 'token': token,
        }, timeout=http.DEFAULT_TIMEOUT)
    except requests.RequestException as e:
        raise ProviderTransientError(str(e))

    if resp.status_code >= 500:
        raise ProviderTransientError('HTTP %d' % resp.status_code)
    if resp.status_code != 200:
        logger.debug('discogs: search HTTP %d, no result', resp.status_code)
        return None

    try:
        results = resp.json().get('results', [])
    except ValueError:
        return None
    if not results:
        return None

    release_url = results[0].get('resource_url')
    if not release_url:
        return None

    _RATE_LIMITER.wait()
    try:
        release_resp = session.get(release_url, params={'token': token},
                                   timeout=http.DEFAULT_TIMEOUT)
    except requests.RequestException as e:
        raise ProviderTransientError(str(e))
    if release_resp.status_code >= 500:
        raise ProviderTransientError('HTTP %d' % release_resp.status_code)
    if release_resp.status_code != 200:
        return None

    try:
        release = release_resp.json()
    except ValueError:
        return None

    return _to_disc_metadata(release)


def _to_disc_metadata(release):
    artists = release.get('artists') or []
    artist = ', '.join(a.get('name', '') for a in artists if a.get('name'))
    artist = artist or 'Unknown Artist'

    metadata = mbngs.DiscMetadata()
    metadata.artist = metadata.sortName = artist
    metadata.title = metadata.releaseTitle = (
        release.get('title') or 'Unknown Album')
    metadata.release = release.get('released') or None

    barcodes = [i.get('value') for i in release.get('identifiers', [])
                if i.get('type') == 'Barcode' and i.get('value')]
    if barcodes:
        metadata.barcode = barcodes[0]

    metadata.catalogNumbers = [
        label.get('catno') for label in release.get('labels', [])
        if label.get('catno')
    ]

    for entry in release.get('tracklist', []):
        # Discogs tracklists can include non-track entries (headings,
        # sub-tracks, indices) marked via 'type_'; only keep real tracks.
        if entry.get('type_') not in (None, 'track'):
            continue
        title = entry.get('title')
        if not title:
            continue
        track = mbngs.TrackMetadata()
        track.artist = track.sortName = artist
        track.title = title
        track.composers = []
        track.performers = []
        metadata.tracks.append(track)

    return metadata
