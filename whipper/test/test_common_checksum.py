# -*- Mode: Python; test-case-name: whipper.test.test_common_checksum -*-
# vi:si:et:sw=4:sts=4:ts=4

import os
import shutil
import subprocess
import tempfile
import unittest

from whipper.common import checksum
from whipper.extern.task import task

FIXTURES_DIR = os.path.dirname(__file__)


def runTask(t):
    runner = task.SyncRunner(verbose=False)
    runner.run(t)
    return t


class Crc32OfWavTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipper.test.checksum.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.wav_path = os.path.join(self.tmpdir, 'track.wav')
        subprocess.check_call(['flac', '-d', '--silent', '-o', self.wav_path,
                               os.path.join(FIXTURES_DIR, 'track.flac')])

    def testDeterministic(self):
        self.assertEqual(checksum.crc32_of_wav(self.wav_path),
                         checksum.crc32_of_wav(self.wav_path))


class CRC32TaskTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipper.test.checksum.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.wav_path = os.path.join(self.tmpdir, 'track.wav')
        subprocess.check_call(['flac', '-d', '--silent', '-o', self.wav_path,
                               os.path.join(FIXTURES_DIR, 'track.flac')])
        self.flac_path = os.path.join(FIXTURES_DIR, 'track.flac')

    def testWaveMode(self):
        t = checksum.CRC32Task(self.wav_path, is_wave=True)
        runTask(t)
        self.assertEqual(t.checksum, checksum.crc32_of_wav(self.wav_path))

    def testNonWaveModeDecodesFirst(self):
        """
        is_wave=False now decodes via ffmpeg instead of shelling out to
        `flac -d` directly -- this is a mechanical change to the decode
        mechanism (whipper.program.ffmpeg.decode_to_wav), not to the
        verification logic, and should produce the same checksum as
        decoding the same audio's WAV directly.
        """
        wave_mode_task = checksum.CRC32Task(self.wav_path, is_wave=True)
        runTask(wave_mode_task)

        non_wave_task = checksum.CRC32Task(self.flac_path, is_wave=False)
        runTask(non_wave_task)

        self.assertEqual(wave_mode_task.checksum, non_wave_task.checksum)


if __name__ == '__main__':
    unittest.main()
