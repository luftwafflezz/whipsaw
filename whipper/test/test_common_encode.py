# -*- Mode: Python; test-case-name: whipper.test.test_common_encode -*-
# vi:si:et:sw=4:sts=4:ts=4

"""
Baseline regression tests for whipper.common.encode.

These characterize today's FLAC-only encode/tag/embed behaviour (real
`flac`/`sox` subprocess calls, real mutagen reads/writes) so later work
generalizing this module to other containers/encoders has something to
diff against.
"""

import os
import shutil
import tempfile
import unittest
import wave
from unittest.mock import patch

from mutagen.flac import FLAC
from PIL import Image

from whipper.common import encode
from whipper.extern.task import task


FIXTURES_DIR = os.path.dirname(__file__)


def _make_silent_wav(path, num_frames=4410, channels=2, sample_rate=44100,
                     sample_width=2):
    """Write a minimal, valid silent WAV file for encoder tests."""
    with wave.open(path, 'wb') as w:
        w.setnchannels(channels)
        w.setsampwidth(sample_width)
        w.setframerate(sample_rate)
        w.writeframes(b'\x00' * num_frames * channels * sample_width)


def runTask(t):
    """Run a whipper Task synchronously to completion; return it."""
    runner = task.SyncRunner(verbose=False)
    runner.run(t)
    return t


class FlacEncodeTaskTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipper.test.encode.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.wav_path = os.path.join(self.tmpdir, 'track.wav')
        _make_silent_wav(self.wav_path)
        self.out_path = os.path.join(self.tmpdir, 'track.flac')

    def testEncodesToValidFlac(self):
        t = encode.FlacEncodeTask(self.wav_path, self.out_path)
        runTask(t)

        self.assertTrue(os.path.isfile(self.out_path))
        f = FLAC(self.out_path)
        self.assertEqual(f.info.channels, 2)
        self.assertEqual(f.info.sample_rate, 44100)
        # flac --verify decodes and compares while encoding; a corrupt
        # encode would have raised via check_call already, but confirm
        # the output is independently re-decodable too.
        self.assertEqual(f.info.length, 0.1)

    def testDescriptionMentionsWhat(self):
        t = encode.FlacEncodeTask(self.wav_path, self.out_path, what="foo")
        self.assertIn('foo', t.description)


class SoxPeakTaskTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipper.test.encode.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.wav_path = os.path.join(self.tmpdir, 'track.wav')
        _make_silent_wav(self.wav_path)

    def testSilentTrackHasZeroPeak(self):
        t = encode.SoxPeakTask(self.wav_path)
        runTask(t)
        self.assertEqual(t.peak, 0)


class TaggingTaskTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipper.test.encode.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.track_path = os.path.join(self.tmpdir, 'track.flac')
        shutil.copy(os.path.join(FIXTURES_DIR, 'track.flac'), self.track_path)

    def testTagsAreWrittenAndPersisted(self):
        tags = {'ARTIST': 'Some Artist', 'TITLE': 'Some Title'}
        t = encode.TaggingTask(self.track_path, tags)
        runTask(t)

        # re-open with a fresh mutagen object to make sure the tags were
        # actually persisted to disk, not just set on the in-memory object.
        reopened = FLAC(self.track_path)
        self.assertEqual(reopened['ARTIST'], ['Some Artist'])
        self.assertEqual(reopened['TITLE'], ['Some Title'])


class MakeFlacPictureTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipper.test.encode.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def testNoneWhenNoPath(self):
        self.assertIsNone(encode.EmbedPictureTask._make_flac_picture(None))

    def testJpegCoverIsReturned(self):
        cover_path = os.path.join(
            FIXTURES_DIR, '76df3287-6cda-33eb-8e9a-044b5e15ffdd.jpg')
        pic = encode.EmbedPictureTask._make_flac_picture(cover_path)
        self.assertIsNotNone(pic)
        self.assertEqual(pic.mime, 'image/jpeg')
        self.assertEqual((pic.width, pic.height), (494, 500))
        with open(cover_path, 'rb') as f:
            self.assertEqual(pic.data, f.read())

    def testUnsupportedFormatReturnsNone(self):
        # GIF is a real, PIL-openable format that _make_flac_picture does
        # not accept -- exercises the "format" rejection branch.
        gif_path = os.path.join(self.tmpdir, 'cover.gif')
        Image.new('RGB', (4, 4)).save(gif_path, format='GIF')

        pic = encode.EmbedPictureTask._make_flac_picture(gif_path)
        self.assertIsNone(pic)

    def testUnsupportedModeReturnsNone(self):
        # CMYK JPEGs decode to PIL mode 'CMYK', which isn't in the
        # accepted (P, RGB, SRGB) set -- exercises the "mode" rejection
        # branch, independently of the format check above.
        cmyk_path = os.path.join(self.tmpdir, 'cover_cmyk.jpg')
        Image.new('CMYK', (4, 4)).save(cmyk_path, format='JPEG')

        pic = encode.EmbedPictureTask._make_flac_picture(cmyk_path)
        self.assertIsNone(pic)


class EmbedPictureTaskTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipper.test.encode.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.track_path = os.path.join(self.tmpdir, 'track.flac')
        shutil.copy(os.path.join(FIXTURES_DIR, 'track.flac'), self.track_path)
        self.cover_path = os.path.join(
            FIXTURES_DIR, '76df3287-6cda-33eb-8e9a-044b5e15ffdd.jpg')

    def testPictureIsPersistedToDisk(self):
        """
        Regression test for the historical whipper bug where
        EmbedPictureTask.add_picture()'d a Picture but never called
        FLAC.save(), so --cover-art embed/complete silently did nothing
        on every released version (fixed only on develop via PR #610).
        Reopening with a fresh mutagen object is what actually catches
        that class of bug -- checking the in-memory object would not.
        """
        t = encode.EmbedPictureTask(self.track_path, self.cover_path)
        runTask(t)

        reopened = FLAC(self.track_path)
        self.assertEqual(len(reopened.pictures), 1)
        pic = reopened.pictures[0]
        self.assertEqual(pic.mime, 'image/jpeg')
        with open(self.cover_path, 'rb') as f:
            self.assertEqual(pic.data, f.read())

    def testNoCoverArtPathLeavesFileUntouched(self):
        t = encode.EmbedPictureTask(self.track_path, None)
        runTask(t)

        reopened = FLAC(self.track_path)
        self.assertEqual(len(reopened.pictures), 0)

    def testSilentSaveFailureIsCaught(self):
        """
        If FLAC.save() were ever again called-but-a-no-op (the historical
        bug class PictureEmbedVerificationError exists to catch), the
        post-write re-open check must raise rather than let the rip
        proceed as if embedding had succeeded.
        """
        with patch('mutagen.flac.FLAC.save', return_value=None):
            t = encode.EmbedPictureTask(self.track_path, self.cover_path)
            runner = task.SyncRunner(verbose=False)
            with self.assertRaises(task.TaskException) as cm:
                runner.run(t)

        self.assertIsInstance(
            cm.exception.exception, encode.PictureEmbedVerificationError)


if __name__ == '__main__':
    unittest.main()
