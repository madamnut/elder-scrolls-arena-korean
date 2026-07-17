#!/usr/bin/env python3
"""Render Korean province labels from the project's native HANGUL9 bank."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct

from PIL import Image, ImageFilter


HANGUL_BASE = 0xAC00
GLYPH_BYTES = 32
VISIBLE_WIDTH = 9
VISIBLE_HEIGHT = 9
ADVANCE = 10
SPACE_ADVANCE = 5
OUTLINE_RGB = (40, 24, 8)
BASIC_RGB = (190, 4, 0)
HIGHLIGHT_RGB = (218, 174, 20)

LABELS = (
    ("high-rock", "하이 락", 56, 50),
    ("hammerfell", "해머펠", 86, 76),
    ("skyrim", "스카이림", 138, 44),
    ("morrowind", "모로윈드", 225, 84),
    ("summurset-isle", "서머셋 섬", 40, 152),
    ("valenwood", "발렌우드", 108, 147),
    ("elsweyr", "엘스웨어", 149, 132),
    ("black-marsh", "블랙 마쉬", 221, 144),
    ("imperial-province", "제국령", 160, 104),
)


def glyph_rows(font_data: bytes, char: str) -> tuple[int, ...]:
    index = ord(char) - HANGUL_BASE
    if not 0 <= index < 11172:
        raise ValueError(f"HANGUL9로 그릴 수 없는 문자: {char!r}")
    start = index * GLYPH_BYTES
    return struct.unpack_from("<16H", font_data, start)[:VISIBLE_HEIGHT]


def render_mask(font_data: bytes, text: str) -> Image.Image:
    advances = [SPACE_ADVANCE if char == " " else ADVANCE for char in text]
    width = sum(advances)
    mask = Image.new("L", (width, VISIBLE_HEIGHT), 0)
    pixels = mask.load()
    cursor = 0
    for char, advance in zip(text, advances):
        if char != " ":
            rows = glyph_rows(font_data, char)
            for y, row in enumerate(rows):
                for x in range(VISIBLE_WIDTH):
                    if row & (0x8000 >> x):
                        pixels[cursor + x, y] = 255
        cursor += advance
    return mask


def colorize(mask: Image.Image, foreground: tuple[int, int, int]) -> Image.Image:
    # One dark pixel around the 9px glyph matches the original OUTPROV style.
    padded = Image.new("L", (mask.width + 2, mask.height + 2), 0)
    padded.paste(mask, (1, 1))
    outline = padded.filter(ImageFilter.MaxFilter(3))
    image = Image.new("RGBA", padded.size, (0, 0, 0, 0))
    image.paste(OUTLINE_RGB + (255,), mask=outline)
    image.paste(foreground + (255,), mask=padded)
    return image


def build_atlas(images: list[Image.Image], columns: int = 3) -> tuple[Image.Image, list[tuple[int, int, int, int]]]:
    """Arrange sprites on a fixed grid with a one-pixel transparent border."""
    cell_width = max(image.width for image in images) + 2
    cell_height = max(image.height for image in images) + 2
    rows = (len(images) + columns - 1) // columns
    atlas = Image.new("RGBA", (cell_width * columns, cell_height * rows), (0, 0, 0, 0))
    rects: list[tuple[int, int, int, int]] = []
    for index, image in enumerate(images):
        x = ((index % columns) * cell_width) + 1
        y = ((index // columns) * cell_height) + 1
        atlas.alpha_composite(image, (x, y))
        rects.append((x, y, image.width, image.height))
    return atlas, rects


def main() -> int:
    parser = argparse.ArgumentParser(description="HANGUL9 지역명 투명 PNG 생성")
    parser.add_argument("font", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    font_data = args.font.read_bytes()
    if len(font_data) != 11172 * GLYPH_BYTES:
        raise ValueError(f"HANGUL9 크기가 올바르지 않습니다: {len(font_data)}")
    args.output.mkdir(parents=True, exist_ok=True)

    lines = [
        "# HANGUL9 지역명 이미지",
        "",
        "Galmuri9 9×9 원본 글리프, 글자 전진폭 10픽셀, 공백 5픽셀, 1픽셀 외곽선.",
        "",
        "| 번호 | 지역명 | PNG 크기 |",
        "|---:|---|---:|",
    ]
    basic_images: list[Image.Image] = []
    highlight_images: list[Image.Image] = []
    basic_layout = Image.new("RGBA", (320, 200), (0, 0, 0, 0))
    highlight_layout = Image.new("RGBA", (320, 200), (0, 0, 0, 0))
    for index, (slug, text, map_x, map_y) in enumerate(LABELS):
        mask = render_mask(font_data, text)
        basic = colorize(mask, BASIC_RGB)
        highlight = colorize(mask, HIGHLIGHT_RGB)
        stem = f"{index:02d}-{slug}"
        for variant, image in (("basic", basic), ("highlight", highlight)):
            image.save(args.output / f"{stem}-{variant}-{image.width}x{image.height}.png")
        basic_images.append(basic)
        highlight_images.append(highlight)
        basic_layout.alpha_composite(basic, (map_x, map_y))
        highlight_layout.alpha_composite(highlight, (map_x, map_y))
        lines.append(f"| {index} | `{text}` | {basic.width}×{basic.height} |")

    basic_layout.save(args.output / "region-labels-basic-layout-320x200.png")
    highlight_layout.save(args.output / "region-labels-highlight-layout-320x200.png")

    basic_atlas, rects = build_atlas(basic_images)
    highlight_atlas, highlight_rects = build_atlas(highlight_images)
    if rects != highlight_rects:
        raise AssertionError("basic/highlight atlas rectangles differ")
    basic_atlas.save(args.output / f"region-labels-basic-atlas-{basic_atlas.width}x{basic_atlas.height}.png")
    highlight_atlas.save(
        args.output / f"region-labels-highlight-atlas-{highlight_atlas.width}x{highlight_atlas.height}.png"
    )

    lines.extend(("", "## 아틀라스 좌표", "", "좌표 기준은 아틀라스 좌상단 `(0, 0)`이다.", "", "| 번호 | 지역명 | X | Y | 폭 | 높이 |", "|---:|---|---:|---:|---:|---:|"))
    for index, ((_, text, _, _), (x, y, width, height)) in enumerate(zip(LABELS, rects)):
        lines.append(f"| {index} | `{text}` | {x} | {y} | {width} | {height} |")

    lines.extend(("", "## 지도 배치 좌표", "", "좌표는 320×200 지도에서 각 스프라이트 캔버스의 좌상단이다.", "", "| 번호 | 지역명 | X | Y |", "|---:|---|---:|---:|"))
    for index, (_, text, map_x, map_y) in enumerate(LABELS):
        lines.append(f"| {index} | `{text}` | {map_x} | {map_y} |")

    (args.output / "이미지정보.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"rendered {len(LABELS)} labels in two colors: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
