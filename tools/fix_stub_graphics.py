#!/usr/bin/env python3
"""Replace stub Graphics.png files (<200 bytes) with valid 64×64 transparent RGBA PNGs."""

import struct
import zlib
import os
import sys
import argparse

STUB_MAX_SIZE = 200
PNG_WIDTH = 64
PNG_HEIGHT = 64

def make_transparent_png(width: int, height: int) -> bytes:
    """Generate a valid PNG: width×height, RGBA, all pixels (0,0,0,0)."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    # IHDR
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)

    # IDAT: each row = 1 filter byte (0) + width*4 RGBA bytes
    row = b"\x00" + b"\x00\x00\x00\x00" * width
    raw = row * height
    idat = zlib.compress(raw, 9)

    # IEND
    iend = b""

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", iend)
    )

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("content_dir", help="Path to content/ directory")
    parser.add_argument("--dry-run", action="store_true", help="Report but don't modify")
    args = parser.parse_args()

    replacement = make_transparent_png(PNG_WIDTH, PNG_HEIGHT)
    stubs = []

    for root, _, files in os.walk(args.content_dir):
        for name in files:
            if name == "Graphics.png":
                path = os.path.join(root, name)
                if os.path.getsize(path) < STUB_MAX_SIZE:
                    stubs.append(path)

    stubs.sort()
    print(f"Found {len(stubs)} stub Graphics.png files (<{STUB_MAX_SIZE} bytes)")

    if args.dry_run:
        for s in stubs:
            print(f"  STUB: {s} ({os.path.getsize(s)} bytes)")
        return

    for s in stubs:
        old_size = os.path.getsize(s)
        with open(s, "wb") as f:
            f.write(replacement)
        print(f"  FIXED: {s} ({old_size} -> {len(replacement)} bytes)")

    print(f"Replaced {len(stubs)} stubs with {PNG_WIDTH}x{PNG_HEIGHT} transparent RGBA PNGs")

if __name__ == "__main__":
    main()
