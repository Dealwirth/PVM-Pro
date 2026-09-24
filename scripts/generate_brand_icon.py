"""Generate the PV Manager brand icon as a pure-stdlib PNG.

Usage: py scripts/generate_brand_icon.py
Creates brand/icon.png and custom_components/pv_manager/brand/icon.png.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

SIZE = 256


def _rounded_rect(x: float, y: float, w: float, h: float, radius: float) -> bool:
    if x < 0 or y < 0 or x > w or y > h:
        return False
    cx = min(max(x, radius), w - radius)
    cy = min(max(y, radius), h - radius)
    dx = x - cx
    dy = y - cy
    return dx * dx + dy * dy <= radius * radius


def build_pixels() -> bytearray:
    """Build RGBA pixels for the icon."""
    pixels = bytearray()
    for y in range(SIZE):
        pixels.append(0)  # PNG filter type: none
        for x in range(SIZE):
            u = x / SIZE
            v = y / SIZE
            if not _rounded_rect(u, v, 1.0, 1.0, 0.22):
                pixels.extend((0, 0, 0, 0))
                continue
            # Deep blue-green background gradient.
            r = int(12 + 24 * (1 - v))
            g = int(58 + 90 * (1 - v))
            b = int(92 + 110 * u)
            # Solar sun in the upper right.
            dx = u - 0.72
            dy = v - 0.28
            if dx * dx + dy * dy <= 0.16 * 0.16:
                r, g, b = 255, 196, 0
            # PV module: three blue panels with a bright diagonal.
            if 0.16 <= u <= 0.68 and 0.5 <= v <= 0.82:
                r, g, b = 26, 92, 168
                if (u + v) % 0.22 < 0.035:
                    r, g, b = 190, 226, 255
                if abs(v - 0.66) < 0.012 or abs(u - 0.42) < 0.012:
                    r, g, b = 12, 46, 92
            pixels.extend((r, g, b, 255))
    return pixels


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build one PNG chunk."""
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def build_png() -> bytes:
    """Return the complete PNG file as bytes."""
    raw = bytes(build_pixels())
    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(raw, 9))
        + png_chunk(b"IEND", b"")
    )


def main() -> None:
    """Write the icon to both documented locations."""
    data = build_png()
    root = Path(__file__).resolve().parent.parent
    targets = [
        root / "brand" / "icon.png",
        root / "custom_components" / "pv_manager" / "brand" / "icon.png",
    ]
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f"wrote {target.relative_to(root)} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
