# -*- Mode: Python; test-case-name: whipsaw.test.test_program_cdparanoia -*-
# vi:si:et:sw=4:sts=4:ts=4

from whipsaw.program import cdrdao
from whipsaw.test import common

# TODO: Current test architecture makes testing cdrdao difficult. Revisit.


class VersionTestCase(common.TestCase):
    def testGetVersion(self):
        v = cdrdao.version()
        self.assertTrue(v)
        # make sure it starts with a digit
        self.assertTrue(int(v[0]))
