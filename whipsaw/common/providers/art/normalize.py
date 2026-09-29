# -*- Mode: Python; test-case-name: whipsaw.test.test_common_providers_art -*-
# vi:si:et:sw=4:sts=4:ts=4

"""
Validate and normalize a fetched ArtResult before it's saved/embedded.

Runs once, after a provider chain returns a winner, rather than per
provider: keeps provider modules simple (just "fetch bytes + mime"), keeps
this logic in exactly one place, and makes it trivial to test independently
of any network provider.
"""

import io

from PIL import Image

import logging
logger = logging.getLogger(__name__)


class NormalizedArt:
    """A validated, re-encoded, size-bounded image ready to save/embed."""

    def __init__(self, data, mime_type, extension):
        self.data = data
        self.mime_type = mime_type
        self.extension = extension


def normalize(art_result, max_dimension, output_format='jpeg'):
    """
    :param art_result: a whipsaw.common.providers.art.base.ArtResult
    :param max_dimension: downscale so neither side exceeds this, in pixels
    :param output_format: 'jpeg' or 'png', the default re-encode target
    :returns: a NormalizedArt, or None if the fetched data isn't decodable
              as an image at all.
    """
    try:
        im = Image.open(io.BytesIO(art_result.data))
        im.load()
    except Exception as e:
        logger.warning('%s: fetched data is not a decodable image (%s)',
                       art_result.source, e)
        return None

    # a PNG with real transparency is kept as PNG rather than flattened
    # onto a JPEG background, which would silently mangle it
    if _has_transparency(im):
        target_format = 'PNG'
    else:
        target_format = output_format.upper()

    if target_format == 'JPEG' and im.mode not in ('RGB', 'L'):
        im = im.convert('RGB')

    if max(im.size) > max_dimension:
        im.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

    buf = io.BytesIO()
    im.save(buf, format=target_format)

    if target_format == 'PNG':
        return NormalizedArt(buf.getvalue(), 'image/png', 'png')
    return NormalizedArt(buf.getvalue(), 'image/jpeg', 'jpg')


def _has_transparency(im):
    if im.mode == 'P':
        return 'transparency' in im.info
    return im.mode in ('RGBA', 'LA')
