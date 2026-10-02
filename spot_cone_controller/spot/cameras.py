"""Spot image sources. Only the selected camera is fetched."""

import struct
import zlib
from functools import lru_cache


@lru_cache(maxsize=8)
def encode_solid_png(width, height, red, green, blue):
    """Small compressed PNG used for mock views and camera failures."""
    row = b"\x00" + bytes((red, green, blue)) * width
    raw = row * height
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            _chunk(b"IDAT", zlib.compress(raw, 9)),
            _chunk(b"IEND", b""),
        ]
    )


def _chunk(tag, data):
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


class SpotCameras:
    def __init__(self, image_client, width, height):
        self.client = image_client
        self.width = int(width)
        self.height = int(height)

    def list_sources(self):
        if self.client is None:
            return []
        sources = []
        for item in self.client.list_image_sources():
            name = item if isinstance(item, str) else getattr(item, "name", "")
            if name:
                sources.append(str(name))
        return sources

    def fetch(self, source_name):
        if self.client is None or not source_name:
            return None
        data = self._fetch_jpeg(source_name)
        if data and data[:2] == b"\xff\xd8":
            return data
        return None

    def _fetch_jpeg(self, source_name):
        from bosdyn.api import image_pb2
        from bosdyn.client.image import build_image_request

        try:
            request = build_image_request(
                source_name,
                quality_percent=40,
                pixel_format=image_pb2.Image.PIXEL_FORMAT_JPEG,
            )
        except TypeError:
            request = build_image_request(source_name, quality_percent=40)
        responses = self.client.get_image([request])
        if not responses:
            return None
        return responses[0].shot.image.data
