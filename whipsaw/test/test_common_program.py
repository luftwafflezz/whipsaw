# -*- Mode: Python; test-case-name: whipsaw.test.test_common_program -*-
# vi:si:et:sw=4:sts=4:ts=4


import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import musicbrainzngs

from whipsaw.common import program, mbngs, config
from whipsaw.command.cd import DEFAULT_DISC_TEMPLATE
from whipsaw.image import table
from whipsaw.result import result


class PathTestCase(unittest.TestCase):

    def testStandardTemplateEmpty(self):
        prog = program.Program(config.Config())

        path = prog.getPath('/tmp', DEFAULT_DISC_TEMPLATE,
                            'mbdiscid', None)
        self.assertEqual(path, ('/tmp/unknown/Unknown Artist - mbdiscid/'
                                'Unknown Artist - mbdiscid'))

    def testStandardTemplateFilled(self):
        prog = program.Program(config.Config())
        md = mbngs.DiscMetadata()
        md.artist = md.sortName = 'Jeff Buckley'
        md.releaseTitle = 'Grace'

        path = prog.getPath('/tmp', DEFAULT_DISC_TEMPLATE,
                            'mbdiscid', md, 0)
        self.assertEqual(path, ('/tmp/unknown/Jeff Buckley - Grace/'
                                'Jeff Buckley - Grace'))

    def testIssue66TemplateFilled(self):
        prog = program.Program(config.Config())
        md = mbngs.DiscMetadata()
        md.artist = md.sortName = 'Jeff Buckley'
        md.releaseTitle = 'Grace'

        path = prog.getPath('/tmp', '%A/%d', 'mbdiscid', md, 0)
        self.assertEqual(path,
                         '/tmp/Jeff Buckley/Grace')


class GetCoverArtTestCase(unittest.TestCase):
    """
    Exercises the real Program.getCoverArt() -> provider chain ->
    normalize -> write pipeline, rather than a hand-rolled reimplementation
    of it (which is what this file tested before -- it never actually
    called the method it claimed to cover).
    """

    def setUp(self):
        self.path = tempfile.mkdtemp(prefix='whipsaw.test.coverart.')
        self.addCleanup(shutil.rmtree, self.path, ignore_errors=True)
        self.prog = program.Program(
            config.Config('/nonexistent/whipsaw-test.conf'))

    @staticmethod
    def _fixture_bytes():
        # Using: Dummy by Portishead
        # https://musicbrainz.org/release/76df3287-6cda-33eb-8e9a-044b5e15ffdd
        fixture_path = os.path.join(
            os.path.dirname(__file__),
            '76df3287-6cda-33eb-8e9a-044b5e15ffdd.jpg')
        with open(fixture_path, 'rb') as f:
            return f.read()

    @patch('musicbrainzngs.get_image_front')
    def testFetchesAndSavesIntoDestinationDirectory(self, mock_get):
        mock_get.return_value = self._fixture_bytes()
        md = mbngs.DiscMetadata()
        md.mbid = '76df3287-6cda-33eb-8e9a-044b5e15ffdd'

        cover_art_path = self.prog.getCoverArt(self.path, md)

        self.assertIsNotNone(cover_art_path)
        # written into the destination directory itself, not the system
        # temp dir -- and no orphaned temp files left behind alongside it
        self.assertEqual(os.listdir(self.path),
                         [os.path.basename(cover_art_path)])
        self.assertTrue(os.path.isfile(cover_art_path))

    @patch('musicbrainzngs.get_release_group_image_front')
    @patch('musicbrainzngs.get_image_front')
    def testNoArtAvailableReturnsNoneWithoutCreatingAnything(
            self, mock_release, mock_release_group):
        mock_release.side_effect = musicbrainzngs.ResponseError('404')
        mock_release_group.side_effect = musicbrainzngs.ResponseError('404')
        md = mbngs.DiscMetadata()
        md.mbid = 'some-release-id'
        md.mbidReleaseGroup = 'some-release-group-id'
        # no artist/title set, so the iTunes provider also has nothing to
        # search with and won't make an HTTP request

        cover_art_path = self.prog.getCoverArt(self.path, md)

        self.assertIsNone(cover_art_path)
        self.assertEqual(os.listdir(self.path), [])


class RipTrackTestCase(unittest.TestCase):
    """
    Exercises the AccurateRip-checksum plumbing in Program.ripTrack() --
    computing arTrackNumber/arTotalTracks and copying t.arv1/t.arv2 onto
    trackResult -- by mocking cdparanoia.ReadVerifyTrackTask. The real
    task shells out to cd-paranoia against physical drive hardware and is
    out of reach for a unit test; this instead verifies the plumbing
    around it, which is what the AccurateRip format-decoupling fix
    actually depends on.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipsaw.test.riptrack.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

        self.prog = program.Program(
            config.Config('/nonexistent/whipsaw-test.conf'))
        self.prog.getRipResult()

        tbl = table.Table()
        tbl.tracks.append(table.Track(1, audio=True))
        tbl.tracks.append(table.Track(2, audio=True))
        tbl.tracks[0].index(1, absolute=0)
        tbl.tracks[1].index(1, absolute=1000)
        tbl.leadout = 2000
        self.prog.result.table = tbl

    @staticmethod
    def _mock_task(path, arv1='deadbeef', arv2='cafef00d'):
        t = MagicMock()
        t.testspeed = 1.0
        t.testduration = 1.0
        t.copyspeed = 1.0
        t.copyduration = 1.0
        t.testchecksum = 'aaaaaaaa'
        t.copychecksum = 'aaaaaaaa'
        t.peak = 0.5
        t.quality = 1.0
        t.arv1 = arv1
        t.arv2 = arv2
        t.path = path
        return t

    def _track_result(self, number, filename):
        trackResult = result.TrackResult()
        trackResult.number = number
        trackResult.filename = filename
        trackResult.testduration = 0.0
        trackResult.copyduration = 0.0
        return trackResult

    @patch('whipsaw.program.cdparanoia.ReadVerifyTrackTask')
    def testNormalTrackPassesItsOwnNumberAndDiscTotal(self, mock_cls):
        filename = os.path.join(self.tmpdir, 'track02.flac')
        trackResult = self._track_result(2, filename)
        mock_cls.return_value = self._mock_task(filename)

        self.prog.ripTrack(MagicMock(), trackResult, offset=0, device=None,
                           taglist={}, overread=False)

        _, kwargs = mock_cls.call_args
        self.assertEqual(kwargs['arTrackNumber'], 2)
        self.assertEqual(kwargs['arTotalTracks'], 2)
        self.assertEqual(kwargs['formatName'], 'flac')
        self.assertEqual(trackResult.arv1, 'deadbeef')
        self.assertEqual(trackResult.arv2, 'cafef00d')

    @patch('whipsaw.program.cdparanoia.ReadVerifyTrackTask')
    def testHtoaSkipsAccurateRip(self, mock_cls):
        # HTOA needs getHTOA() to succeed, which reads track 1's index 0
        # (the pregap) -- give it one.
        self.prog.result.table.tracks[0].index(0, absolute=0)

        filename = os.path.join(self.tmpdir, 'track00.flac')
        trackResult = self._track_result(0, filename)
        mock_cls.return_value = self._mock_task(filename, arv1=None,
                                                arv2=None)

        self.prog.ripTrack(MagicMock(), trackResult, offset=0, device=None,
                           taglist={}, overread=False)

        _, kwargs = mock_cls.call_args
        self.assertIsNone(kwargs['arTrackNumber'])
        self.assertEqual(kwargs['arTotalTracks'], 2)
        self.assertIsNone(trackResult.arv1)
        self.assertIsNone(trackResult.arv2)


class GetCDDBTestCase(unittest.TestCase):

    @patch('whipsaw.extern.freedb.perform_lookup')
    def testArtistSlashTitleIsParsed(self, mock_lookup):
        mock_lookup.return_value = [{'DTITLE': 'The Artist / The Album'}]

        md = program.Program.getCDDB(['id', 1, [0], 100])

        self.assertEqual(md.artist, 'The Artist')
        self.assertEqual(md.title, 'The Album')

    @patch('whipsaw.extern.freedb.perform_lookup')
    def testNoSeparatorFallsBackToWholeStringAsTitle(self, mock_lookup):
        mock_lookup.return_value = [{'DTITLE': 'JustATitleNoSeparator'}]

        md = program.Program.getCDDB(['id', 1, [0], 100])

        self.assertEqual(md.artist, 'Unknown Artist')
        self.assertEqual(md.title, 'JustATitleNoSeparator')

    @patch('whipsaw.extern.freedb.perform_lookup')
    def testNoMatchReturnsNone(self, mock_lookup):
        mock_lookup.return_value = []

        self.assertIsNone(program.Program.getCDDB(['id', 1, [0], 100]))

    @patch('whipsaw.extern.freedb.perform_lookup')
    def testProtocolErrorReturnsNone(self, mock_lookup):
        mock_lookup.side_effect = ValueError('bad response')

        self.assertIsNone(program.Program.getCDDB(['id', 1, [0], 100]))


class GetDiscogsTestCase(unittest.TestCase):

    def setUp(self):
        self.prog = program.Program(
            config.Config('/nonexistent/whipsaw-test.conf'))

    def testNoSearchHintReturnsNoneWithoutNetworkCall(self):
        self.assertIsNone(self.prog.getDiscogs(None))

    @patch('whipsaw.common.providers.metadata.discogs.search')
    def testDelegatesToDiscogsSearch(self, mock_search):
        expected = mbngs.DiscMetadata()
        mock_search.return_value = expected

        result = self.prog.getDiscogs('artist - title')

        self.assertIs(result, expected)
        mock_search.assert_called_once_with(self.prog._config,
                                            'artist - title')

    @patch('whipsaw.common.providers.metadata.discogs.search')
    def testTransientErrorIsCaughtAndReturnsNone(self, mock_search):
        from whipsaw.common.providers.base import ProviderTransientError
        mock_search.side_effect = ProviderTransientError('timed out')

        self.assertIsNone(self.prog.getDiscogs('artist - title'))

    def testNoSearchHintSkipsImportEntirely(self):
        # not just "returns None" -- the whole point is avoiding the
        # transitive `import requests` when there's nothing to search
        # for, so whipsaw works without it installed as long as
        # --search is never passed
        with patch('whipsaw.common.providers.metadata.discogs.search') \
                as mock_search:
            self.prog.getDiscogs(None)
            mock_search.assert_not_called()


class LazyOptionalImportsTestCase(unittest.TestCase):
    """
    Pillow and requests are optional (the `cover_art` extra), needed only
    for cover-art fetching and the Discogs metadata fallback. Historically
    whipsaw ran fine without them (cd.py checks importlib.util.find_spec
    ("PIL") before ever calling getCoverArt()) -- pin that
    whipsaw.common.program doesn't reintroduce a hard, module-load-time
    dependency on either by importing them at the top of the file instead
    of inside the specific methods that need them.
    """

    def testCoverArtAndDiscogsDependenciesAreNotImportedAtModuleLevel(self):
        for name in ('art_chain', 'normalize_art', 'discogs_metadata'):
            self.assertFalse(
                hasattr(program, name),
                '%r should be a lazy, function-local import in '
                'getCoverArt()/getDiscogs(), not a module-level one -- '
                'it transitively pulls in requests/PIL' % name)

    def testGetCoverArtFailsGracefullyWithoutRequests(self):
        prog = program.Program(config.Config('/nonexistent/whipsaw-test.conf'))
        with patch.dict('sys.modules', {'requests': None}):
            result = prog.getCoverArt('/tmp', mbngs.DiscMetadata())
        self.assertIsNone(result)

    def testGetDiscogsFailsGracefullyWithoutRequests(self):
        prog = program.Program(config.Config('/nonexistent/whipsaw-test.conf'))
        with patch.dict('sys.modules', {'requests': None}):
            result = prog.getDiscogs('artist - title')
        self.assertIsNone(result)
