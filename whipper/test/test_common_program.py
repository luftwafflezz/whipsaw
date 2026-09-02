# -*- Mode: Python; test-case-name: whipper.test.test_common_program -*-
# vi:si:et:sw=4:sts=4:ts=4


import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import musicbrainzngs

from whipper.common import program, mbngs, config
from whipper.command.cd import DEFAULT_DISC_TEMPLATE


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
        self.path = tempfile.mkdtemp(prefix='whipper.test.coverart.')
        self.addCleanup(shutil.rmtree, self.path, ignore_errors=True)
        self.prog = program.Program(
            config.Config('/nonexistent/whipper-test.conf'))

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
