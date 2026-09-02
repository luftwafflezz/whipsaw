# -*- Mode: Python; test-case-name: whipper.test.test_common_providers_art -*-
# vi:si:et:sw=4:sts=4:ts=4

from whipper.common.providers.base import Provider


class ArtResult:
    """The result of a successful cover-art fetch, before normalization."""

    def __init__(self, data, mime_type, source):
        self.data = data
        self.mime_type = mime_type
        self.source = source


class ArtProvider(Provider):
    """A single cover-art source. Subclasses implement fetch()."""

    _section_prefix = 'art'

    def fetch(self, metadata):
        """
        :param metadata: a whipper.common.mbngs.DiscMetadata
        :returns: an ArtResult, or a falsy value if this provider has no
                  art for this release.
        :raises whipper.common.providers.base.ProviderTransientError: on a
                recoverable failure (network, rate limit, 5xx) -- the chain
                will try the next provider.
        :raises whipper.common.providers.base.ProviderConfigError: if this
                provider isn't configured.
        """
        raise NotImplementedError
