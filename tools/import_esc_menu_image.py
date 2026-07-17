#!/usr/bin/env python3
"""Import a finished 320x147 PNG as Arena's OP.IMG escape menu."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from arena_img import ArenaIMG, decode, encode_uncompressed


EXPECTED_SIZE = (320, 147)


def load_palette(path: Path) -> list[tuple[int, int, int]]:
    data = path.read_bytes()
    if len(data) != 776:
        raise ValueError(f"PAL.COL 크기가 올바르지 않습니다: {len(data)}")
    raw = data[8:]
    return [tuple(raw[index : index + 3]) for index in range(0, 768, 3)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--png", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--palette", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()

    rgba = Image.open(args.png).convert("RGBA")
    if rgba.size != EXPECTED_SIZE:
        raise ValueError(f"완성 PNG 크기 오류: {rgba.size} != {EXPECTED_SIZE}")
    if rgba.getextrema()[3] != (255, 255):
        raise ValueError("완성 PNG에는 투명 픽셀이 없어야 합니다.")

    source = decode(args.source)
    if (source.width, source.height) != EXPECTED_SIZE or source.palette is not None:
        raise ValueError("원본 OP.IMG는 팔레트 없는 320x147 이미지여야 합니다.")

    palette = load_palette(args.palette)
    palette_image = Image.new("P", (1, 1))
    palette_image.putpalette([component for color in palette for component in color])
    indexed = rgba.convert("RGB").quantize(
        palette=palette_image,
        dither=Image.Dither.NONE,
    )

    pixels = indexed.tobytes()
    result = ArenaIMG(
        source.x,
        source.y,
        source.width,
        source.height,
        source.palette,
        pixels,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encode_uncompressed(result, pixels, args.output)
    if decode(args.output) != result:
        raise ValueError("OP.IMG 저장 후 왕복 검증에 실패했습니다.")

    if args.preview is not None:
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        indexed.save(args.preview)

    print(f"wrote: {args.output}")
    print(f"header: ({source.x},{source.y}) {source.width}x{source.height}")
    print(f"palette: {args.palette}")
    if args.preview is not None:
        print(f"preview: {args.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
