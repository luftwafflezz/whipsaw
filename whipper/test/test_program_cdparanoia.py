# -*- Mode: Python; test-case-name: whipper.test.test_program_cdparanoia -*-
# vi:si:et:sw=4:sts=4:ts=4

import os
import shutil
import tempfile

from whipper.extern.task import task

from whipper.image import table
from whipper.program import cdparanoia

from whipper.test import common


class ParseTestCase(common.TestCase):

    def setUp(self):
        # report from Afghan Whigs - Sweet Son Of A Bitch
        path = os.path.join(os.path.dirname(__file__),
                            'cdparanoia.progress')
        self._parser = cdparanoia.ProgressParser(start=45990, stop=47719)

        self._handle = open(path)

    def testParse(self):
        for line in self._handle.readlines():
            self._parser.parse(line)

        q = '%.01f %%' % (self._parser.getTrackQuality() * 100.0, )
        self.assertEqual(q, '99.6 %')


class Parse1FrameTestCase(common.TestCase):

    def setUp(self):
        path = os.path.join(os.path.dirname(__file__),
                            'cdparanoia.progress.strokes')
        self._parser = cdparanoia.ProgressParser(start=0, stop=0)

        self._handle = open(path)

    def testParse(self):
        for line in self._handle.readlines():
            self._parser.parse(line)

        q = '%.01f %%' % (self._parser.getTrackQuality() * 100.0, )
        self.assertEqual(q, '100.0 %')


class ErrorTestCase(common.TestCase):

    def setUp(self):
        # report from a rip with offset -1164 causing scsi errors
        path = os.path.join(os.path.dirname(__file__),
                            'cdparanoia.progress.error')
        self._parser = cdparanoia.ProgressParser(start=0, stop=10800)

        self._handle = open(path)

    def testParse(self):
        for line in self._handle.readlines():
            self._parser.parse(line)

        q = '%.01f %%' % (self._parser.getTrackQuality() * 100.0, )
        self.assertEqual(q, '79.6 %')


class VersionTestCase(common.TestCase):

    def testGetVersion(self):
        v = cdparanoia.getCdParanoiaVersion()
        self.assertTrue(v)


class AnalyzeFileTask(cdparanoia.AnalyzeTask):

    def __init__(self, path):
        self.command = ['cat', path]

    def readbytesout(self, bytes_stdout):
        self.readbyteserr(bytes_stdout)


class CacheTestCase(common.TestCase):

    def testDefeatsCache(self):
        self.runner = task.SyncRunner(verbose=False)

        path = os.path.join(os.path.dirname(__file__),
                            'cdparanoia', 'PX-L890SA.cdparanoia-A.stderr')
        t = AnalyzeFileTask(path)
        self.runner.run(t)
        self.assertTrue(t.defeatsCache)


class ReadVerifyTrackTaskConstructionTestCase(common.TestCase):
    """
    ReadVerifyTrackTask.__init__() only builds its sub-task list -- it
    doesn't run anything until a runner calls .start() on it, which is
    where the real `cd-paranoia` subprocess call (needing physical drive
    hardware) happens. That means the wiring itself -- which sub-tasks
    get created, in what order, with what format_name/AccurateRip
    parameters -- is testable without hardware, even though the class as
    a whole has never had any test coverage.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='whipper.test.cdparanoia.')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

        self.tbl = table.Table()
        self.tbl.tracks.append(table.Track(1, audio=True))
        self.tbl.tracks[0].index(1, absolute=0)
        self.tbl.leadout = 1000

    def _make_task(self, **kwargs):
        path = os.path.join(self.tmpdir, 'track.out')
        t = cdparanoia.ReadVerifyTrackTask(
            path, self.tbl, start=0, stop=999, overread=False, **kwargs)
        # constructor already created real temp files on disk; clean them
        # up since we never call stop() to do it ourselves
        self.addCleanup(lambda: os.path.exists(t._tmpwavpath) and
                        os.unlink(t._tmpwavpath))
        self.addCleanup(lambda: os.path.exists(t._tmppath) and
                        os.unlink(t._tmppath))
        return t

    def testTaskListOrderAndCount(self):
        t = self._make_task(formatName='mp3')
        self.assertEqual(len(t.tasks), 9)
        self.assertIs(t.tasks[0], t._test_read_task)
        self.assertIs(t.tasks[1], t._test_checksum_task)
        self.assertIs(t.tasks[2], t._verify_read_task)
        self.assertIs(t.tasks[3], t._verify_checksum_task)
        self.assertIs(t.tasks[4], t._encode_task)
        self.assertIs(t.tasks[5], t._encode_verify_task)
        self.assertIs(t.tasks[6], t._peak_task)
        self.assertIs(t.tasks[7], t._tag_task)
        self.assertIs(t.tasks[8], t._embed_picture_task)

    def testFormatNamePropagatesToEncodeTasks(self):
        t = self._make_task(formatName='opus')
        self.assertEqual(t._encode_task.format_name, 'opus')
        self.assertEqual(t._encode_verify_task.format_name, 'opus')
        self.assertEqual(t._tag_task.format_name, 'opus')
        self.assertEqual(t._embed_picture_task.format_name, 'opus')

    def testDefaultFormatIsFlac(self):
        t = self._make_task()
        self.assertEqual(t._encode_task.format_name, 'flac')

    def testAccurateRipParametersStored(self):
        t = self._make_task(arTrackNumber=3, arTotalTracks=12)
        self.assertEqual(t._ar_track_number, 3)
        self.assertEqual(t._ar_total_tracks, 12)

    def testAccurateRipParametersDefaultToNone(self):
        t = self._make_task()
        self.assertIsNone(t._ar_track_number)
        self.assertIsNone(t._ar_total_tracks)
