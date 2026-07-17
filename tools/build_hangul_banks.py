#!/usr/bin/env python3
"""Build the 12px and 16px raw Hangul banks used by ARENAKR.COM.

Every bank contains 11,172 records in Unicode Hangul syllable order.  A
record is always sixteen little-endian 16-bit rows (32 bytes), allowing 512
glyphs to fit exactly in one 16 KiB EMS page.  The bitmap is never scaled by
the game renderer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageFont


HANGUL_BASE = 0xAC00
HANGUL_COUNT = 11172
STORED_ROWS = 16
GLYPH_BYTES = 32


class BuildError(ValueError):
    pass


def rows_to_record(rows: list[str], cell_width: int, cell_height: int) -> bytes:
    if len(rows) > cell_height:
        raise BuildError(f"글리프 높이 {len(rows)}가 셀 높이 {cell_height}를 넘습니다.")
    words: list[int] = []
    for row in rows:
        if len(row) > cell_width:
            raise BuildError(f"글리프 폭 {len(row)}가 셀 폭 {cell_width}를 넘습니다.")
        value = 0
        for x, pixel in enumerate(row):
            if pixel in ("#", "1"):
                value |= 0x8000 >> x
        words.append(value)
    words.extend([0] * (STORED_ROWS - len(words)))
    return struct.pack("<16H", *words)


def build_pfp(path: Path, cell_width: int = 12, cell_height: int = 12) -> bytes:
    source = json.loads(path.read_text(encoding="utf-8"))
    glyphs = {glyph.get("unicode"): glyph for glyph in source["glyphs"]}

    def resolve(codepoint: int, stack: frozenset[int] = frozenset()) -> list[str]:
        if codepoint in stack:
            raise BuildError(f"U+{codepoint:04X}: 순환 컴포넌트")
        glyph = glyphs.get(codepoint)
        if glyph is None:
            raise BuildError(f"U+{codepoint:04X}: 글리프가 없습니다.")
        if "data" in glyph:
            rows = list(glyph["data"])
        else:
            canvas = [[False] * cell_width for _ in range(cell_height)]
            for component in glyph.get("components", []):
                component_rows = resolve(component, stack | {codepoint})
                # PFP component bitmaps share a baseline. Choseong components
                # are full-height, while horizontal jungseong and jongseong
                # components omit transparent rows above them. Align their
                # stored rows to the bottom of the 12px cell before overlaying.
                y_offset = max(0, cell_height - len(component_rows))
                for source_y, row in enumerate(component_rows[:cell_height]):
                    y = y_offset + source_y
                    if y >= cell_height:
                        break
                    for x, pixel in enumerate(row[:cell_width]):
                        canvas[y][x] |= pixel in ("#", "1")
            rows = ["".join("#" if pixel else "." for pixel in row) for row in canvas]
        return rows

    output = bytearray()
    for codepoint in range(HANGUL_BASE, HANGUL_BASE + HANGUL_COUNT):
        output.extend(rows_to_record(resolve(codepoint), cell_width, cell_height))
    return bytes(output)


def build_ttf(path: Path, pixel_size: int = 16) -> bytes:
    font = ImageFont.truetype(str(path), pixel_size)
    output = bytearray()
    for codepoint in range(HANGUL_BASE, HANGUL_BASE + HANGUL_COUNT):
        image = Image.new("1", (16, 16), 0)
        ImageDraw.Draw(image).text((0, 0), chr(codepoint), font=font, fill=1, anchor="lt")
        bbox = image.getbbox()
        if bbox is None:
            raise BuildError(f"U+{codepoint:04X}: 빈 글리프")
        rows = []
        for y in range(16):
            rows.append("".join("#" if image.getpixel((x, y)) else "." for x in range(16)))
        output.extend(rows_to_record(rows, 16, 16))
    return bytes(output)


def write_bank(data: bytes, output: Path, metadata: Path | None, source: Path,
               source_font: str, visible_width: int, visible_height: int) -> None:
    expected = HANGUL_COUNT * GLYPH_BYTES
    if len(data) != expected:
        raise BuildError(f"출력 크기 {len(data)} != {expected}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    if metadata:
        metadata.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_text(json.dumps({
            "source": str(source),
            "source_font": source_font,
            "license": "SIL Open Font License 1.1",
            "first_codepoint": "U+AC00",
            "glyphs": HANGUL_COUNT,
            "visible_width": visible_width,
            "visible_height": visible_height,
            "record_bytes": GLYPH_BYTES,
            "glyphs_per_ems_page": 512,
            "ems_pages": 22,
            "file_bytes": len(data),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Arena용 12px·16px 한글 글리프 뱅크 생성")
    parser.add_argument("--mulmaru-pfp", type=Path, required=True)
    parser.add_argument("--neodgm-ttf", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--metadata-dir", type=Path)
    args = parser.parse_args()

    bank12 = build_pfp(args.mulmaru_pfp)
    bank16 = build_ttf(args.neodgm_ttf)
    write_bank(bank12, args.output_dir / "HANGUL12.FNT",
               args.metadata_dir / "HANGUL12.json" if args.metadata_dir else None,
               args.mulmaru_pfp, "Mulmaru Mono 12", 12, 12)
    write_bank(bank16, args.output_dir / "HANGUL16.FNT",
               args.metadata_dir / "HANGUL16.json" if args.metadata_dir else None,
               args.neodgm_ttf, "NeoDunggeunmo 1.601", 16, 16)
    print(f"HANGUL12.FNT: {len(bank12)} bytes")
    print(f"HANGUL16.FNT: {len(bank16)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
