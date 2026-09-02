# -*- Mode: Python; test-case-name: whipper.test.test_common_providers_art -*-
# vi:si:et:sw=4:sts=4:ts=4

from whipper.common.providers.base import ProviderChain
from whipper.common.providers.art.caa import (
    CAAReleaseProvider, CAAReleaseGroupProvider,
)
from whipper.common.providers.art.itunes import ITunesArtProvider

import logging
logger = logging.getLogger(__name__)

# fanart.tv, Discogs and Last.fm join this registry once their provider
# modules land (they need API keys/tokens, so are off by default anyway).
PROVIDER_CLASSES = {
    'caa_release': CAAReleaseProvider,
    'caa_release_group': CAAReleaseGroupProvider,
    'itunes': ITunesArtProvider,
}


def build_chain(config):
    """
    Build the configured cover-art provider chain.

    Unknown provider names in the configured chain are skipped with a
    warning rather than failing the whole rip.
    """
    names = config.get_art_provider_chain()
    providers = []
    for name in names:
        cls = PROVIDER_CLASSES.get(name)
        if cls is None:
            logger.warning('unknown cover art provider %r in config, '
                           'skipping', name)
            continue
        providers.append(cls(config))
    return ProviderChain(providers)
