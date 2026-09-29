# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
# test-case-name: whipsaw.test.test_common_providers_metadata

import unittest
from unittest.mock import MagicMock, patch

from whipsaw.common import config
from whipsaw.common.providers.base import ProviderTransientError
from whipsaw.common.providers.metadata import cdtext, discogs
from whipsaw.image import table


DISCOGS_RELEASE = {
    'artists': [{'name': 'Test Artist'}],
    'title': 'Test Album',
    'released': '2001-02-03',
    'identifiers': [{'type': 'Barcode', 'value': '123456789012'}],
    'labels': [{'catno': 'CAT-001'}],
    'tracklist': [
        {'title': 'Track One'},
        {'title': 'Track Two'},
        {'type_': 'heading', 'title': 'Side B'},
    ],
}


class DiscogsSearchTestCase(unittest.TestCase):

    def setUp(self):
        self.config = config.Config('/nonexistent/whipsaw-test.conf')
        self.config._parser.add_section('metadata:discogs')
        self.config._parser.set('metadata:discogs', 'token', 'deadbeef')

    def testNoQueryReturnsNone(self):
        self.assertIsNone(discogs.search(self.config, None))
        self.assertIsNone(discogs.search(self.config, ''))

    def testNoTokenReturnsNone(self):
        cfg = config.Config('/nonexistent/whipsaw-test.conf')
        self.assertIsNone(discogs.search(cfg, 'artist - title'))

    @patch('whipsaw.common.http.get_session')
    def testSuccessfulSearchReturnsMetadata(self, mock_get_session):
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = {
            'results': [{'resource_url':
                        'https://api.discogs.com/releases/1'}]
        }
        release_resp = MagicMock(status_code=200)
        release_resp.json.return_value = DISCOGS_RELEASE

        session = MagicMock()
        session.get.side_effect = [search_resp, release_resp]
        mock_get_session.return_value = session

        with patch('whipsaw.common.providers.metadata.discogs.'
                   '_RATE_LIMITER.wait'):
            md = discogs.search(self.config, 'test artist - test album')

        self.assertEqual(md.artist, 'Test Artist')
        self.assertEqual(md.title, 'Test Album')
        self.assertEqual(md.barcode, '123456789012')
        self.assertEqual(md.catalogNumbers, ['CAT-001'])
        # the heading entry should be skipped, only 2 real tracks kept
        self.assertEqual(len(md.tracks), 2)
        self.assertEqual(md.tracks[0].title, 'Track One')
        self.assertEqual(md.tracks[0].composers, [])
        self.assertEqual(md.tracks[0].performers, [])

    @patch('whipsaw.common.http.get_session')
    def testNoSearchResultsReturnsNone(self, mock_get_session):
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = {'results': []}
        session = MagicMock()
        session.get.return_value = search_resp
        mock_get_session.return_value = session

        with patch('whipsaw.common.providers.metadata.discogs.'
                   '_RATE_LIMITER.wait'):
            self.assertIsNone(
                discogs.search(self.config, 'nothing matches this'))

    @patch('whipsaw.common.http.get_session')
    def testServerErrorRaisesTransientError(self, mock_get_session):
        search_resp = MagicMock(status_code=503)
        session = MagicMock()
        session.get.return_value = search_resp
        mock_get_session.return_value = session

        with patch('whipsaw.common.providers.metadata.discogs.'
                   '_RATE_LIMITER.wait'):
            self.assertRaises(ProviderTransientError, discogs.search,
                              self.config, 'query')


def _make_table_with_cdtext(disc_title=None, disc_performer=None,
                            track_titles=None):
    tbl = table.Table()
    tbl.cdtext = {}
    if disc_title:
        tbl.cdtext['TITLE'] = disc_title
    if disc_performer:
        tbl.cdtext['PERFORMER'] = disc_performer

    track_titles = track_titles or []
    for i, title in enumerate(track_titles):
        track = table.Track(i + 1, audio=True)
        track.cdtext = {'TITLE': title} if title else {}
        tbl.tracks.append(track)
    return tbl


class ApplyCdTextFallbackTestCase(unittest.TestCase):

    def testNoMetadataNoCdTextReturnsNone(self):
        tbl = _make_table_with_cdtext()
        self.assertIsNone(cdtext.apply_cdtext_fallback(None, tbl))

    def testNoMetadataWithCdTextSynthesizesDiscMetadata(self):
        tbl = _make_table_with_cdtext(
            disc_title='CD Title', disc_performer='CD Artist',
            track_titles=['Song One', 'Song Two'])

        md = cdtext.apply_cdtext_fallback(None, tbl)

        self.assertEqual(md.artist, 'CD Artist')
        self.assertEqual(md.title, 'CD Title')
        self.assertEqual(len(md.tracks), 2)
        self.assertEqual(md.tracks[0].title, 'Song One')
        self.assertEqual(md.tracks[1].title, 'Song Two')

    def testNoMetadataNoDiscTitleReturnsNone(self):
        # PERFORMER alone, no TITLE -- not enough to synthesize anything
        tbl = _make_table_with_cdtext(disc_performer='CD Artist')
        self.assertIsNone(cdtext.apply_cdtext_fallback(None, tbl))

    def testExistingMetadataWithTracksIsNotTouched(self):
        from whipsaw.common import mbngs
        md = mbngs.DiscMetadata()
        md.artist = md.sortName = 'Real Artist'
        md.title = md.releaseTitle = 'Real Album'
        existing_track = mbngs.TrackMetadata()
        existing_track.title = 'Real Track'
        md.tracks.append(existing_track)

        tbl = _make_table_with_cdtext(
            disc_title='CD Title', track_titles=['CD Track'])

        result = cdtext.apply_cdtext_fallback(md, tbl)

        self.assertIs(result, md)
        self.assertEqual(result.artist, 'Real Artist')
        self.assertEqual(len(result.tracks), 1)
        self.assertEqual(result.tracks[0].title, 'Real Track')

    def testExistingMetadataWithoutTracksGetsThemFilledIn(self):
        from whipsaw.common import mbngs
        md = mbngs.DiscMetadata()
        md.artist = md.sortName = 'Real Artist'
        md.title = md.releaseTitle = 'Real Album'
        # no tracks -- e.g. a sparse FreeDB match

        tbl = _make_table_with_cdtext(
            track_titles=['CD Track One', 'CD Track Two'])

        result = cdtext.apply_cdtext_fallback(md, tbl)

        self.assertEqual(result.artist, 'Real Artist')  # untouched
        self.assertEqual(len(result.tracks), 2)
        self.assertEqual(result.tracks[0].title, 'CD Track One')
        self.assertEqual(result.tracks[0].composers, [])


if __name__ == '__main__':
    unittest.main()
