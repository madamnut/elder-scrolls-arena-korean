#!/usr/bin/env python3
"""Render final-size Korean character-stat labels as transparent sprites."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

from PIL import Image


GLYPH_BYTES = 32
HANGUL_BASE = 0xAC00
GLYPH_WIDTH = 9
GLYPH_HEIGHT = 9
SPACE_WIDTH = 5
ATLAS_WIDTH = 128
GUTTER = 2
TEXT_PALETTE_INDEX = 253

LABEL_GROUPS = {
    "primary": (
        ("strength", "힘"),
        ("intelligence", "지능"),
        ("willpower", "의지"),
        ("agility", "민첩"),
        ("speed", "속도"),
        ("endurance", "인내"),
        ("personality", "매력"),
        ("luck", "행운"),
    ),
    "derived": (
        ("damage", "근접 피해"),
        ("max_kilos", "소지 한도"),
        ("spell_points", "마력"),
        ("magic_defense", "마법 저항"),
        ("to_hit", "명중"),
        ("to_defend", "회피"),
        ("health_growth", "성장 체력"),
        ("healing_rate", "회복률"),
        ("charisma", "카리스마"),
    ),
    "status": (
        ("health", "체력"),
        ("fatigue", "활력"),
        ("gold", "금화"),
        ("experience", "경험치"),
        ("level", "레벨"),
        ("done", "완료"),
        ("bonus_points", "잔여 스탯"),
    ),
}


def glyph_rows(font_data: bytes, char: str) -> tuple[int, ...]:
    index = ord(char) - HANGUL_BASE
    if not 0 <= index < 11172:
        raise ValueError(f"HANGUL9로 그릴 수 없는 문자: {char!r}")
    start = index * GLYPH_BYTES
    return struct.unpack_from("<16H", font_data, start)[:GLYPH_HEIGHT]


def text_width(text: str) -> int:
    return sum(SPACE_WIDTH if char == " " else GLYPH_WIDTH for char in text)


def render_text(font_data: bytes, text: str, color: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGBA", (text_width(text), GLYPH_HEIGHT), (0, 0, 0, 0))
    pixels = image.load()
    cursor = 0
    for char in text:
        if char == " ":
            cursor += SPACE_WIDTH
            continue
        for y, row in enumerate(glyph_rows(font_data, char)):
            for x in range(GLYPH_WIDTH):
                if row & (0x8000 >> x):
                    pixels[cursor + x, y] = (*color, 255)
        cursor += GLYPH_WIDTH
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description="캐릭터 능력치 한글 글자 아틀라스 생성")
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
    palette = palette_data[8:]
    start = TEXT_PALETTE_INDEX * 3
    color = tuple(palette[start : start + 3])

    args.output.mkdir(parents=True, exist_ok=True)
    sprites: list[tuple[str, str, str, Image.Image]] = []
    for group, labels in LABEL_GROUPS.items():
        for key, text in labels:
            sprite = render_text(font_data, text, color)
            sprite.save(args.output / f"{group}-{key}-{text}.png")
            sprites.append((group, key, text, sprite))

    placements: list[tuple[int, int, str, str, str, Image.Image]] = []
    x = y = GUTTER
    row_height = GLYPH_HEIGHT
    for group, key, text, sprite in sprites:
        if x + sprite.width + GUTTER > ATLAS_WIDTH:
            x = GUTTER
            y += row_height + GUTTER
        placements.append((x, y, group, key, text, sprite))
        x += sprite.width + GUTTER

    atlas_height = y + row_height + GUTTER
    atlas = Image.new("RGBA", (ATLAS_WIDTH, atlas_height), (0, 0, 0, 0))
    metadata = {
        "canvas": [ATLAS_WIDTH, atlas_height],
        "glyph": {"source": "HANGUL9", "size": [9, 9], "scale": 1},
        "spacing": {"hangul_advance": 9, "space_advance": 5, "atlas_gutter": GUTTER},
        "color": {"palette": "CHARSHT.COL", "index": TEXT_PALETTE_INDEX, "rgb": list(color)},
        "sprites": [],
    }
    for px, py, group, key, text, sprite in placements:
        atlas.alpha_composite(sprite, (px, py))
        metadata["sprites"].append(
            {
                "group": group,
                "key": key,
                "text": text,
                "rect": [px, py, sprite.width, sprite.height],
                "file": f"{group}-{key}-{text}.png",
            }
        )

    atlas.save(args.output / "CHARSTAT-text-atlas-actual-size.png")
    (args.output / "CHARSTAT-text-atlas.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote: {args.output / 'CHARSTAT-text-atlas-actual-size.png'}")
    print(f"sprites: {len(sprites)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
