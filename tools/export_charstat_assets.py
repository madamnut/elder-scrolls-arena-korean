#!/usr/bin/env python3
"""Export the original pre-drawn character-stat IMG assets as actual-size PNGs."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from arena_img import decode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("palette_col", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    palette_data = args.palette_col.read_bytes()
    if len(palette_data) != 776:
        raise ValueError(f"expected 776-byte CHARSHT.COL, got {len(palette_data)}")
    # Unlike embedded Arena IMG palettes, CHARSHT.COL already stores 8-bit
    # RGB components. Scaling it as a VGA 0..63 palette destroys its colors.
    palette = palette_data[8:]

    args.output.mkdir(parents=True, exist_ok=True)
    for name in ("CHARSTAT.IMG", "BONUS.IMG"):
        source = decode(args.source / name)
        image = Image.frombytes("P", (source.width, source.height), source.pixels)
        image.putpalette(palette)
        output = args.output / f"{Path(name).stem}-original-{source.width}x{source.height}.png"
        image.save(output)
        print(f"{name}: {source.width}x{source.height} -> {output}")

    updown_data = (args.source / "UPDOWN.IMG").read_bytes()
    if len(updown_data) != 8 * 16:
        raise ValueError(f"expected raw 8x16 UPDOWN.IMG, got {len(updown_data)} bytes")
    updown = Image.frombytes("P", (8, 16), updown_data)
    updown.putpalette(palette)
    updown_output = args.output / "UPDOWN-original-8x16.png"
    updown.save(updown_output)
    print(f"UPDOWN.IMG: raw 8x16 -> {updown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
