# -*- Mode: Python; test-case-name: whipsaw.test.test_common_config -*-
# vi:si:et:sw=4:sts=4:ts=4

# Copyright (C) 2009 Thomas Vander Stichele

# This file is part of whipsaw.
#
# whipsaw is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# whipsaw is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with whipsaw.  If not, see <http://www.gnu.org/licenses/>.

import codecs
import configparser
import os.path
import shutil
import tempfile
from urllib.parse import urlparse, quote

from whipsaw.common import directory

import logging
logger = logging.getLogger(__name__)


# Keyed providers (fanart.tv, Discogs, Last.fm) are listed in the default
# chain too, but each individually defaults to disabled (via its own
# Provider.enabled override) until the user configures credentials for
# it -- so their presence here is inert out of the box.
DEFAULT_ART_PROVIDER_CHAIN = [
    'caa_release', 'caa_release_group', 'itunes',
    'fanarttv', 'discogs', 'lastfm',
]
DEFAULT_ART_MAX_DIMENSION = 1200
DEFAULT_ART_FORMAT = 'jpeg'

DEFAULT_ENCODING_FORMAT = 'flac'
DEFAULT_FLAC_COMPRESSION_LEVEL = 8
DEFAULT_MP3_QUALITY = 0
DEFAULT_OPUS_BITRATE = '320k'
DEFAULT_AAC_BITRATE = '320k'


class Config:

    def __init__(self, path=None):
        self._path = path or directory.config_path()

        self._parser = configparser.ConfigParser(
            inline_comment_prefixes=';')

        self.open()

    def open(self):
        # Open the file with the correct encoding
        if os.path.exists(self._path):
            with codecs.open(self._path, 'r', encoding='utf-8') as f:
                self._parser.read_file(f)

        logger.debug('loaded %d sections from config file',
                     len(self._parser.sections()))

    def write(self):
        fd, path = tempfile.mkstemp(suffix='.whipsawrc')
        handle = os.fdopen(fd, 'w')
        self._parser.write(handle)
        handle.close()
        shutil.move(path, self._path)

    # any section

    def _getter(self, suffix, section, option):
        methodName = 'get' + suffix
        method = getattr(self._parser, methodName)
        try:
            return method(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return None

    def get(self, section, option):
        return self._getter('', section, option)

    def getboolean(self, section, option):
        return self._getter('boolean', section, option)

    # musicbrainz section

    def get_musicbrainz_server(self):
        conf = self.get('musicbrainz', 'server') or 'https://musicbrainz.org'
        if not conf.startswith(('http://', 'https://')):
            raise KeyError('Invalid MusicBrainz server: unsupported '
                           'or missing scheme')
        scheme, netloc, _, _, _, _ = urlparse(conf)
        return {'scheme': scheme, 'netloc': netloc}

    # cover art section

    def get_art_provider_chain(self):
        """Ordered list of enabled cover art provider names."""
        raw = self.get('cover_art', 'chain')
        if raw:
            names = [n.strip() for n in raw.split(',') if n.strip()]
        else:
            names = list(DEFAULT_ART_PROVIDER_CHAIN)
        return [n for n in names
                if self.getboolean('art:%s' % n, 'enabled') is not False]

    def get_cover_art_max_dimension(self):
        raw = self.get('cover_art', 'max_dimension')
        try:
            return int(raw)
        except (TypeError, ValueError):
            return DEFAULT_ART_MAX_DIMENSION

    def get_cover_art_format(self):
        return self.get('cover_art', 'format') or DEFAULT_ART_FORMAT

    def get_provider_credential(self, section, key):
        """e.g. get_provider_credential('art:fanarttv', 'api_key')."""
        return self.get(section, key)

    # encoding section

    def get_encoding_format(self):
        return self.get('encoding', 'format') or DEFAULT_ENCODING_FORMAT

    def get_flac_compression_level(self):
        raw = self.get('encoding', 'flac_compression_level')
        try:
            return int(raw)
        except (TypeError, ValueError):
            return DEFAULT_FLAC_COMPRESSION_LEVEL

    def get_mp3_quality(self):
        raw = self.get('encoding', 'mp3_quality')
        try:
            return int(raw)
        except (TypeError, ValueError):
            return DEFAULT_MP3_QUALITY

    def get_opus_bitrate(self):
        return self.get('encoding', 'opus_bitrate') or DEFAULT_OPUS_BITRATE

    def get_aac_bitrate(self):
        return self.get('encoding', 'aac_bitrate') or DEFAULT_AAC_BITRATE

    # drive sections

    def setReadOffset(self, vendor, model, release, offset):
        """Set a read offset for the given drive."""
        self._setDriveOption(vendor, model, release, 'read_offset', offset)

    def getReadOffset(self, vendor, model, release):
        """Get a read offset for the given drive."""
        return int(self._getDriveOption(vendor, model, release, 'read_offset'))

    def setDefeatsCache(self, vendor, model, release, defeat):
        """Set whether the drive defeats the cache."""
        self._setDriveOption(vendor, model, release, 'defeats_cache', defeat)

    def getDefeatsCache(self, vendor, model, release):
        option = self._getDriveOption(vendor, model, release, 'defeats_cache')
        return option == 'True'

    def _findDriveSection(self, vendor, model, release):
        for name in self._parser.sections():
            if not name.startswith('drive:'):
                continue

            logger.debug('looking at section %r', name)
            conf = {}
            for key in ['vendor', 'model', 'release']:
                locals()[key] = locals()[key].strip()
                conf[key] = self._parser.get(name, key)
                logger.debug("%s: '%s' versus '%s'",
                             key, locals()[key], conf[key])
            if vendor.strip() != conf['vendor']:
                continue
            if model.strip() != conf['model']:
                continue
            if release.strip() != conf['release']:
                continue

            return name

        raise KeyError("Could not find configuration section for %s/%s/%s" % (
            vendor, model, release))

    def _findOrCreateDriveSection(self, vendor, model, release):
        try:
            section = self._findDriveSection(vendor, model, release)
        except KeyError:
            section = 'drive:' + quote('%s:%s:%s' % (
                vendor, model, release))
            self._parser.add_section(section)
            for key in ['vendor', 'model', 'release']:
                self._parser.set(section, key, locals()[key].strip())

        self.write()

        return self._findDriveSection(vendor, model, release)

    def _getDriveOption(self, vendor, model, release, key):
        """Get an option for the given drive."""
        section = self._findDriveSection(vendor, model, release)
        try:
            return self._parser.get(section, key)
        except configparser.NoOptionError:
            raise KeyError("Could not find %s for %s/%s/%s" % (
                key, vendor, model, release))

    def _setDriveOption(self, vendor, model, release, key, value):
        """
        Set an option for the given drive.

        Strips the given strings of leading and trailing whitespace.
        """
        section = self._findOrCreateDriveSection(vendor, model, release)
        self._parser.set(section, key, str(value))
        self.write()
