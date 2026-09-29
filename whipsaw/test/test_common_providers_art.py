# -*- Mode: Python; test-case-name: whipsaw.test.test_common_providers_art -*-
# vi:si:et:sw=4:sts=4:ts=4

import io
import os
import unittest
from unittest.mock import MagicMock, patch

import musicbrainzngs
from PIL import Image

from whipsaw.common import config, mbngs
from whipsaw.common.providers.art import chain as art_chain
from whipsaw.common.providers.art.base import ArtResult
from whipsaw.common.providers.art.caa import (
    CAAReleaseGroupProvider, CAAReleaseProvider,
)
from whipsaw.common.providers.art.discogs import DiscogsArtProvider
from whipsaw.common.providers.art.fanarttv import FanartTvProvider
from whipsaw.common.providers.art.itunes import ITunesArtProvider
from whipsaw.common.providers.art.lastfm import LastFmArtProvider
from whipsaw.common.providers.art.normalize import normalize

FIXTURES_DIR = os.path.dirname(__file__)


def _metadata(mbid=None, mbid_release_group=None, artist=None, title=None,
              barcode=None, catalog_numbers=None):
    md = mbngs.DiscMetadata()
    md.mbid = mbid
    md.mbidReleaseGroup = mbid_release_group
    md.artist = artist
    md.releaseTitle = title
    md.barcode = barcode
    md.catalogNumbers = catalog_numbers or []
    return md


class CAAReleaseProviderTestCase(unittest.TestCase):

    def setUp(self):
        self.config = config.Config('/nonexistent/whipsaw-test.conf')
        self.provider = CAAReleaseProvider(self.config)

    def testNoMbidReturnsNone(self):
        self.assertIsNone(self.provider.fetch(_metadata()))

    @patch('musicbrainzngs.get_image_front')
    def testReturnsArtResultOnSuccess(self, mock_get):
        mock_get.return_value = b'fake-jpeg-bytes'
        result = self.provider.fetch(_metadata(mbid='abc-123'))

        self.assertIsInstance(result, ArtResult)
        self.assertEqual(result.data, b'fake-jpeg-bytes')
        self.assertEqual(result.source, 'caa_release')
        mock_get.assert_called_once_with('abc-123', 1200)

    @patch('musicbrainzngs.get_image_front')
    def testWebServiceErrorReturnsNone(self, mock_get):
        mock_get.side_effect = musicbrainzngs.ResponseError('404')
        self.assertIsNone(self.provider.fetch(_metadata(mbid='abc-123')))


class CAAReleaseGroupProviderTestCase(unittest.TestCase):

    def setUp(self):
        self.config = config.Config('/nonexistent/whipsaw-test.conf')
        self.provider = CAAReleaseGroupProvider(self.config)

    def testNoReleaseGroupIdReturnsNone(self):
        self.assertIsNone(self.provider.fetch(_metadata()))

    @patch('musicbrainzngs.get_release_group_image_front')
    def testReturnsArtResultOnSuccess(self, mock_get):
        mock_get.return_value = b'fake-jpeg-bytes'
        result = self.provider.fetch(_metadata(mbid_release_group='rg-1'))

        self.assertIsInstance(result, ArtResult)
        self.assertEqual(result.source, 'caa_release_group')
        mock_get.assert_called_once_with('rg-1', 1200)


class ITunesArtProviderTestCase(unittest.TestCase):

    def setUp(self):
        self.config = config.Config('/nonexistent/whipsaw-test.conf')
        self.provider = ITunesArtProvider(self.config)
        # tests shouldn't actually sleep on the module-level rate limiter
        self.provider_patcher = patch(
            'whipsaw.common.providers.art.itunes._RATE_LIMITER.wait')
        self.provider_patcher.start()
        self.addCleanup(self.provider_patcher.stop)

    def testNoArtistOrTitleReturnsNone(self):
        self.assertIsNone(self.provider.fetch(_metadata()))

    @patch('whipsaw.common.http.get_session')
    def testReturnsArtResultOnSuccess(self, mock_get_session):
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = {
            'results': [{'artworkUrl100':
                        'https://example/100x100bb.jpg'}]
        }
        img_resp = MagicMock(status_code=200, content=b'imgbytes')
        img_resp.headers = {'Content-Type': 'image/jpeg'}

        session = MagicMock()
        session.get.side_effect = [search_resp, img_resp]
        mock_get_session.return_value = session

        result = self.provider.fetch(_metadata(artist='A', title='T'))

        self.assertEqual(result.data, b'imgbytes')
        self.assertEqual(result.source, 'itunes')
        # the low-res thumbnail URL should have been upsized before fetch
        second_call_url = session.get.call_args_list[1].args[0]
        self.assertIn('1200x1200bb.jpg', second_call_url)

    @patch('whipsaw.common.http.get_session')
    def testNoResultsReturnsNone(self, mock_get_session):
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = {'results': []}
        session = MagicMock()
        session.get.return_value = search_resp
        mock_get_session.return_value = session

        self.assertIsNone(
            self.provider.fetch(_metadata(artist='A', title='T')))


class NormalizeTestCase(unittest.TestCase):

    def testDecodableJpegIsReencoded(self):
        cover_path = os.path.join(
            FIXTURES_DIR, '76df3287-6cda-33eb-8e9a-044b5e15ffdd.jpg')
        with open(cover_path, 'rb') as f:
            art = ArtResult(f.read(), 'image/jpeg', 'test')

        result = normalize(art, max_dimension=1200)

        self.assertIsNotNone(result)
        self.assertEqual(result.mime_type, 'image/jpeg')
        self.assertEqual(result.extension, 'jpg')
        im = Image.open(io.BytesIO(result.data))
        self.assertEqual(im.size, (494, 500))

    def testOversizedImageIsDownscaled(self):
        cover_path = os.path.join(
            FIXTURES_DIR, '76df3287-6cda-33eb-8e9a-044b5e15ffdd.jpg')
        with open(cover_path, 'rb') as f:
            art = ArtResult(f.read(), 'image/jpeg', 'test')

        result = normalize(art, max_dimension=100)

        im = Image.open(io.BytesIO(result.data))
        self.assertLessEqual(max(im.size), 100)

    def testTransparentPngIsKeptAsPng(self):
        buf = io.BytesIO()
        Image.new('RGBA', (10, 10), (255, 0, 0, 128)).save(buf, format='PNG')
        art = ArtResult(buf.getvalue(), 'image/png', 'test')

        result = normalize(art, max_dimension=1200, output_format='jpeg')

        self.assertEqual(result.mime_type, 'image/png')
        self.assertEqual(result.extension, 'png')

    def testUndecodableDataReturnsNone(self):
        art = ArtResult(b'not an image', 'image/jpeg', 'test')
        self.assertIsNone(normalize(art, max_dimension=1200))


class FanartTvProviderTestCase(unittest.TestCase):

    def setUp(self):
        self.config = config.Config('/nonexistent/whipsaw-test.conf')
        self.provider = FanartTvProvider(self.config)

    def testDisabledWithoutApiKey(self):
        self.assertFalse(self.provider.enabled)

    def testEnabledWithApiKey(self):
        self.config._parser.add_section('art:fanarttv')
        self.config._parser.set('art:fanarttv', 'api_key', 'deadbeef')
        self.assertTrue(self.provider.enabled)

    def testExplicitlyDisabledOverridesApiKeyPresence(self):
        self.config._parser.add_section('art:fanarttv')
        self.config._parser.set('art:fanarttv', 'api_key', 'deadbeef')
        self.config._parser.set('art:fanarttv', 'enabled', 'false')
        self.assertFalse(self.provider.enabled)

    def testNoReleaseGroupIdReturnsNone(self):
        self.assertIsNone(self.provider.fetch(_metadata()))

    @patch('whipsaw.common.http.get_session')
    def testReturnsArtResultOnSuccess(self, mock_get_session):
        api_resp = MagicMock(status_code=200)
        api_resp.json.return_value = {
            'albums': {'rg-1': {
                'albumcover': [{'url': 'https://x/cover.jpg'}]}}
        }
        img_resp = MagicMock(status_code=200, content=b'imgbytes')
        img_resp.headers = {'Content-Type': 'image/jpeg'}
        session = MagicMock()
        session.get.side_effect = [api_resp, img_resp]
        mock_get_session.return_value = session

        with patch('whipsaw.common.providers.art.fanarttv.'
                   '_RATE_LIMITER.wait'):
            result = self.provider.fetch(_metadata(mbid_release_group='rg-1'))

        self.assertEqual(result.data, b'imgbytes')
        self.assertEqual(result.source, 'fanarttv')


class DiscogsArtProviderTestCase(unittest.TestCase):

    def setUp(self):
        self.config = config.Config('/nonexistent/whipsaw-test.conf')
        self.provider = DiscogsArtProvider(self.config)

    def testDisabledWithoutToken(self):
        self.assertFalse(self.provider.enabled)

    def testEnabledWithToken(self):
        self.config._parser.add_section('art:discogs')
        self.config._parser.set('art:discogs', 'token', 'deadbeef')
        self.assertTrue(self.provider.enabled)

    def testNoBarcodeOrCatalogNumberReturnsNone(self):
        self.assertIsNone(self.provider.fetch(_metadata()))

    @patch('whipsaw.common.http.get_session')
    def testSearchesByBarcodeWhenAvailable(self, mock_get_session):
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = {
            'results': [{'cover_image': 'https://x/cover.jpg'}]
        }
        img_resp = MagicMock(status_code=200, content=b'imgbytes')
        img_resp.headers = {'Content-Type': 'image/jpeg'}
        session = MagicMock()
        session.get.side_effect = [search_resp, img_resp]
        mock_get_session.return_value = session

        with patch('whipsaw.common.providers.art.discogs.'
                   '_RATE_LIMITER.wait'):
            result = self.provider.fetch(_metadata(barcode='123456789012'))

        self.assertEqual(result.data, b'imgbytes')
        params = session.get.call_args_list[0].kwargs['params']
        self.assertEqual(params['barcode'], '123456789012')

    @patch('whipsaw.common.http.get_session')
    def testFallsBackToCatalogNumberWithoutBarcode(self, mock_get_session):
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = {'results': []}
        session = MagicMock()
        session.get.return_value = search_resp
        mock_get_session.return_value = session

        with patch('whipsaw.common.providers.art.discogs.'
                   '_RATE_LIMITER.wait'):
            self.provider.fetch(_metadata(catalog_numbers=['CAT-1']))

        params = session.get.call_args_list[0].kwargs['params']
        self.assertEqual(params['catno'], 'CAT-1')


class LastFmArtProviderTestCase(unittest.TestCase):

    def setUp(self):
        self.config = config.Config('/nonexistent/whipsaw-test.conf')
        self.provider = LastFmArtProvider(self.config)

    def testDisabledByDefaultEvenWithApiKey(self):
        # Last.fm needs an explicit `enabled = true`, not just a key --
        # it's the weakest-signal provider and shouldn't surprise anyone.
        self.config._parser.add_section('art:lastfm')
        self.config._parser.set('art:lastfm', 'api_key', 'deadbeef')
        self.assertFalse(self.provider.enabled)

    def testEnabledRequiresBothFlagAndKey(self):
        self.config._parser.add_section('art:lastfm')
        self.config._parser.set('art:lastfm', 'enabled', 'true')
        self.config._parser.set('art:lastfm', 'api_key', 'deadbeef')
        self.assertTrue(self.provider.enabled)

    def testEnabledFlagAloneWithoutKeyIsNotEnough(self):
        self.config._parser.add_section('art:lastfm')
        self.config._parser.set('art:lastfm', 'enabled', 'true')
        self.assertFalse(self.provider.enabled)

    def testNoArtistOrTitleReturnsNone(self):
        self.assertIsNone(self.provider.fetch(_metadata()))

    @patch('whipsaw.common.http.get_session')
    def testReturnsBestSizeImage(self, mock_get_session):
        api_resp = MagicMock(status_code=200)
        api_resp.json.return_value = {
            'album': {'image': [
                {'size': 'small', '#text': 'https://x/small.jpg'},
                {'size': 'mega', '#text': 'https://x/mega.jpg'},
                {'size': 'large', '#text': ''},
            ]}
        }
        img_resp = MagicMock(status_code=200, content=b'imgbytes')
        img_resp.headers = {'Content-Type': 'image/jpeg'}
        session = MagicMock()
        session.get.side_effect = [api_resp, img_resp]
        mock_get_session.return_value = session

        with patch('whipsaw.common.providers.art.lastfm.'
                   '_RATE_LIMITER.wait'):
            result = self.provider.fetch(_metadata(artist='A', title='T'))

        self.assertEqual(result.data, b'imgbytes')
        fetched_url = session.get.call_args_list[1].args[0]
        self.assertEqual(fetched_url, 'https://x/mega.jpg')


class BuildChainTestCase(unittest.TestCase):

    def testUnknownProviderNameIsSkippedNotFatal(self):
        cfg = config.Config('/nonexistent/whipsaw-test.conf')
        cfg._parser.add_section('cover_art')
        cfg._parser.set('cover_art', 'chain', 'caa_release, not_a_real_one')

        built = art_chain.build_chain(cfg)

        self.assertEqual([p.name for p in built.providers], ['caa_release'])


if __name__ == '__main__':
    unittest.main()
