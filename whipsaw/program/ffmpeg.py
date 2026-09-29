# -*- Mode: Python; test-case-name: whipsaw.test.test_program_ffmpeg -*-
# vi:si:et:sw=4:sts=4:ts=4

"""
ffmpeg-based multi-format audio encoding, replacing the old FLAC-only
whipsaw.program.flac (a plain subprocess wrapper around the standalone
`flac` CLI).

The `-f <container_format>` flag is passed explicitly on every ffmpeg
invocation here rather than relying on output-filename extensions: whipsaw
writes tracks to a `<path>.part` temp file during ripping, regardless of
final codec, so ffmpeg can't infer the container from the extension.
"""

import subprocess

import logging
logger = logging.getLogger(__name__)


# codec: the ffmpeg -c:a encoder name
# ext: the file extension the final track gets
# container_format: the ffmpeg -f muxer/demuxer name
# lossless: whether bit-exact PCM round-trip is expected (drives which
#           kind of check EncodeVerifyTask performs)
CODEC_PROFILES = {
    'flac': {
        'codec': 'flac', 'ext': 'flac',
        'container_format': 'flac', 'lossless': True,
    },
    'wav': {
        'codec': 'pcm_s16le', 'ext': 'wav',
        'container_format': 'wav', 'lossless': True,
    },
    'alac': {
        'codec': 'alac', 'ext': 'm4a',
        'container_format': 'mp4', 'lossless': True,
    },
    'mp3': {
        'codec': 'libmp3lame', 'ext': 'mp3',
        'container_format': 'mp3', 'lossless': False,
    },
    'opus': {
        'codec': 'libopus', 'ext': 'opus',
        'container_format': 'ogg', 'lossless': False,
    },
    'vorbis': {
        'codec': 'libvorbis', 'ext': 'ogg',
        'container_format': 'ogg', 'lossless': False,
    },
    'aac': {
        'codec': 'aac', 'ext': 'm4a',
        'container_format': 'mp4', 'lossless': False,
    },
}


class EncodeError(Exception):
    def __init__(self, format_name, stderr):
        self.format_name = format_name
        self.stderr = stderr
        super().__init__(
            'ffmpeg failed to encode to %s: %s' % (format_name, stderr))


class DecodeError(Exception):
    def __init__(self, path, stderr):
        self.path = path
        self.stderr = stderr
        super().__init__('ffmpeg failed to decode %r: %s' % (path, stderr))


_available_encoders = None


def _list_available_encoders():
    global _available_encoders
    if _available_encoders is None:
        try:
            out = subprocess.check_output(
                ['ffmpeg', '-hide_banner', '-encoders'],
                stderr=subprocess.STDOUT).decode('utf-8', errors='replace')
        except (OSError, subprocess.CalledProcessError) as e:
            logger.error('could not query ffmpeg encoders: %s', e)
            _available_encoders = set()
        else:
            # encoder listing lines look like " A....D flac  FLAC ..."
            names = set()
            for line in out.splitlines():
                fields = line.split()
                if line[:1] == ' ' and len(fields) >= 2:
                    names.add(fields[1])
            _available_encoders = names
    return _available_encoders


def check_encoder_available(format_name):
    """
    :returns: True if ffmpeg reports this format's encoder as available in
              the local ffmpeg build (some distro builds omit e.g.
              libfdk_aac for licensing reasons).
    :raises KeyError: if format_name isn't a known profile
    """
    codec = CODEC_PROFILES[format_name]['codec']
    return codec in _list_available_encoders()


def _quality_args(format_name, config):
    """Build the ffmpeg quality/bitrate args for format_name from config."""
    if config is None:
        return []
    if format_name == 'flac':
        return ['-compression_level',
                str(config.get_flac_compression_level())]
    if format_name == 'mp3':
        return ['-q:a', str(config.get_mp3_quality())]
    if format_name == 'opus':
        return ['-b:a', config.get_opus_bitrate()]
    if format_name == 'aac':
        return ['-b:a', config.get_aac_bitrate()]
    return []


def encode(infile, outfile, format_name, config=None):
    """
    Encode infile (a WAV) to outfile using the given format.

    :param config: a whipsaw.common.config.Config, consulted for
                   quality/bitrate settings; quality defaults are used if
                   omitted.
    :raises KeyError: if format_name isn't a known profile
    :raises EncodeError: if ffmpeg exits non-zero
    """
    profile = CODEC_PROFILES[format_name]
    argv = ['ffmpeg', '-y', '-loglevel', 'error', '-i', infile,
            '-map_metadata', '-1', '-c:a', profile['codec']]
    argv += _quality_args(format_name, config)
    argv += ['-f', profile['container_format'], outfile]

    result = subprocess.run(argv, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode != 0:
        stderr = result.stderr.decode('utf-8', errors='replace')
        logger.error('ffmpeg encode to %s failed: %s', format_name, stderr)
        raise EncodeError(format_name, stderr)


def decode_to_wav(infile, outfile):
    """
    Decode infile to 16-bit PCM WAV via ffmpeg.

    :raises DecodeError: if ffmpeg exits non-zero
    """
    argv = ['ffmpeg', '-y', '-loglevel', 'error', '-i', infile,
            '-c:a', 'pcm_s16le', '-f', 'wav', outfile]

    result = subprocess.run(argv, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode != 0:
        stderr = result.stderr.decode('utf-8', errors='replace')
        logger.error('ffmpeg decode of %r failed: %s', infile, stderr)
        raise DecodeError(infile, stderr)
