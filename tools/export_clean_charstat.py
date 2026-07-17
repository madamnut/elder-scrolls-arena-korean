#!/usr/bin/env python3
"""Export text-free, actual-size character-stat UI PNGs."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from arena_img import decode
from localize_charstat import erase_text


TEXT_INDEX = 253
CHARSTAT_TEXT_RECTS = (
    (5, 49, 160, 115),
    (0, 125, 45, 175),
    (15, 180, 36, 190),
)
BONUS_TEXT_RECTS = ((3, 3, 52, 13),)


def clean(source_path: Path, rects: tuple[tuple[int, int, int, int], ...]) -> tuple[object, bytes]:
    source = decode(source_path)
    pixels = bytearray(source.pixels)
    erase_text(pixels, source.width, source.height, rects)
    return source, bytes(pixels)


def save_indexed_png(source: object, pixels: bytes, palette: bytes, output: Path) -> None:
    image = Image.frombytes("P", (source.width, source.height), pixels)
    image.putpalette(palette)
    image.save(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="글자가 없는 캐릭터 능력치 UI 이미지 생성")
    parser.add_argument("--charstat", type=Path, required=True)
    parser.add_argument("--bonus", type=Path, required=True)
    parser.add_argument("--palette", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    palette_data = args.palette.read_bytes()
    if len(palette_data) != 776:
        raise ValueError(f"CHARSHT.COL 크기가 올바르지 않습니다: {len(palette_data)}")
    palette = palette_data[8:]

    charstat, charstat_pixels = clean(args.charstat, CHARSTAT_TEXT_RECTS)
    bonus, bonus_pixels = clean(args.bonus, BONUS_TEXT_RECTS)
    args.output.mkdir(parents=True, exist_ok=True)
    charstat_output = args.output / "CHARSTAT-clean-171x200.png"
    bonus_output = args.output / "BONUS-clean-77x16.png"
    save_indexed_png(charstat, charstat_pixels, palette, charstat_output)
    save_indexed_png(bonus, bonus_pixels, palette, bonus_output)
    print(f"wrote: {charstat_output}")
    print(f"wrote: {bonus_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
