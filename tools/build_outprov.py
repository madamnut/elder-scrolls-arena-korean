#!/usr/bin/env python3
"""Build an uncompressed OUTPROV.CIF from localized highlight PNGs."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct

from PIL import Image

from render_region_labels import LABELS, OUTLINE_RGB, HIGHLIGHT_RGB


HEADER = struct.Struct("<6H")
TRANSPARENT_INDEX = 0
OUTLINE_INDEX = 206
HIGHLIGHT_INDEX = 20


def main() -> int:
    parser = argparse.ArgumentParser(description="한글 OUTPROV.CIF 생성")
    parser.add_argument("sprites", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    output = bytearray()
    for index, (slug, _text, x, y) in enumerate(LABELS):
        matches = list(args.sprites.glob(f"{index:02d}-{slug}-highlight-*.png"))
        if len(matches) != 1:
            raise ValueError(f"{slug}: 강조 PNG가 하나가 아닙니다: {matches}")
        image = Image.open(matches[0]).convert("RGBA")
        pixels = bytearray()
        for red, green, blue, alpha in image.getdata():
            if alpha < 128:
                pixels.append(TRANSPARENT_INDEX)
            elif (red, green, blue) == OUTLINE_RGB:
                pixels.append(OUTLINE_INDEX)
            elif (red, green, blue) == HIGHLIGHT_RGB:
                pixels.append(HIGHLIGHT_INDEX)
            else:
                raise ValueError(f"{slug}: 예상 밖 RGBA {(red, green, blue, alpha)}")
        output.extend(HEADER.pack(x, y, image.width, image.height, 0x0800, len(pixels)))
        output.extend(pixels)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    print(f"wrote 9 frames: {args.output} ({len(output)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
