import os
import subprocess
import sys
import tempfile
import unittest


class LoggingEnvTestCase(unittest.TestCase):
    """The WHIPSAW_* logging switches documented in the README must work."""

    def testLogfileAndDebugLevel(self):
        # logging is configured at import time, so it needs a fresh process
        top = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        with tempfile.TemporaryDirectory() as tmp:
            logfile = os.path.join(tmp, 'out.log')
            env = dict(os.environ,
                       WHIPSAW_LOGFILE=logfile,
                       WHIPSAW_DEBUG='DEBUG',
                       PYTHONPATH=os.pathsep.join(
                           [top] + os.environ.get('PYTHONPATH', '').split(
                               os.pathsep)))
            subprocess.run(
                [sys.executable, '-c',
                 'import logging, whipsaw; '
                 'logging.getLogger("t").debug("marker-debug-line")'],
                env=env, check=True)
            with open(logfile) as f:
                self.assertIn('marker-debug-line', f.read())
