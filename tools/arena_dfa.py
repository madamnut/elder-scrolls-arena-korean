#!/usr/bin/env python3
"""Decode TES Arena DFA animation frames for analysis."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct

from PIL import Image


def decode_rle(data: bytes, output_size: int) -> bytes:
    source = 0
    output = bytearray()
    while len(output) < output_size:
        sample = data[source]
        source += 1
        if sample & 0x80:
            value = data[source]
            source += 1
            output.extend(bytes((value,)) * (sample - 0x7F))
        else:
            count = sample + 1
            output.extend(data[source : source + count])
            source += count
    return bytes(output[:output_size])


def decode(path: Path) -> tuple[int, int, list[bytes]]:
    data = path.read_bytes()
    count, _, _, width, height, packed_size = struct.unpack_from("<6H", data)
    first = decode_rle(data[12 : 12 + packed_size], width * height)
    frames = [first]
    offset = 12 + packed_size
    for _ in range(1, count):
        frame = bytearray(first)
        _, chunk_count = struct.unpack_from("<2H", data, offset)
        offset += 4
        for _ in range(chunk_count):
            update_offset, update_count = struct.unpack_from("<2H", data, offset)
            offset += 4
            frame[update_offset : update_offset + update_count] = data[offset : offset + update_count]
            offset += update_count
        frames.append(bytes(frame))
    return width, height, frames


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--palette-png", type=Path, required=True)
    args = parser.parse_args()
    width, height, frames = decode(args.input)
    palette = Image.open(args.palette_png).getpalette()
    args.output.mkdir(parents=True, exist_ok=True)
    for index, pixels in enumerate(frames):
        image = Image.frombytes("P", (width, height), pixels)
        image.putpalette(palette)
        image.save(args.output / f"frame-{index:02d}.png")
    print(f"{args.input.name}: {len(frames)} frames, {width}x{height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
