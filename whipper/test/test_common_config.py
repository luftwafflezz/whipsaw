# -*- Mode: Python; test-case-name: whipper.test.test_common_config -*-
# vi:si:et:sw=4:sts=4:ts=4

import os
import tempfile

from whipper.common import config

from whipper.test import common as tcommon


class ConfigTestCase(tcommon.TestCase):

    def setUp(self):
        fd, self._path = tempfile.mkstemp(suffix='.whipper.test.config')
        os.close(fd)
        self._config = config.Config(self._path)

    def tearDown(self):
        os.unlink(self._path)

    def testAddReadOffset(self):
        self.assertRaises(KeyError, self._config.getReadOffset,
                          'PLEXTOR ', 'DVDR   PX-L890SA', '1.05')
        self._config.setReadOffset('PLEXTOR ', 'DVDR   PX-L890SA', '1.05', 6)

        # getting it from memory should work
        offset = self._config.getReadOffset(
            'PLEXTOR ', 'DVDR   PX-L890SA', '1.05')
        self.assertEqual(offset, 6)

        # and so should getting it after reading it again
        self._config.open()
        offset = self._config.getReadOffset(
            'PLEXTOR ', 'DVDR   PX-L890SA', '1.05')
        self.assertEqual(offset, 6)

    def testAddReadOffsetSpaced(self):
        self.assertRaises(KeyError, self._config.getReadOffset,
                          'Slimtype', 'eSAU208   2     ', 'ML03')
        self._config.setReadOffset('Slimtype', 'eSAU208   2     ', 'ML03', 6)

        # getting it from memory should work
        offset = self._config.getReadOffset(
            'Slimtype', 'eSAU208   2     ', 'ML03')
        self.assertEqual(offset, 6)

        # and so should getting it after reading it again
        self._config.open()
        offset = self._config.getReadOffset(
            'Slimtype', 'eSAU208   2     ', 'ML03')
        self.assertEqual(offset, 6)

    def testDefeatsCache(self):
        self.assertRaises(KeyError, self._config.getDefeatsCache,
                          'PLEXTOR ', 'DVDR   PX-L890SA', '1.05')

        self._config.setDefeatsCache(
            'PLEXTOR ', 'DVDR   PX-L890SA', '1.05', False)
        defeats = self._config.getDefeatsCache(
            'PLEXTOR ', 'DVDR   PX-L890SA', '1.05')
        self.assertEqual(defeats, False)

        self._config.setDefeatsCache(
            'PLEXTOR ', 'DVDR   PX-L890SA', '1.05', True)
        defeats = self._config.getDefeatsCache(
            'PLEXTOR ', 'DVDR   PX-L890SA', '1.05')
        self.assertEqual(defeats, True)

    def test_get_musicbrainz_server(self):
        self.assertEqual(self._config.get_musicbrainz_server(),
                         {'scheme': 'https', 'netloc': 'musicbrainz.org'},
                         msg='Default value is correct')

        self._config._parser.add_section('musicbrainz')

        self._config._parser.set('musicbrainz', 'server',
                                 'http://192.168.2.141:5000')
        self._config.write()
        self.assertEqual(self._config.get_musicbrainz_server(),
                         {'scheme': 'http', 'netloc': '192.168.2.141:5000'},
                         msg='Correctly returns user-set value')

        # Test for unsupported scheme
        self._config._parser.set('musicbrainz', 'server', 'ftp://example.com')
        self._config.write()
        self.assertRaises(KeyError, self._config.get_musicbrainz_server)

        # Test for absent scheme
        self._config._parser.set('musicbrainz', 'server', 'example.com')
        self._config.write()
        self.assertRaises(KeyError, self._config.get_musicbrainz_server)

        self._config._parser.remove_section('musicbrainz')

    def test_get_art_provider_chain_default(self):
        # an old whipper.conf with none of the new sections should still
        # get the default provider chain, no migration needed
        self.assertEqual(
            self._config.get_art_provider_chain(),
            ['caa_release', 'caa_release_group', 'itunes'])

    def test_get_art_provider_chain_custom_order(self):
        self._config._parser.add_section('cover_art')
        self._config._parser.set('cover_art', 'chain', 'itunes, caa_release')
        self._config.write()

        self.assertEqual(self._config.get_art_provider_chain(),
                         ['itunes', 'caa_release'])

    def test_get_art_provider_chain_respects_disabled(self):
        self._config._parser.add_section('art:itunes')
        self._config._parser.set('art:itunes', 'enabled', 'false')
        self._config.write()

        chain = self._config.get_art_provider_chain()
        self.assertNotIn('itunes', chain)
        self.assertIn('caa_release', chain)

    def test_get_cover_art_max_dimension_default(self):
        self.assertEqual(self._config.get_cover_art_max_dimension(), 1200)

    def test_get_cover_art_max_dimension_custom(self):
        self._config._parser.add_section('cover_art')
        self._config._parser.set('cover_art', 'max_dimension', '500')
        self._config.write()

        self.assertEqual(self._config.get_cover_art_max_dimension(), 500)

    def test_get_provider_credential_absent(self):
        self.assertIsNone(
            self._config.get_provider_credential('art:fanarttv', 'api_key'))

    def test_get_provider_credential_present(self):
        self._config._parser.add_section('art:fanarttv')
        self._config._parser.set('art:fanarttv', 'api_key', 'deadbeef')
        self._config.write()

        self.assertEqual(
            self._config.get_provider_credential('art:fanarttv', 'api_key'),
            'deadbeef')
