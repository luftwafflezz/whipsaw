# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
# test-case-name: whipper.test.test_common_providers_metadata

"""
CD-Text as a last-resort metadata fallback.

Unlike the other metadata sources, this isn't a "provider" tried as a
peer in a chain -- it's a patch applied once, after every other source
has had its chance, filling in only whatever's still missing. CD-Text is
already parsed by cdrdao's TOC read (Table.cdtext / Track.cdtext, plain
dicts keyed by field name, e.g. 'TITLE'/'PERFORMER') -- no new TOC
parsing needed here.
"""

from whipper.common import mbngs

import logging
logger = logging.getLogger(__name__)


def apply_cdtext_fallback(metadata, table):
    """
    :param metadata: a whipper.common.mbngs.DiscMetadata, or None if
                     nothing was found via any other source
    :param table: the disc's TOC (whipper.image.table.Table)
    :returns: metadata, patched in place; a freshly synthesized
              DiscMetadata if `metadata` was None and disc-level CD-Text
              is available; or None if there's nothing to work with
              either way
    """
    disc_cdtext = table.cdtext or {}

    if metadata is None:
        disc_title = disc_cdtext.get('TITLE')
        if not disc_title:
            return None
        metadata = mbngs.DiscMetadata()
        metadata.artist = metadata.sortName = (
            disc_cdtext.get('PERFORMER') or 'Unknown Artist')
        metadata.title = metadata.releaseTitle = disc_title
        logger.info('used CD-Text for disc-level metadata: %s - %s',
                    metadata.artist, metadata.title)

    if not metadata.tracks:
        for track in table.tracks:
            if not track.audio:
                continue
            track_cdtext = track.cdtext or {}
            title = track_cdtext.get('TITLE')
            if not title:
                continue
            tm = mbngs.TrackMetadata()
            tm.artist = tm.sortName = (
                track_cdtext.get('PERFORMER') or metadata.artist)
            tm.title = title
            tm.composers = []
            tm.performers = []
            metadata.tracks.append(tm)
        if metadata.tracks:
            logger.info('used CD-Text for %d track title(s)',
                        len(metadata.tracks))

    return metadata
