#!/usr/bin/env python3
"""Import artist-finished CHARSTAT/BONUS PNGs without palette conversion loss."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from arena_img import ArenaIMG, decode, encode_uncompressed, write_png


def indexed_pixels(path: Path, size: tuple[int, int], palette: list[tuple[int, int, int]]) -> bytes:
    image = Image.open(path).convert("RGBA")
    if image.size != size:
        raise ValueError(f"{path.name} 크기 오류: {image.size} != {size}")
    lookup = {color: index for index, color in enumerate(palette)}
    output = bytearray()
    for red, green, blue, alpha in image.getdata():
        if alpha != 255:
            raise ValueError(f"{path.name}에는 투명 픽셀이 없어야 합니다.")
        color = (red, green, blue)
        if color not in lookup:
            raise ValueError(f"{path.name}의 색상이 CHARSHT.COL에 없습니다: {color}")
        output.append(lookup[color])
    return bytes(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="완성된 능력치 창 PNG를 Arena IMG로 변환")
    parser.add_argument("--charstat-png", type=Path, required=True)
    parser.add_argument("--bonus-png", type=Path, required=True)
    parser.add_argument("--charstat-source", type=Path, required=True)
    parser.add_argument("--bonus-source", type=Path, required=True)
    parser.add_argument("--palette", type=Path, required=True)
    parser.add_argument("--bonus-x", type=int, default=62)
    parser.add_argument("--bonus-y", type=int, default=119)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    palette_data = args.palette.read_bytes()
    if len(palette_data) != 776:
        raise ValueError(f"CHARSHT.COL 크기가 올바르지 않습니다: {len(palette_data)}")
    raw_palette = palette_data[8:]
    palette = [tuple(raw_palette[index : index + 3]) for index in range(0, 768, 3)]

    charstat_source = decode(args.charstat_source)
    bonus_source = decode(args.bonus_source)
    charstat_pixels = indexed_pixels(
        args.charstat_png, (charstat_source.width, charstat_source.height), palette
    )
    bonus_pixels = indexed_pixels(
        args.bonus_png, (bonus_source.width, bonus_source.height), palette
    )

    charstat = ArenaIMG(
        charstat_source.x,
        charstat_source.y,
        charstat_source.width,
        charstat_source.height,
        charstat_source.palette,
        charstat_pixels,
    )
    bonus = ArenaIMG(
        args.bonus_x,
        args.bonus_y,
        bonus_source.width,
        bonus_source.height,
        bonus_source.palette,
        bonus_pixels,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    encode_uncompressed(charstat, charstat_pixels, args.output / "CHARSTAT.IMG")
    encode_uncompressed(bonus, bonus_pixels, args.output / "BONUS.IMG")
    write_png(charstat, args.output / "CHARSTAT-preview-171x200.png", palette)
    write_png(bonus, args.output / "BONUS-preview-77x16.png", palette)
    print(f"wrote: {args.output}")
    print(f"BONUS position: ({args.bonus_x}, {args.bonus_y})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
