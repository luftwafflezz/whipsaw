# -*- Mode: Python; test-case-name: whipsaw.test.test_common_encode -*-
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

import os
import tempfile
import wave

from whipsaw.common import checksum, tags
from whipsaw.common.tags import PictureEmbedVerificationError  # noqa: F401
from whipsaw.extern.task import task

from whipsaw.program import ffmpeg
from whipsaw.program import sox

import logging
logger = logging.getLogger(__name__)


class SoxPeakTask(task.Task):
    description = 'Calculating peak level'

    def __init__(self, track_path):
        self.track_path = track_path
        self.peak = None

    def start(self, runner):
        task.Task.start(self, runner)
        self.schedule(0.0, self._sox_peak)

    def _sox_peak(self):
        self.peak = sox.peak_level(self.track_path)
        self.stop()


class EncodeTask(task.Task):
    """Encode a WAV to the given format via ffmpeg."""

    def __init__(self, track_path, track_out_path, format_name,
                 config=None, what="track"):
        self.track_path = track_path
        self.track_out_path = track_out_path
        self.format_name = format_name
        self.config = config
        self.new_path = None
        self.description = 'Encoding %s to %s' % (
            what, format_name.upper())

    def start(self, runner):
        task.Task.start(self, runner)
        self.schedule(0.0, self._encode)

    def _encode(self):
        ffmpeg.encode(self.track_path, self.track_out_path,
                      self.format_name, self.config)
        self.stop()


class EncodeVerificationError(Exception):
    """Raised when a track's encoded output fails post-encode verification."""


class EncodeVerifyTask(task.Task):
    """
    Verify an encoded track against its pre-encode WAV.

    For lossless formats: decode back and CRC32-compare against the
    original WAV -- the direct generalization of what `flac --verify`
    gave us for FLAC specifically.

    For lossy formats: bit-exact comparison is impossible by design, so
    this instead checks that decoding succeeds and that the decoded
    sample count is within a codec-specific tolerance of the source (see
    _LOSSY_FRAME_TOLERANCE) -- a fundamentally weaker guarantee than
    lossless verify, never presented as equivalent.
    """

    description = 'Verifying encoded track'

    # Empirically measured ffmpeg encoder priming/resampling deltas (see
    # whipsaw/test/test_program_ffmpeg.py). Opus always resamples to/from
    # 48kHz internally (it has no native 44.1kHz mode), which needs much
    # more slack than the encoder-delay-only formats.
    _LOSSY_FRAME_TOLERANCE = {
        'mp3': 200,
        'aac': 200,
        'vorbis': 200,
        'opus': 2000,
    }
    _DEFAULT_LOSSY_TOLERANCE = 200

    checksum = None  # set on success, for lossless formats only

    def __init__(self, wav_path, encoded_path, format_name):
        self.wav_path = wav_path
        self.encoded_path = encoded_path
        self.format_name = format_name

    def start(self, runner):
        task.Task.start(self, runner)
        self.schedule(0.0, self._verify)

    def _verify(self):
        profile = ffmpeg.CODEC_PROFILES[self.format_name]
        fd, tmp_wav = tempfile.mkstemp(suffix='.verify.wav')
        os.close(fd)
        try:
            try:
                ffmpeg.decode_to_wav(self.encoded_path, tmp_wav)
            except ffmpeg.DecodeError as e:
                self.setAndRaiseException(EncodeVerificationError(str(e)))
                self.stop()
                return

            if profile['lossless']:
                self._verify_lossless(tmp_wav)
            else:
                self._verify_lossy(tmp_wav)
        finally:
            os.unlink(tmp_wav)

        self.stop()

    def _verify_lossless(self, decoded_wav_path):
        orig_crc = checksum.crc32_of_wav(self.wav_path)
        decoded_crc = checksum.crc32_of_wav(decoded_wav_path)
        self.checksum = decoded_crc
        if orig_crc != decoded_crc:
            self.setAndRaiseException(EncodeVerificationError(
                'decoded %s does not match source (lossless encode '
                'should be bit-exact)' % self.format_name))

    def _verify_lossy(self, decoded_wav_path):
        orig_frames = _wav_frame_count(self.wav_path)
        decoded_frames = _wav_frame_count(decoded_wav_path)
        tolerance = self._LOSSY_FRAME_TOLERANCE.get(
            self.format_name, self._DEFAULT_LOSSY_TOLERANCE)
        delta = abs(decoded_frames - orig_frames)
        if delta > tolerance:
            self.setAndRaiseException(EncodeVerificationError(
                'decoded %s frame count %d differs from source %d by '
                '%d frames, more than the %d-frame tolerance' % (
                    self.format_name, decoded_frames, orig_frames,
                    delta, tolerance)))


def _wav_frame_count(path):
    with wave.open(path) as w:
        return w.getnframes()


class TaggingTask(task.Task):
    # TODO: Wizzup: Do we really want this as 'Task'...?
    # I only made it a task for now because that it's easier to integrate in
    # program/cdparanoia.py - where whipsaw currently does the tagging.
    # We should just move the tagging to a more sensible place.

    description = 'Writing tags'

    def __init__(self, track_path, track_tags, format_name):
        self.track_path = track_path
        self.tags = track_tags
        self.format_name = format_name

    def start(self, runner):
        task.Task.start(self, runner)
        self.schedule(0.0, self._tag)

    def _tag(self):
        writer = tags.get_tag_writer(self.format_name)
        writer.write(self.track_path, self.tags)
        self.stop()


class EmbedPictureTask(task.Task):
    description = 'Embedding cover art'

    def __init__(self, track_path, cover_art_path, format_name):
        self.track_path = track_path
        self.cover_art_path = cover_art_path
        self.format_name = format_name

    def start(self, runner):
        task.Task.start(self, runner)
        self.schedule(0.0, self._embed_picture)

    @staticmethod
    def _prepare_picture(cover_art_path):
        """
        Read a cover art file into a tags.PreparedPicture.

        cover_art_path always comes from Program.getCoverArt(), which
        already validated/normalized the image (re-encoded to a clean
        JPEG or PNG, size-bounded) before writing it to disk -- so this
        just needs to read it back and grab its mime type/dimensions, not
        re-validate format/mode the way whipsaw used to when embedding
        could be handed an arbitrary, unvalidated file.
        """
        if not cover_art_path:
            return None

        from PIL import Image

        with Image.open(cover_art_path) as im:
            mime_type = 'image/png' if im.format == 'PNG' else 'image/jpeg'
            width, height = im.size

        with open(cover_art_path, 'rb') as f:
            data = f.read()

        return tags.PreparedPicture(data, mime_type, width, height)

    def _embed_picture(self):
        picture = self._prepare_picture(self.cover_art_path)
        if picture:
            writer = tags.get_tag_writer(self.format_name)
            try:
                writer.embed_picture_and_verify(self.track_path, picture)
            except PictureEmbedVerificationError as e:
                self.setAndRaiseException(e)

        self.stop()
