# -*- Mode: Python; test-case-name: whipper.test.test_common_tags -*-
# vi:si:et:sw=4:sts=4:ts=4

"""
Format-agnostic tag and cover-art writing.

whipper's internal tag dict (built by Program.getTagList()) uses Vorbis
comment-style keys (ARTIST, MUSICBRAINZ_DISCID, ...) since FLAC was the
only output format that ever existed. mutagen's tag scheme differs per
container, so writing the same dict to MP3/WAV (ID3) or ALAC/AAC (MP4
atoms) needs an explicit mapping -- that's what TagWriter subclasses do.
FLAC/Ogg Opus/Ogg Vorbis all use real Vorbis comments already and need no
mapping at all.
"""

import base64

from mutagen.flac import FLAC, Picture
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm
from mutagen.id3 import (
    PictureType, TALB, TCOM, TDRC, TIT2, TPE1, TPE2, TPOS, TRCK, TSRC,
    TXXX, APIC,
)

import logging
logger = logging.getLogger(__name__)


class PictureEmbedVerificationError(Exception):
    """
    Raised when a picture was supposedly embedded but isn't actually
    present when the track file is re-opened with a fresh mutagen object.

    Historically, whipper called FLAC.add_picture() without ever calling
    FLAC.save() (fixed in PR #610, but never in a released version), so
    --cover-art embed/complete silently did nothing on every version
    anyone would actually pip install. Checking the in-memory Picture
    object never would have caught that; only reopening the file does --
    so embed_picture_and_verify() applies that check uniformly across
    every container, not just FLAC.
    """


class PreparedPicture:
    """A cover image ready to embed: raw bytes plus what each writer needs."""

    def __init__(self, data, mime_type, width=None, height=None):
        self.data = data
        self.mime_type = mime_type
        self.width = width
        self.height = height


def _mp4_freeform_key(name):
    return '----:com.apple.iTunes:%s' % name


class TagWriter:
    """Base class: subclasses implement write()/embed_picture()/has_picture."""

    def write(self, path, tags):
        """Write `tags` (whipper's internal Vorbis-style dict) to `path`."""
        raise NotImplementedError

    def embed_picture(self, path, picture):
        """:param picture: a PreparedPicture"""
        raise NotImplementedError

    def has_picture(self, path):
        """:returns: True if `path` has an embedded cover picture."""
        raise NotImplementedError

    def embed_picture_and_verify(self, path, picture):
        """
        Embed `picture` into `path`, then reopen the file with a fresh
        mutagen object and confirm it actually persisted. See
        PictureEmbedVerificationError's docstring for why this matters.
        """
        self.embed_picture(path, picture)
        if not self.has_picture(path):
            raise PictureEmbedVerificationError(
                'picture was not found in %r after embedding' % path)


class VorbisCommentTagWriter(TagWriter):
    """FLAC, Ogg Opus, Ogg Vorbis: all real Vorbis comments already."""

    _MUTAGEN_CLASSES = {
        'flac': FLAC,
        'ogg_opus': OggOpus,
        'ogg_vorbis': OggVorbis,
    }

    def __init__(self, container):
        self._cls = self._MUTAGEN_CLASSES[container]
        self._is_native_flac = container == 'flac'

    def write(self, path, tags):
        w = self._cls(path)
        for key, value in tags.items():
            w[key] = value
        w.save()

    def embed_picture(self, path, picture):
        w = self._cls(path)
        pic = Picture()
        pic.data = picture.data
        pic.type = PictureType.COVER_FRONT
        pic.mime = picture.mime_type
        if picture.width and picture.height:
            pic.width, pic.height = picture.width, picture.height

        if self._is_native_flac:
            w.add_picture(pic)
        else:
            # Ogg containers have no native picture block; embed the same
            # FLAC Picture structure, base64-encoded, as a Vorbis comment
            # -- the de facto standard convention (also used by Picard).
            block = base64.b64encode(pic.write()).decode('ascii')
            w['METADATA_BLOCK_PICTURE'] = [block]
        w.save()

    def has_picture(self, path):
        w = self._cls(path)
        if self._is_native_flac:
            return len(w.pictures) > 0
        return bool(w.get('METADATA_BLOCK_PICTURE'))


# whipper's internal key -> ID3 frame class, for the tags with a direct
# one-value-per-frame equivalent. TRACKNUMBER/TRACKTOTAL and DISCNUMBER/
# DISCTOTAL are combined into single TRCK/TPOS frames instead (handled
# separately in ID3TagWriter.write()), and everything else not listed here
# falls through to a freeform TXXX:<key> frame.
_ID3_SIMPLE_FRAMES = {
    'ARTIST': TPE1,
    'ALBUMARTIST': TPE2,
    'TITLE': TIT2,
    'ALBUM': TALB,
    'DATE': TDRC,
    'COMPOSER': TCOM,
}
_ID3_HANDLED_KEYS = set(_ID3_SIMPLE_FRAMES) | {
    'TRACKNUMBER', 'TRACKTOTAL', 'DISCNUMBER', 'DISCTOTAL', 'ISRC',
}


class ID3TagWriter(TagWriter):
    """MP3, WAV."""

    _MUTAGEN_CLASSES = {'mp3': MP3, 'wav': WAVE}

    def __init__(self, container):
        self._cls = self._MUTAGEN_CLASSES[container]

    def _open_with_tags(self, path):
        w = self._cls(path)
        if w.tags is None:
            w.add_tags()
        return w

    def write(self, path, tags):
        w = self._open_with_tags(path)
        id3 = w.tags

        track_number = tags.get('TRACKNUMBER')
        if track_number:
            track_total = tags.get('TRACKTOTAL')
            text = ('%s/%s' % (track_number, track_total) if track_total
                    else str(track_number))
            id3.add(TRCK(encoding=3, text=[text]))

        disc_number = tags.get('DISCNUMBER')
        if disc_number:
            disc_total = tags.get('DISCTOTAL')
            text = ('%s/%s' % (disc_number, disc_total) if disc_total
                    else str(disc_number))
            id3.add(TPOS(encoding=3, text=[text]))

        if 'ISRC' in tags:
            id3.add(TSRC(encoding=3, text=[tags['ISRC']]))

        for key, frame_cls in _ID3_SIMPLE_FRAMES.items():
            if key in tags:
                value = tags[key]
                text = value if isinstance(value, list) else [value]
                id3.add(frame_cls(encoding=3, text=text))

        for key, value in tags.items():
            if key in _ID3_HANDLED_KEYS:
                continue
            text = value if isinstance(value, list) else [value]
            id3.add(TXXX(encoding=3, desc=key, text=text))

        w.save()

    def embed_picture(self, path, picture):
        w = self._open_with_tags(path)
        w.tags.add(APIC(encoding=3, mime=picture.mime_type,
                        type=PictureType.COVER_FRONT, desc='cover',
                        data=picture.data))
        w.save()

    def has_picture(self, path):
        w = self._cls(path)
        if w.tags is None:
            return False
        return len(w.tags.getall('APIC')) > 0


# whipper's internal key -> MP4 atom name, for the tags with a direct
# equivalent. trkn/disk are combined int-tuple atoms (handled separately
# in MP4TagWriter.write()); anything else falls through to a freeform
# '----:com.apple.iTunes:<key>' atom.
_MP4_SIMPLE_ATOMS = {
    'ARTIST': '\xa9ART',
    'ALBUMARTIST': 'aART',
    'TITLE': '\xa9nam',
    'ALBUM': '\xa9alb',
    'DATE': '\xa9day',
    'COMPOSER': '\xa9wrt',
}
_MP4_HANDLED_KEYS = set(_MP4_SIMPLE_ATOMS) | {
    'TRACKNUMBER', 'TRACKTOTAL', 'DISCNUMBER', 'DISCTOTAL',
}


class MP4TagWriter(TagWriter):
    """ALAC, AAC (both muxed into an MP4/M4A container)."""

    def write(self, path, tags):
        w = MP4(path)

        for key, atom in _MP4_SIMPLE_ATOMS.items():
            if key in tags:
                value = tags[key]
                w[atom] = value if isinstance(value, list) else [value]

        track_number = tags.get('TRACKNUMBER')
        if track_number:
            w['trkn'] = [(int(track_number),
                         int(tags.get('TRACKTOTAL') or 0))]

        disc_number = tags.get('DISCNUMBER')
        if disc_number:
            w['disk'] = [(int(disc_number),
                         int(tags.get('DISCTOTAL') or 0))]

        for key, value in tags.items():
            if key in _MP4_HANDLED_KEYS:
                continue
            values = value if isinstance(value, list) else [value]
            w[_mp4_freeform_key(key)] = [
                MP4FreeForm(v.encode('utf-8')) for v in values]

        w.save()

    def embed_picture(self, path, picture):
        w = MP4(path)
        image_format = (MP4Cover.FORMAT_PNG if picture.mime_type == 'image/png'
                        else MP4Cover.FORMAT_JPEG)
        w['covr'] = [MP4Cover(picture.data, imageformat=image_format)]
        w.save()

    def has_picture(self, path):
        w = MP4(path)
        return len(w.get('covr', [])) > 0


_CONTAINER_TO_WRITER = {
    'flac': lambda: VorbisCommentTagWriter('flac'),
    'ogg_opus': lambda: VorbisCommentTagWriter('ogg_opus'),
    'ogg_vorbis': lambda: VorbisCommentTagWriter('ogg_vorbis'),
    'mp3': lambda: ID3TagWriter('mp3'),
    'wav': lambda: ID3TagWriter('wav'),
    'mp4': MP4TagWriter,
}

# maps whipper.program.ffmpeg format names to the tag-container names
# above -- distinct from ffmpeg's own -f muxer name, since opus and vorbis
# both mux into 'ogg' but need different mutagen classes, and alac and aac
# both mux into 'mp4' but share one MP4-atom-based writer.
_FORMAT_TO_TAG_CONTAINER = {
    'flac': 'flac',
    'wav': 'wav',
    'alac': 'mp4',
    'aac': 'mp4',
    'mp3': 'mp3',
    'opus': 'ogg_opus',
    'vorbis': 'ogg_vorbis',
}


def get_tag_writer(format_name):
    """
    :param format_name: a whipper.program.ffmpeg.CODEC_PROFILES key
    :returns: a TagWriter instance for that format's container
    :raises KeyError: if format_name isn't known
    """
    container = _FORMAT_TO_TAG_CONTAINER[format_name]
    return _CONTAINER_TO_WRITER[container]()
