# -*- Mode: Python; test-case-name: whipsaw.test.test_program_sox -*-

import os
import tempfile

from whipsaw.common import common
from whipsaw.extern.task import task
from whipsaw.program.soxi import AudioLengthTask
from whipsaw.test import common as tcommon

base_track_file = os.path.join(os.path.dirname(__file__), 'track.flac')
base_track_length = 10 * common.SAMPLES_PER_FRAME


class AudioLengthTestCase(tcommon.TestCase):

    def testLength(self):
        path = base_track_file
        t = AudioLengthTask(path)
        runner = task.SyncRunner()
        runner.run(t, verbose=False)
        self.assertEqual(t.length, base_track_length)


class AudioLengthPathTestCase(tcommon.TestCase):

    def _testSuffix(self, suffix):
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "wb") as temptrack:
            with open(base_track_file, "rb") as f:
                temptrack.write(f.read())

        t = AudioLengthTask(path)
        runner = task.SyncRunner()
        runner.run(t, verbose=False)
        self.assertEqual(t.length, base_track_length)
        os.unlink(path)


class NormalAudioLengthPathTestCase(AudioLengthPathTestCase):

    def testSingleQuote(self):
        self._testSuffix("whipsaw.test.Guns 'N Roses.flac")

    def testDoubleQuote(self):
        # This test makes sure we can checksum files with double quote in
        # their name
        self._testSuffix('whipsaw.test.12" edit.flac')


class AbsentFileAudioLengthPathTestCase(AudioLengthPathTestCase):
    def testAbsentFile(self):
        tempdir = tempfile.mkdtemp()
        path = os.path.join(tempdir, "nonexistent.flac")

        t = AudioLengthTask(path)
        runner = task.SyncRunner()
        self.assertRaises(task.TaskException, runner.run,
                          t, verbose=False)

        os.rmdir(tempdir)
