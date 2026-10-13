# -*- Mode: Python; test-case-name: whipsaw.test.test_result_plugins -*-
# vi:si:et:sw=4:sts=4:ts=4

import unittest
from unittest.mock import patch

from whipsaw.result import result


class FakePlugin:
    pass


class FakeEntryPoint:
    name = 'fake'

    @staticmethod
    def load():
        return FakePlugin


class SelectableEntryPoints:
    """What entry_points() returns on Python 3.10+."""

    def select(self, **params):
        assert params == {'group': 'whipsaw.logger'}
        return [FakeEntryPoint()]


class GetLoggersTestCase(unittest.TestCase):

    def testBuiltInLoggerIsAlwaysThere(self):
        # the real entry_points() of whichever Python is running the tests
        self.assertIn('whipsaw', result.getLoggers())

    def testSelectableEntryPoints(self):
        with patch.object(result, 'entry_points',
                          return_value=SelectableEntryPoints()):
            loggers = result.getLoggers()
        self.assertIs(loggers['fake'], FakePlugin)
        self.assertIn('whipsaw', loggers)

    def testPlainDictEntryPointsOfPython39(self):
        # 3.9's entry_points() takes no arguments and returns a plain dict
        # of group name -> entry points, so selecting by keyword raises
        # TypeError there.
        eps = {'whipsaw.logger': [FakeEntryPoint()], 'other': []}
        with patch.object(result, 'entry_points', return_value=eps):
            loggers = result.getLoggers()
        self.assertIs(loggers['fake'], FakePlugin)
        self.assertIn('whipsaw', loggers)

    def testPlainDictWithoutOurGroup(self):
        with patch.object(result, 'entry_points', return_value={}):
            self.assertEqual(list(result.getLoggers()), ['whipsaw'])
