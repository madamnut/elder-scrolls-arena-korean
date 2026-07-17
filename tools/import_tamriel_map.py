#!/usr/bin/env python3
"""Import a localized TAMRIEL map while preserving its fixed-offset click masks."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct

from PIL import Image

from arena_img import decode, decode_type04, encode_type04, palette_8bit


HEADER = struct.Struct("<6H")
MASK_OFFSET = 0x87D5


def main() -> int:
    parser = argparse.ArgumentParser(description="TAMRIEL.MNU 지도 및 클릭 마스크 보존 변환")
    parser.add_argument("original", type=Path)
    parser.add_argument("clean_map", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()

    original_data = args.original.read_bytes()
    x, y, width, height, flags, packed_size = HEADER.unpack_from(original_data)
    if (x, y, width, height, flags, packed_size) != (0, 0, 320, 200, 0x0904, 33993):
        raise ValueError("지원하는 CD판 TAMRIEL.MNU 헤더와 다릅니다.")
    if HEADER.size + packed_size + 768 != MASK_OFFSET:
        raise ValueError("원본 클릭 마스크 시작점이 0x87D5가 아닙니다.")
    original = decode(args.original)
    if original.palette is None:
        raise ValueError("TAMRIEL.MNU 내장 팔레트가 없습니다.")

    base = Image.open(args.clean_map).convert("RGBA").resize((320, 200), Image.Resampling.BILINEAR)
    labels = Image.open(args.labels).convert("RGBA")
    if labels.size != (320, 200):
        raise ValueError(f"지역명 레이아웃이 320×200이 아닙니다: {labels.size}")
    base.alpha_composite(labels)
    rgb = Image.new("RGB", base.size, (0, 0, 0))
    rgb.paste(base, mask=base.getchannel("A"))

    palette_image = Image.new("P", (1, 1))
    palette_image.putpalette(palette_8bit(original.palette))
    indexed = rgb.quantize(palette=palette_image, dither=Image.Dither.NONE)
    pixels = indexed.tobytes()
    packed = encode_type04(pixels, target_size=packed_size)
    if decode_type04(packed, width * height) != pixels:
        raise ValueError("type-4 압축 왕복 검증에 실패했습니다.")

    header = HEADER.pack(x, y, width, height, flags, packed_size)
    palette = original_data[HEADER.size + packed_size : MASK_OFFSET]
    masks = original_data[MASK_OFFSET:]
    output_data = header + packed + palette + masks
    if len(output_data) != len(original_data) or output_data[MASK_OFFSET:] != masks:
        raise ValueError("클릭 마스크 보존 검증에 실패했습니다.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output_data)
    if args.preview is not None:
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        indexed.save(args.preview)
    print(f"wrote: {args.output}")
    print(f"type-4 bytes: {len(packed)}/{packed_size}")
    print(f"click masks preserved: {len(masks)} bytes at 0x{MASK_OFFSET:X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
