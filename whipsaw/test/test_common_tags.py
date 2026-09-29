# -*- Mode: Python; test-case-name: whipsaw.test.test_common_tags -*-
# vi:si:et:sw=4:sts=4:ts=4

import os
import shutil
import subprocess
import tempfile
import unittest

from whipsaw.common import tags
from whipsaw.program import ffmpeg

FIXTURES_DIR = os.path.dirname(__file__)

SAMPLE_TAGS = {
    'ARTIST': 'Test Artist',
    'ALBUMARTIST': 'Test Album Artist',
    'TITLE': 'Test Title',
    'ALBUM': 'Test Album',
    'TRACKNUMBER': '3',
    'TRACKTOTAL': '12',
    'DISCNUMBER': '1',
    'DISCTOTAL': '2',
    'DATE': '2020-01-01',
    'ISRC': 'US1234567890',
    'COMPOSER': ['Composer A', 'Composer B'],
    'MUSICBRAINZ_DISCID': 'abc123',
    'MUSICBRAINZ_TRACKID': 'def456',
}


def _encode_fixture(tmpdir, format_name):
    wav_path = os.path.join(tmpdir, 'orig.wav')
    subprocess.check_call(['flac', '-d', '--silent', '-o', wav_path,
                           os.path.join(FIXTURES_DIR, 'track.flac')])
    profile = ffmpeg.CODEC_PROFILES[format_name]
    out_path = os.path.join(tmpdir, 'track.%s' % profile['ext'])
    ffmpeg.encode(wav_path, out_path, format_name)
    return out_path


def _picture():
    cover_path = os.path.join(
        FIXTURES_DIR, '76df3287-6cda-33eb-8e9a-044b5e15ffdd.jpg')
    with open(cover_path, 'rb') as f:
        data = f.read()
    return tags.PreparedPicture(data, 'image/jpeg', 494, 500)


class WriteAndEmbedAcrossFormatsTestCase(unittest.TestCase):
    """
    Every supported output format should accept the same internal tag
    dict and picture, and read them back correctly -- this is the
    cross-container round trip the ffmpeg encoding work depends on.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipsaw.test.tags.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def _roundtrip(self, format_name):
        path = _encode_fixture(self.tmpdir, format_name)
        writer = tags.get_tag_writer(format_name)
        writer.write(path, SAMPLE_TAGS)
        writer.embed_picture_and_verify(path, _picture())
        return path, writer

    def testFlac(self):
        from mutagen.flac import FLAC
        path, writer = self._roundtrip('flac')
        w = FLAC(path)
        self.assertEqual(w['ARTIST'], ['Test Artist'])
        self.assertEqual(w['COMPOSER'], ['Composer A', 'Composer B'])
        self.assertEqual(len(w.pictures), 1)

    def testWav(self):
        from mutagen.wave import WAVE
        path, writer = self._roundtrip('wav')
        w = WAVE(path)
        self.assertEqual(w.tags['TPE1'].text, ['Test Artist'])
        self.assertEqual(w.tags['TRCK'].text, ['3/12'])
        self.assertEqual(w.tags['TPOS'].text, ['1/2'])
        self.assertEqual(w.tags['TSRC'].text, ['US1234567890'])
        self.assertTrue(writer.has_picture(path))

    def testMp3(self):
        from mutagen.mp3 import MP3
        path, writer = self._roundtrip('mp3')
        w = MP3(path)
        self.assertEqual(w.tags['TPE1'].text, ['Test Artist'])
        self.assertEqual(w.tags['TXXX:MUSICBRAINZ_DISCID'].text, ['abc123'])
        self.assertTrue(writer.has_picture(path))

    def testAlac(self):
        from mutagen.mp4 import MP4
        path, writer = self._roundtrip('alac')
        w = MP4(path)
        self.assertEqual(w['\xa9ART'], ['Test Artist'])
        self.assertEqual(w['trkn'], [(3, 12)])
        self.assertEqual(w['disk'], [(1, 2)])
        freeform = bytes(w['----:com.apple.iTunes:MUSICBRAINZ_DISCID'][0])
        self.assertEqual(freeform, b'abc123')
        self.assertTrue(writer.has_picture(path))

    def testAac(self):
        path, writer = self._roundtrip('aac')
        self.assertTrue(writer.has_picture(path))

    def testOpus(self):
        from mutagen.oggopus import OggOpus
        path, writer = self._roundtrip('opus')
        w = OggOpus(path)
        self.assertEqual(w['ARTIST'], ['Test Artist'])
        self.assertTrue(writer.has_picture(path))

    def testVorbis(self):
        from mutagen.oggvorbis import OggVorbis
        path, writer = self._roundtrip('vorbis')
        w = OggVorbis(path)
        self.assertEqual(w['ARTIST'], ['Test Artist'])
        self.assertTrue(writer.has_picture(path))


class HasPictureNegativeTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipsaw.test.tags.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def testFlacWithoutPicture(self):
        path = _encode_fixture(self.tmpdir, 'flac')
        writer = tags.get_tag_writer('flac')
        writer.write(path, SAMPLE_TAGS)
        self.assertFalse(writer.has_picture(path))

    def testMp3WithoutPicture(self):
        path = _encode_fixture(self.tmpdir, 'mp3')
        writer = tags.get_tag_writer('mp3')
        writer.write(path, SAMPLE_TAGS)
        self.assertFalse(writer.has_picture(path))


class GetTagWriterTestCase(unittest.TestCase):

    def testUnknownFormatRaisesKeyError(self):
        self.assertRaises(KeyError, tags.get_tag_writer, 'not_a_format')


if __name__ == '__main__':
    unittest.main()
