#!/usr/bin/env python3
"""Render actual-size Korean sprites for Arena's OP.IMG escape menu."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

from PIL import Image


HANGUL_BASE = 0xAC00
GLYPH_BYTES = 32
FOREGROUND = (215, 159, 7, 255)  # PAL.COL index 192
SHADOW = (100, 77, 24, 255)  # PAL.COL index 198

TEXTS = (
    ("title-elder-scrolls", "The Elder Scrolls", "엘더 스크롤", 16),
    ("title-arena", "ARENA", "아레나", 16),
    ("sound", "SOUND", "효과음", 9),
    ("music", "MUSIC", "음악", 9),
    ("detail", "DETAIL", "화질", 9),
    ("new-game", "NEW GAME", "새 게임", 9),
    ("load-game", "LOAD GAME", "불러오기", 9),
    ("save-game", "SAVE GAME", "저장하기", 9),
    ("drop-to-dos", "DROP TO DOS", "게임 종료", 9),
    ("continue", "CONTINUE", "계속하기", 9),
    ("drop-to-dos-literal", "DROP TO DOS (대안)", "도스로 나가기", 9),
)


def glyph_rows(font_data: bytes, char: str, height: int) -> tuple[int, ...]:
    index = ord(char) - HANGUL_BASE
    if not 0 <= index < 11172:
        raise ValueError(f"글리프 뱅크로 그릴 수 없는 문자: {char!r}")
    start = index * GLYPH_BYTES
    return struct.unpack_from("<16H", font_data, start)[:height]


def render_mask(font_data: bytes, text: str, size: int) -> Image.Image:
    if size == 9:
        visible_width, advance, space = 9, 10, 5
    elif size == 16:
        visible_width, advance, space = 16, 17, 8
    else:
        raise ValueError(f"지원하지 않는 글리프 크기: {size}")

    width = sum(space if char == " " else advance for char in text)
    mask = Image.new("L", (width, size), 0)
    pixels = mask.load()
    cursor = 0
    for char in text:
        char_advance = space if char == " " else advance
        if char != " ":
            for y, row in enumerate(glyph_rows(font_data, char, size)):
                for x in range(visible_width):
                    if row & (0x8000 >> x):
                        pixels[cursor + x, y] = 255
        cursor += char_advance
    return mask


def colorize(mask: Image.Image) -> Image.Image:
    sprite = Image.new("RGBA", (mask.width + 1, mask.height + 1), (0, 0, 0, 0))
    sprite.paste(SHADOW, (1, 1), mask)
    sprite.paste(FOREGROUND, (0, 0), mask)
    bounds = sprite.getbbox()
    if bounds is None:
        raise ValueError("빈 글자 이미지는 만들 수 없습니다.")
    return sprite.crop(bounds)


def pack(images: list[Image.Image], max_width: int = 240) -> tuple[Image.Image, list[tuple[int, int, int, int]]]:
    gap = 4
    x = gap
    y = gap
    row_height = 0
    placements: list[tuple[int, int, int, int]] = []
    for image in images:
        if x > gap and x + image.width + gap > max_width:
            x = gap
            y += row_height + gap
            row_height = 0
        placements.append((x, y, image.width, image.height))
        x += image.width + gap
        row_height = max(row_height, image.height)
    height = y + row_height + gap
    atlas = Image.new("RGBA", (max_width, height), (0, 0, 0, 0))
    for image, (px, py, _, _) in zip(images, placements):
        atlas.alpha_composite(image, (px, py))
    return atlas, placements


def main() -> int:
    parser = argparse.ArgumentParser(description="ESC 메뉴 한글 단어 PNG와 실제 크기 아틀라스 생성")
    parser.add_argument("--font9", type=Path, required=True)
    parser.add_argument("--font16", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    font9 = args.font9.read_bytes()
    font16 = args.font16.read_bytes()
    expected = 11172 * GLYPH_BYTES
    if len(font9) != expected or len(font16) != expected:
        raise ValueError("한글 글리프 뱅크 크기가 올바르지 않습니다.")

    words = args.output / "words"
    words.mkdir(parents=True, exist_ok=True)
    images: list[Image.Image] = []
    records: list[dict[str, object]] = []
    for index, (slug, source, korean, size) in enumerate(TEXTS, start=1):
        bank = font9 if size == 9 else font16
        image = colorize(render_mask(bank, korean, size))
        filename = f"{index:02d}_{slug}_{image.width}x{image.height}.png"
        image.save(words / filename)
        images.append(image)
        records.append(
            {
                "index": index,
                "slug": slug,
                "source": source,
                "korean": korean,
                "font_bank": f"HANGUL{size}",
                "file": f"words/{filename}",
                "width": image.width,
                "height": image.height,
            }
        )

    atlas, placements = pack(images)
    atlas_name = f"04_ESC-menu-text-atlas-actual-size-{atlas.width}x{atlas.height}.png"
    atlas.save(args.output / atlas_name)
    for record, (x, y, width, height) in zip(records, placements):
        record["atlas"] = {"x": x, "y": y, "width": width, "height": height}
    (args.output / "04_ESC-menu-text-atlas.json").write_text(
        json.dumps({"atlas": atlas_name, "entries": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"rendered: {len(records)} sprites")
    print(f"atlas: {args.output / atlas_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
