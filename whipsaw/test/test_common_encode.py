# -*- Mode: Python; test-case-name: whipsaw.test.test_common_encode -*-
# vi:si:et:sw=4:sts=4:ts=4

"""
Tests for whipsaw.common.encode: the real `flac`/ffmpeg/`sox` subprocess
calls and real mutagen reads/writes, per output format.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
import wave
from unittest.mock import patch

from mutagen.flac import FLAC

from whipsaw.common import encode
from whipsaw.extern.task import task
from whipsaw.program import ffmpeg


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
    """Run a whipsaw Task synchronously to completion; return it."""
    runner = task.SyncRunner(verbose=False)
    runner.run(t)
    return t


class EncodeTaskTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipsaw.test.encode.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.wav_path = os.path.join(self.tmpdir, 'track.wav')
        _make_silent_wav(self.wav_path)
        self.out_path = os.path.join(self.tmpdir, 'track.flac')

    def testEncodesToValidFlac(self):
        t = encode.EncodeTask(self.wav_path, self.out_path, 'flac')
        runTask(t)

        self.assertTrue(os.path.isfile(self.out_path))
        f = FLAC(self.out_path)
        self.assertEqual(f.info.channels, 2)
        self.assertEqual(f.info.sample_rate, 44100)
        self.assertEqual(f.info.length, 0.1)

    def testDescriptionMentionsWhatAndFormat(self):
        t = encode.EncodeTask(self.wav_path, self.out_path, 'flac',
                              what="foo")
        self.assertIn('foo', t.description)
        self.assertIn('FLAC', t.description)

    def testEachSupportedFormatEncodesSuccessfully(self):
        for format_name, profile in ffmpeg.CODEC_PROFILES.items():
            out_path = os.path.join(
                self.tmpdir, 'out_%s.%s' % (format_name, profile['ext']))
            t = encode.EncodeTask(self.wav_path, out_path, format_name)
            runTask(t)
            self.assertTrue(os.path.isfile(out_path),
                            '%s did not produce output' % format_name)
            self.assertGreater(os.path.getsize(out_path), 0)


class EncodeVerifyTaskTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipsaw.test.encode.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.wav_path = os.path.join(self.tmpdir, 'track.wav')
        subprocess.check_call(['flac', '-d', '--silent', '-o',
                               self.wav_path,
                               os.path.join(FIXTURES_DIR, 'track.flac')])

    def _encode(self, format_name):
        profile = ffmpeg.CODEC_PROFILES[format_name]
        out_path = os.path.join(self.tmpdir, 'out.%s' % profile['ext'])
        ffmpeg.encode(self.wav_path, out_path, format_name)
        return out_path

    def testLosslessFormatsVerifySuccessfully(self):
        for format_name in ('flac', 'wav', 'alac'):
            out_path = self._encode(format_name)
            t = encode.EncodeVerifyTask(self.wav_path, out_path,
                                        format_name)
            runTask(t)
            self.assertIsNotNone(t.checksum)

    def testLossyFormatsVerifySuccessfully(self):
        for format_name in ('mp3', 'opus', 'vorbis', 'aac'):
            out_path = self._encode(format_name)
            t = encode.EncodeVerifyTask(self.wav_path, out_path,
                                        format_name)
            runTask(t)  # should not raise

    def testLosslessMismatchRaises(self):
        out_path = self._encode('flac')
        # corrupt the source comparison by pointing at a different WAV
        other_wav = os.path.join(self.tmpdir, 'other.wav')
        _make_silent_wav(other_wav)

        t = encode.EncodeVerifyTask(other_wav, out_path, 'flac')
        with self.assertRaises(task.TaskException) as cm:
            runTask(t)
        self.assertIsInstance(cm.exception.exception,
                              encode.EncodeVerificationError)

    def testDecodeFailureRaises(self):
        bogus_path = os.path.join(self.tmpdir, 'not_really_audio.flac')
        with open(bogus_path, 'wb') as f:
            f.write(b'this is not a flac file')

        t = encode.EncodeVerifyTask(self.wav_path, bogus_path, 'flac')
        with self.assertRaises(task.TaskException) as cm:
            runTask(t)
        self.assertIsInstance(cm.exception.exception,
                              encode.EncodeVerificationError)


class SoxPeakTaskTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipsaw.test.encode.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.wav_path = os.path.join(self.tmpdir, 'track.wav')
        _make_silent_wav(self.wav_path)

    def testSilentTrackHasZeroPeak(self):
        t = encode.SoxPeakTask(self.wav_path)
        runTask(t)
        self.assertEqual(t.peak, 0)


class TaggingTaskTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipsaw.test.encode.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.track_path = os.path.join(self.tmpdir, 'track.flac')
        shutil.copy(os.path.join(FIXTURES_DIR, 'track.flac'), self.track_path)

    def testTagsAreWrittenAndPersisted(self):
        track_tags = {'ARTIST': 'Some Artist', 'TITLE': 'Some Title'}
        t = encode.TaggingTask(self.track_path, track_tags, 'flac')
        runTask(t)

        # re-open with a fresh mutagen object to make sure the tags were
        # actually persisted to disk, not just set on the in-memory object.
        reopened = FLAC(self.track_path)
        self.assertEqual(reopened['ARTIST'], ['Some Artist'])
        self.assertEqual(reopened['TITLE'], ['Some Title'])


class PreparePictureTestCase(unittest.TestCase):
    """
    _prepare_picture() no longer rejects unsupported formats/modes the way
    the old FLAC-only _make_flac_picture() did -- that validation now
    happens once, upstream, in Program.getCoverArt()'s normalize() step,
    which guarantees every cover_art_path this ever receives is already a
    clean JPEG or PNG. This just needs to read it back correctly.
    """

    def testNoneWhenNoPath(self):
        self.assertIsNone(encode.EmbedPictureTask._prepare_picture(None))

    def testJpegCoverIsReturned(self):
        cover_path = os.path.join(
            FIXTURES_DIR, '76df3287-6cda-33eb-8e9a-044b5e15ffdd.jpg')
        pic = encode.EmbedPictureTask._prepare_picture(cover_path)
        self.assertIsNotNone(pic)
        self.assertEqual(pic.mime_type, 'image/jpeg')
        self.assertEqual((pic.width, pic.height), (494, 500))
        with open(cover_path, 'rb') as f:
            self.assertEqual(pic.data, f.read())


class EmbedPictureTaskTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipsaw.test.encode.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.track_path = os.path.join(self.tmpdir, 'track.flac')
        shutil.copy(os.path.join(FIXTURES_DIR, 'track.flac'), self.track_path)
        self.cover_path = os.path.join(
            FIXTURES_DIR, '76df3287-6cda-33eb-8e9a-044b5e15ffdd.jpg')

    def testPictureIsPersistedToDisk(self):
        """
        Regression test for the historical whipsaw bug where
        EmbedPictureTask.add_picture()'d a Picture but never called
        FLAC.save(), so --cover-art embed/complete silently did nothing
        on every released version (fixed only on develop via PR #610).
        Reopening with a fresh mutagen object is what actually catches
        that class of bug -- checking the in-memory object would not.
        """
        t = encode.EmbedPictureTask(self.track_path, self.cover_path, 'flac')
        runTask(t)

        reopened = FLAC(self.track_path)
        self.assertEqual(len(reopened.pictures), 1)
        pic = reopened.pictures[0]
        self.assertEqual(pic.mime, 'image/jpeg')
        with open(self.cover_path, 'rb') as f:
            self.assertEqual(pic.data, f.read())

    def testNoCoverArtPathLeavesFileUntouched(self):
        t = encode.EmbedPictureTask(self.track_path, None, 'flac')
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
            t = encode.EmbedPictureTask(self.track_path, self.cover_path,
                                        'flac')
            runner = task.SyncRunner(verbose=False)
            with self.assertRaises(task.TaskException) as cm:
                runner.run(t)

        self.assertIsInstance(
            cm.exception.exception, encode.PictureEmbedVerificationError)


if __name__ == '__main__':
    unittest.main()
