#!/usr/bin/env python3
"""Localize Arena's fixed character-stat labels with the native HANGUL9 bank."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct

from PIL import Image

from arena_img import ArenaIMG, decode, encode_uncompressed, write_png


GLYPH_BYTES = 32
HANGUL_BASE = 0xAC00
GLYPH_WIDTH = 9
GLYPH_HEIGHT = 9
TEXT_INDEX = 253

PRIMARY_LABELS = (
    ("힘", 10, 38),
    ("지", 10, 48),
    ("의", 10, 58),
    ("민", 10, 68),
    ("속", 10, 78),
    ("체", 10, 88),
    ("매", 10, 98),
    ("운", 10, 108),
)

DERIVED_LABELS = (
    ("피해", 52, 47),
    ("주문", 52, 57),
    ("마방", 52, 67),
    ("명중", 52, 77),
    ("체력", 52, 90),
    ("매력", 52, 100),
    ("중량", 112, 47),
    ("방어", 112, 77),
    ("회복", 112, 90),
)

STATUS_LABELS = (
    ("체력", 18, 124),
    ("피로", 18, 134),
    ("골드", 18, 144),
    ("경험치", 3, 158),
    ("레벨", 22, 167),
    ("완료", 18, 182),
)


def glyph_rows(font_data: bytes, char: str) -> tuple[int, ...]:
    index = ord(char) - HANGUL_BASE
    if not 0 <= index < 11172:
        raise ValueError(f"HANGUL9로 그릴 수 없는 문자: {char!r}")
    start = index * GLYPH_BYTES
    return struct.unpack_from("<16H", font_data, start)[:GLYPH_HEIGHT]


def erase_text(pixels: bytearray, width: int, height: int, rects: tuple[tuple[int, int, int, int], ...]) -> None:
    mask = bytearray(width * height)
    for left, top, right, bottom in rects:
        for y in range(max(0, top), min(height, bottom)):
            for x in range(max(0, left), min(width, right)):
                index = (y * width) + x
                if pixels[index] == TEXT_INDEX:
                    mask[index] = 1

    unresolved = sum(mask)
    while unresolved:
        changed: list[tuple[int, int]] = []
        for index, value in enumerate(mask):
            if not value:
                continue
            x = index % width
            y = index // width
            neighbors: list[int] = []
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    nindex = (ny * width) + nx
                    if not mask[nindex]:
                        neighbors.append(pixels[nindex])
            if neighbors:
                # The stone texture uses a narrow ordered palette ramp; the
                # median neighbor keeps the repair deterministic and local.
                neighbors.sort()
                changed.append((index, neighbors[len(neighbors) // 2]))
        if not changed:
            raise ValueError("영문 글자 마스크를 복원할 수 없습니다.")
        for index, value in changed:
            pixels[index] = value
            mask[index] = 0
        unresolved -= len(changed)


def draw_text(pixels: bytearray, width: int, height: int, font_data: bytes, text: str, x: int, y: int) -> None:
    cursor = x
    for char in text:
        if char == " ":
            cursor += 5
            continue
        rows = glyph_rows(font_data, char)
        for row_index, row in enumerate(rows):
            py = y + row_index
            if not 0 <= py < height:
                continue
            for column in range(GLYPH_WIDTH):
                px = cursor + column
                if 0 <= px < width and (row & (0x8000 >> column)):
                    pixels[(py * width) + px] = TEXT_INDEX
        cursor += GLYPH_WIDTH


def localize(source: Path, font_data: bytes, labels: tuple[tuple[str, int, int], ...], rects: tuple[tuple[int, int, int, int], ...]) -> tuple[ArenaIMG, bytes]:
    image = decode(source)
    pixels = bytearray(image.pixels)
    erase_text(pixels, image.width, image.height, rects)
    for text, x, y in labels:
        draw_text(pixels, image.width, image.height, font_data, text, x, y)
    return image, bytes(pixels)


def main() -> int:
    parser = argparse.ArgumentParser(description="캐릭터 능력치 고정 UI 한글화")
    parser.add_argument("--charstat", type=Path, required=True)
    parser.add_argument("--bonus", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--palette", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    font_data = args.font.read_bytes()
    if len(font_data) != 11172 * GLYPH_BYTES:
        raise ValueError(f"HANGUL9 크기가 올바르지 않습니다: {len(font_data)}")
    palette_data = args.palette.read_bytes()
    if len(palette_data) != 776:
        raise ValueError(f"CHARSHT.COL 크기가 올바르지 않습니다: {len(palette_data)}")
    palette_bytes = palette_data[8:]
    palette = [tuple(palette_bytes[index : index + 3]) for index in range(0, 768, 3)]

    charstat, charstat_pixels = localize(
        args.charstat,
        font_data,
        PRIMARY_LABELS + DERIVED_LABELS + STATUS_LABELS,
        ((5, 49, 160, 115), (0, 125, 45, 175), (15, 180, 36, 190)),
    )
    bonus, bonus_pixels = localize(
        args.bonus,
        font_data,
        (("보너스 점수", 5, 4),),
        ((3, 3, 46, 12),),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    charstat_output = args.output / "CHARSTAT.IMG"
    bonus_output = args.output / "BONUS.IMG"
    encode_uncompressed(charstat, charstat_pixels, charstat_output)
    encode_uncompressed(bonus, bonus_pixels, bonus_output)
    write_png(ArenaIMG(charstat.x, charstat.y, charstat.width, charstat.height, None, charstat_pixels), args.output / "CHARSTAT-preview-171x200.png", palette)
    write_png(ArenaIMG(bonus.x, bonus.y, bonus.width, bonus.height, None, bonus_pixels), args.output / "BONUS-preview-77x16.png", palette)
    print(f"wrote: {charstat_output}")
    print(f"wrote: {bonus_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
