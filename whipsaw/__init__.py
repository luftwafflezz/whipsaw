import logging
import os
import sys

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version('whipsaw')
except PackageNotFoundError:
    # not installed as package or is being run from source/git checkout
    from setuptools_scm import get_version
    __version__ = get_version()

level = logging.INFO
if 'WHIPSAW_DEBUG' in os.environ:
    level = os.environ['WHIPSAW_DEBUG'].upper()

log_init_func = logging.basicConfig
if 'WHIPSAW_COLOR_LOG' in os.environ:
    import coloredlogs

    def init_coloredlogs(**kwargs):
        # coloredlogs comes with its own log format, we don't want to use that
        coloredlogs.install(fmt=logging.BASIC_FORMAT, **kwargs)
    log_init_func = init_coloredlogs

if 'WHIPSAW_LOGFILE' in os.environ:
    log_init_func(filename=os.environ['WHIPSAW_LOGFILE'],
                  filemode='w', level=level)
else:
    log_init_func(stream=sys.stderr, level=level)
