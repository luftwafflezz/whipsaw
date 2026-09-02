# -*- Mode: Python; test-case-name: whipper.test.test_program_arc -*-
# vi:si:et:sw=4:sts=4:ts=4

"""
Regression test for a load-bearing invariant of the ffmpeg encoding work:
AccurateRip's checksum extension (whipper.program.arc, backed by the
compiled `accuraterip` module) is built on libsndfile and accepts *either*
WAV or FLAC input, decoding both to the same PCM before checksumming.

That means AccurateRip verification can be computed from the pre-encode
WAV unconditionally, regardless of which container the user ultimately
encodes to (FLAC/ALAC/MP3/Opus/...) -- encoder choice becomes provably
irrelevant to AccurateRip correctness, as long as this equivalence holds.
This test pins that equivalence down so a future change can't silently
break it.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from whipper.program.arc import accuraterip_checksum

FIXTURES_DIR = os.path.dirname(__file__)


class WavFlacEquivalenceTestCase(unittest.TestCase):
    """WAV and FLAC encodings of the same audio must checksum identically."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipper.test.arc.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

        self.flac_path = os.path.join(FIXTURES_DIR, 'track.flac')
        self.wav_path = os.path.join(self.tmpdir, 'track.wav')
        subprocess.check_call(['flac', '-d', '--silent',
                               '-o', self.wav_path, self.flac_path])

    def testChecksumsMatchAcrossContainers(self):
        v1_wav, v2_wav = accuraterip_checksum(self.wav_path, 1, 1)
        v1_flac, v2_flac = accuraterip_checksum(self.flac_path, 1, 1)

        self.assertIsNotNone(v1_wav)
        self.assertIsNotNone(v2_wav)
        self.assertEqual(v1_wav, v1_flac)
        self.assertEqual(v2_wav, v2_flac)

    def testChecksumsAreDeterministic(self):
        first = accuraterip_checksum(self.wav_path, 1, 1)
        second = accuraterip_checksum(self.wav_path, 1, 1)
        self.assertEqual(first, second)


if __name__ == '__main__':
    unittest.main()
