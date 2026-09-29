# -*- Mode: Python; test-case-name: whipsaw.test.test_common_drive -*-
# vi:si:et:sw=4:sts=4:ts=4

from whipsaw.test import common
from whipsaw.common import drive


class ListifyTestCase(common.TestCase):

    def testString(self):
        string = '/dev/sr0'
        self.assertEqual(drive._listify(string), [string, ])

    def testList(self):
        lst = ['/dev/scd0', '/dev/sr0']
        self.assertEqual(drive._listify(lst), lst)
