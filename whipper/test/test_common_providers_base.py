# -*- Mode: Python; test-case-name: whipper.test.test_common_providers_base -*-
# vi:si:et:sw=4:sts=4:ts=4

import unittest

from whipper.common import config
from whipper.common.providers.base import (
    Provider, ProviderChain, ProviderConfigError, ProviderTransientError,
)


class _StubProvider(Provider):
    _section_prefix = 'stub'

    def __init__(self, config, name, result=None, raises=None):
        super().__init__(config)
        self.name = name
        self._result = result
        self._raises = raises
        self.calls = 0

    def fetch(self, *args, **kwargs):
        self.calls += 1
        if self._raises:
            raise self._raises
        return self._result


class ProviderEnabledTestCase(unittest.TestCase):

    def setUp(self):
        self.config = config.Config('/nonexistent/whipper-test.conf')

    def testEnabledByDefault(self):
        p = _StubProvider(self.config, 'foo')
        self.assertTrue(p.enabled)

    def testDisabledByExplicitConfig(self):
        self.config._parser.add_section('stub:foo')
        self.config._parser.set('stub:foo', 'enabled', 'false')
        p = _StubProvider(self.config, 'foo')
        self.assertFalse(p.enabled)


class ProviderChainTestCase(unittest.TestCase):

    def setUp(self):
        self.config = config.Config('/nonexistent/whipper-test.conf')

    def testFirstSuccessWins(self):
        first = _StubProvider(self.config, 'first', result='FIRST')
        second = _StubProvider(self.config, 'second', result='SECOND')
        chain = ProviderChain([first, second])

        name, result = chain.run('fetch')

        self.assertEqual(name, 'first')
        self.assertEqual(result, 'FIRST')
        self.assertEqual(second.calls, 0)

    def testFallsThroughOnEmptyResult(self):
        first = _StubProvider(self.config, 'first', result=None)
        second = _StubProvider(self.config, 'second', result='SECOND')
        chain = ProviderChain([first, second])

        name, result = chain.run('fetch')

        self.assertEqual(name, 'second')
        self.assertEqual(result, 'SECOND')

    def testFallsThroughOnTransientError(self):
        first = _StubProvider(self.config, 'first',
                              raises=ProviderTransientError('timed out'))
        second = _StubProvider(self.config, 'second', result='SECOND')
        chain = ProviderChain([first, second])

        name, result = chain.run('fetch')

        self.assertEqual(name, 'second')
        self.assertEqual(result, 'SECOND')

    def testFallsThroughOnConfigError(self):
        first = _StubProvider(self.config, 'first',
                              raises=ProviderConfigError('no api key'))
        second = _StubProvider(self.config, 'second', result='SECOND')
        chain = ProviderChain([first, second])

        name, result = chain.run('fetch')

        self.assertEqual(name, 'second')
        self.assertEqual(result, 'SECOND')

    def testSkipsDisabledProviders(self):
        self.config._parser.add_section('stub:first')
        self.config._parser.set('stub:first', 'enabled', 'false')
        first = _StubProvider(self.config, 'first', result='FIRST')
        second = _StubProvider(self.config, 'second', result='SECOND')
        chain = ProviderChain([first, second])

        name, result = chain.run('fetch')

        self.assertEqual(name, 'second')
        self.assertEqual(first.calls, 0)

    def testReturnsNoneWhenEveryProviderFails(self):
        first = _StubProvider(self.config, 'first', result=None)
        second = _StubProvider(self.config, 'second',
                               raises=ProviderTransientError('down'))
        chain = ProviderChain([first, second])

        name, result = chain.run('fetch')

        self.assertIsNone(name)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
