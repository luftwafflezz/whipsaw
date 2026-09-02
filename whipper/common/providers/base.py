# -*- Mode: Python; test-case-name: whipper.test.test_common_providers_base -*-
# vi:si:et:sw=4:sts=4:ts=4

"""
Shared machinery for whipper's provider-chain pattern.

Both the cover-art fallback chain (whipper.common.providers.art) and the
metadata fallback chain build on this: config-driven ordering, per-provider
enable/disable, and "one provider's failure doesn't abort the whole rip,
just try the next provider" as a structural property rather than a
hoped-for one.
"""

import logging
logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """Base class for provider-related errors."""


class ProviderTransientError(ProviderError):
    """
    A provider failed in a way that's worth trying the next provider for
    (a network timeout, a 5xx response, a rate limit) -- as opposed to "this
    provider is correctly configured and definitively has no answer," which
    a provider signals by simply returning a falsy result instead of
    raising.
    """


class ProviderConfigError(ProviderError):
    """A provider isn't usable because it isn't configured (e.g. no key)."""


class Provider:
    """
    Base class for a single named, independently enable/disable-able source
    in a provider chain.

    Subclasses set ``name`` and ``_section_prefix`` (e.g. name='fanarttv',
    _section_prefix='art' -> config section 'art:fanarttv'), and implement
    whatever fetch method the concrete chain (art, metadata, ...) calls.
    """

    name = None
    _section_prefix = None

    def __init__(self, config):
        self.config = config

    @property
    def enabled(self):
        """
        Whether this provider should be tried at all.

        Default: enabled, unless explicitly turned off via
        ``enabled = false`` in this provider's config section. Providers
        that require credentials should override this to also require
        those credentials be present.
        """
        section = '%s:%s' % (self._section_prefix, self.name)
        return self.config.getboolean(section, 'enabled') is not False


class ProviderChain:
    """
    Try a list of providers in order via a given method name, returning the
    first non-empty result.
    """

    def __init__(self, providers):
        self.providers = providers

    def run(self, method_name, *args, **kwargs):
        """
        :returns: (provider_name, result) for the first enabled provider
                  that returns a truthy result, or (None, None) if every
                  provider was disabled, unconfigured, errored, or came up
                  empty.
        """
        for provider in self.providers:
            if not provider.enabled:
                logger.debug('%s: disabled, skipping', provider.name)
                continue
            try:
                result = getattr(provider, method_name)(*args, **kwargs)
            except ProviderConfigError as e:
                logger.debug('%s: not configured (%s), skipping',
                             provider.name, e)
                continue
            except ProviderTransientError as e:
                logger.warning('%s: %s, trying next provider',
                               provider.name, e)
                continue
            if result:
                logger.info('resolved via %s', provider.name)
                return provider.name, result
        return None, None
