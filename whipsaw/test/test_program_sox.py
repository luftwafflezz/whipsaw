# -*- Mode: Python; test-case-name: whipsaw.test.test_program_sox -*-

import os

from whipsaw.program import sox
from whipsaw.test import common


class PeakLevelTestCase(common.TestCase):
    def setUp(self):
        self.path = os.path.join(os.path.dirname(__file__), 'track.flac')

    def testParse(self):
        self.assertEqual(26215, sox.peak_level(self.path))
