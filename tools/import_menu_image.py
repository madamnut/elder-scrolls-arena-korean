#!/usr/bin/env python3
"""Import one finished 320x200 PNG as Arena's MENU.IMG."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from arena_flc import decode as decode_flc
from arena_img import decode as decode_img, encode_uncompressed, palette_8bit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("png", type=Path)
    parser.add_argument("original_img", type=Path)
    parser.add_argument("palette_flc", type=Path)
    parser.add_argument("output_img", type=Path)
    parser.add_argument("preview_png", type=Path)
    args = parser.parse_args()

    edited = Image.open(args.png).convert("RGB")
    if edited.size != (320, 200):
        raise ValueError(f"MENU PNG must be 320x200, got {edited.size}")

    original = decode_img(args.original_img)
    if original.palette is not None:
        scaled = palette_8bit(original.palette)
        palette = [tuple(scaled[index : index + 3]) for index in range(0, 768, 3)]
    else:
        palette = decode_flc(args.palette_flc).frames[-1].palette
    palette_image = Image.new("P", (1, 1))
    palette_image.putpalette([component for color in palette for component in color])
    indexed = edited.quantize(palette=palette_image, dither=Image.Dither.NONE)

    args.output_img.parent.mkdir(parents=True, exist_ok=True)
    args.preview_png.parent.mkdir(parents=True, exist_ok=True)
    encode_uncompressed(original, indexed.tobytes(), args.output_img)
    indexed.save(args.preview_png)
    print(f"wrote: {args.output_img}")
    print(f"preview: {args.preview_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
