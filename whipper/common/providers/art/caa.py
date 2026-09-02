# -*- Mode: Python; test-case-name: whipper.test.test_common_providers_art -*-
# vi:si:et:sw=4:sts=4:ts=4

import musicbrainzngs

from whipper.common.providers.art.base import ArtProvider, ArtResult

import logging
logger = logging.getLogger(__name__)


class CAAReleaseProvider(ArtProvider):
    """Cover Art Archive, at the specific release level."""

    name = 'caa_release'

    def fetch(self, metadata):
        release_id = getattr(metadata, 'mbid', None)
        if not release_id:
            return None
        size = self.config.get_cover_art_max_dimension()
        try:
            data = musicbrainzngs.get_image_front(release_id, size)
        except musicbrainzngs.WebServiceError as e:
            # Covers both "no cover art for this release" (404) and
            # transient failures (network, 5xx, rate limit) -- the
            # musicbrainzngs API doesn't distinguish them by exception
            # type, so we treat all of it as "this provider has nothing,
            # try the next one" rather than aborting the whole chain.
            logger.debug('%s: no cover art for release %s (%s)',
                         self.name, release_id, e)
            return None
        if not data:
            return None
        return ArtResult(data, 'image/jpeg', self.name)


class CAAReleaseGroupProvider(ArtProvider):
    """Cover Art Archive, falling back to the release-group level."""

    name = 'caa_release_group'

    def fetch(self, metadata):
        release_group_id = getattr(metadata, 'mbidReleaseGroup', None)
        if not release_group_id:
            return None
        size = self.config.get_cover_art_max_dimension()
        try:
            data = musicbrainzngs.get_release_group_image_front(
                release_group_id, size)
        except musicbrainzngs.WebServiceError as e:
            logger.debug('%s: no cover art for release group %s (%s)',
                         self.name, release_group_id, e)
            return None
        if not data:
            return None
        return ArtResult(data, 'image/jpeg', self.name)
