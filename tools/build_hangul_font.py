#!/usr/bin/env python3
"""Build Arena's raw 9px Hangul glyph bank from Galmuri9 BDF.

Output format intentionally has no header: 11,172 glyph records in Unicode
Hangul syllable order. Each record is 32 bytes (16 little-endian 16-bit rows),
so 512 glyphs fit exactly in one 16 KiB EMS page.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys

from arena_font import write_grayscale_png


HANGUL_BASE = 0xAC00
HANGUL_COUNT = 11172
GLYPH_WIDTH = 9
GLYPH_HEIGHT = 9
STORED_ROWS = 16
GLYPH_BYTES = STORED_ROWS * 2
GLYPHS_PER_PAGE = 512
EMS_PAGE_BYTES = 16384


class BuildError(ValueError):
    pass


def parse_bdf(path: Path) -> dict[int, tuple[int, ...]]:
    glyphs: dict[int, tuple[int, ...]] = {}
    # BDF control records and bitmap data are ASCII. Descriptive properties may
    # contain UTF-8 punctuation, which is irrelevant to this parser.
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    index = 0
    while index < len(lines):
        if not lines[index].startswith("STARTCHAR "):
            index += 1
            continue

        encoding: int | None = None
        width = height = x_offset = y_offset = None
        bitmap_rows: list[int] = []
        index += 1
        while index < len(lines) and lines[index] != "ENDCHAR":
            line = lines[index]
            if line.startswith("ENCODING "):
                encoding = int(line.split()[1])
            elif line.startswith("BBX "):
                _, w, h, x, y = line.split()
                width, height, x_offset, y_offset = map(int, (w, h, x, y))
            elif line == "BITMAP":
                index += 1
                while index < len(lines) and lines[index] != "ENDCHAR":
                    hex_row = lines[index].strip()
                    value = int(hex_row, 16)
                    value <<= 16 - (len(hex_row) * 4)
                    bitmap_rows.append(value & 0xFFFF)
                    index += 1
                break
            index += 1

        if encoding is not None and HANGUL_BASE <= encoding < HANGUL_BASE + HANGUL_COUNT:
            if width is None or height is None:
                raise BuildError(f"U+{encoding:04X}: BBX가 없습니다.")
            if (
                width > GLYPH_WIDTH
                or height > GLYPH_HEIGHT
                or x_offset is None
                or y_offset is None
                or x_offset < 0
                or y_offset < 0
                or (x_offset + width) > GLYPH_WIDTH
                or (y_offset + height) > GLYPH_HEIGHT
            ):
                raise BuildError(
                    f"U+{encoding:04X}: 예상 밖 BBX {width} {height} {x_offset} {y_offset}"
                )
            if len(bitmap_rows) != height:
                raise BuildError(f"U+{encoding:04X}: 비트맵 행이 {len(bitmap_rows)}개입니다.")
            # Normalize variable BDF boxes to a 9x9 cell whose baseline is the
            # bottom row. BDF bitmap rows are top-to-bottom.
            top_padding = GLYPH_HEIGHT - (y_offset + height)
            normalized = ([0] * top_padding) + [row >> x_offset for row in bitmap_rows]
            normalized.extend([0] * (GLYPH_HEIGHT - len(normalized)))
            glyphs[encoding] = tuple(normalized)
        index += 1
    return glyphs


def build_font(glyphs: dict[int, tuple[int, ...]]) -> bytes:
    missing = [
        codepoint
        for codepoint in range(HANGUL_BASE, HANGUL_BASE + HANGUL_COUNT)
        if codepoint not in glyphs
    ]
    if missing:
        preview = ", ".join(f"U+{codepoint:04X}" for codepoint in missing[:10])
        raise BuildError(f"현대 한글 음절 {len(missing)}개가 없습니다: {preview}")

    output = bytearray()
    for codepoint in range(HANGUL_BASE, HANGUL_BASE + HANGUL_COUNT):
        rows = list(glyphs[codepoint]) + ([0] * (STORED_ROWS - GLYPH_HEIGHT))
        output.extend(struct.pack(f"<{STORED_ROWS}H", *rows))
    expected = HANGUL_COUNT * GLYPH_BYTES
    if len(output) != expected:
        raise AssertionError((len(output), expected))
    return bytes(output)


def render_preview(font_data: bytes, output: Path) -> None:
    # Common syllables plus boundaries, laid out as a compact contact sheet.
    sample = "가각간갇갈감갑값갓강개객거검것게겨결경고곡골공과관광구국군궁권귀그극근글금급기길김나난날남내너네년노누눈다단달담답당대더도동되두라락란람랑러레려로록론료루를리마만말맛망매머명모무문미바박반발밤방배버번별보복본봉부불비사산살상새서선설성세소속손송수순술시신실아악안알암압앙애어언얼업없여연열영오옥온올옷와완왕외요용우운울원위유육윤으은을음의이인일임입있자작잔잘잠장재저전절정제조족존좋주준줄중지진질집차착찬참창처천철청초총추축춘출충치친칠카타파하한할함합항해허현형호홍화환활회효후훈흐흥희히힣"
    glyphs: list[bytes] = []
    for char in sample:
        glyph_index = ord(char) - HANGUL_BASE
        start = glyph_index * GLYPH_BYTES
        glyphs.append(font_data[start : start + GLYPH_BYTES])

    columns = 24
    rows = (len(glyphs) + columns - 1) // columns
    scale = 4
    cell_w = GLYPH_WIDTH + 2
    cell_h = GLYPH_HEIGHT + 2
    width = columns * cell_w
    height = rows * cell_h
    pixels = bytearray([20] * (width * height))
    for index, glyph in enumerate(glyphs):
        ox = (index % columns) * cell_w + 1
        oy = (index // columns) * cell_h + 1
        rows16 = struct.unpack(f"<{STORED_ROWS}H", glyph)
        for y in range(GLYPH_HEIGHT):
            for x in range(GLYPH_WIDTH):
                if rows16[y] & (0x8000 >> x):
                    pixels[(oy + y) * width + ox + x] = 255

    scaled_width = width * scale
    scaled_height = height * scale
    scaled = bytearray(scaled_width * scaled_height)
    for y in range(height):
        source = pixels[y * width : (y + 1) * width]
        expanded = bytes(value for value in source for _ in range(scale))
        for sy in range(scale):
            start = ((y * scale) + sy) * scaled_width
            scaled[start : start + scaled_width] = expanded
    write_grayscale_png(output, scaled_width, scaled_height, bytes(scaled))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Galmuri9 BDF에서 Arena 한글 글리프 뱅크 생성")
    parser.add_argument("bdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args(argv)

    try:
        glyphs = parse_bdf(args.bdf)
        font_data = build_font(glyphs)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(font_data)
        if args.metadata:
            metadata = {
                "source": str(args.bdf),
                "source_font": "Galmuri9 2.40.3",
                "license": "SIL Open Font License 1.1",
                "first_codepoint": "U+AC00",
                "glyphs": HANGUL_COUNT,
                "visible_width": GLYPH_WIDTH,
                "visible_height": GLYPH_HEIGHT,
                "record_bytes": GLYPH_BYTES,
                "glyphs_per_ems_page": GLYPHS_PER_PAGE,
                "ems_pages": (HANGUL_COUNT + GLYPHS_PER_PAGE - 1) // GLYPHS_PER_PAGE,
                "file_bytes": len(font_data),
            }
            args.metadata.parent.mkdir(parents=True, exist_ok=True)
            args.metadata.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        if args.preview:
            render_preview(font_data, args.preview)
    except (BuildError, OSError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"glyphs: {HANGUL_COUNT}")
    print(f"bytes: {len(font_data)}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
