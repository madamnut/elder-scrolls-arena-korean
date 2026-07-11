#!/usr/bin/env python3
"""Inspect and render TES Arena's fixed-width-row bitmap font DAT files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import struct
import sys
import zlib


BITMAP_OFFSET = 95
ROW_BYTES = 2
ROW_WIDTH = 16
ACTIVE_BITMAPS = 95  # '!' (33) through DEL (127); space borrows '!''s width.


class FontError(ValueError):
    pass


@dataclass(frozen=True)
class ArenaFont:
    path: Path
    height: int
    glyph_rows: tuple[tuple[int, ...], ...]

    @classmethod
    def load(cls, path: Path) -> "ArenaFont":
        data = path.read_bytes()
        if len(data) <= BITMAP_OFFSET:
            raise FontError("폰트 파일이 너무 짧습니다.")
        height = data[0]
        if not 1 <= height <= 16:
            raise FontError(f"지원하지 않는 글자 높이: {height}")
        bitmap_bytes = len(data) - BITMAP_OFFSET
        stride = height * ROW_BYTES
        if bitmap_bytes % stride != 0:
            raise FontError(
                f"비트맵 영역 {bitmap_bytes}바이트가 글자 크기 {stride}바이트로 나누어지지 않습니다."
            )
        glyph_count = bitmap_bytes // stride
        rows: list[tuple[int, ...]] = []
        offset = BITMAP_OFFSET
        for _ in range(glyph_count):
            rows.append(tuple(struct.unpack_from(f"<{height}H", data, offset)))
            offset += stride
        return cls(path=path, height=height, glyph_rows=tuple(rows))

    def derived_width(self, glyph_index: int) -> int:
        rows = self.glyph_rows[glyph_index]
        max_pixel = -1
        for row in rows:
            for x in range(ROW_WIDTH):
                if row & (0x8000 >> x):
                    max_pixel = max(max_pixel, x)
        return min(ROW_WIDTH, max_pixel + 2) if max_pixel >= 0 else 1


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def write_grayscale_png(path: Path, width: int, height: int, pixels: bytes) -> None:
    if len(pixels) != width * height:
        raise ValueError("PNG 픽셀 버퍼 크기가 맞지 않습니다.")
    scanlines = bytearray()
    for y in range(height):
        scanlines.append(0)  # PNG filter: None
        start = y * width
        scanlines.extend(pixels[start : start + width])
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    data = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(bytes(scanlines), level=9))
        + png_chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def render_sheet(font: ArenaFont, output: Path, columns: int, scale: int) -> None:
    if columns <= 0 or scale <= 0:
        raise FontError("columns와 scale은 양수여야 합니다.")
    glyph_count = len(font.glyph_rows)
    rows = (glyph_count + columns - 1) // columns
    cell_width = ROW_WIDTH + 2
    cell_height = font.height + 2
    width = columns * cell_width
    height = rows * cell_height
    pixels = bytearray([24] * (width * height))

    for glyph_index, glyph_rows in enumerate(font.glyph_rows):
        cell_x = (glyph_index % columns) * cell_width
        cell_y = (glyph_index // columns) * cell_height
        # Border color distinguishes the 95 active bitmaps from five trailing ones.
        border = 80 if glyph_index < ACTIVE_BITMAPS else 140
        for x in range(cell_width):
            pixels[cell_y * width + cell_x + x] = border
            pixels[(cell_y + cell_height - 1) * width + cell_x + x] = border
        for y in range(cell_height):
            pixels[(cell_y + y) * width + cell_x] = border
            pixels[(cell_y + y) * width + cell_x + cell_width - 1] = border

        for y, bits in enumerate(glyph_rows):
            for x in range(ROW_WIDTH):
                if bits & (0x8000 >> x):
                    pixels[(cell_y + 1 + y) * width + cell_x + 1 + x] = 255

    if scale != 1:
        scaled_width = width * scale
        scaled_height = height * scale
        scaled = bytearray(scaled_width * scaled_height)
        for y in range(height):
            source_row = pixels[y * width : (y + 1) * width]
            expanded = bytes(value for value in source_row for _ in range(scale))
            for sy in range(scale):
                start = ((y * scale) + sy) * scaled_width
                scaled[start : start + scaled_width] = expanded
        width, height, pixels = scaled_width, scaled_height, scaled

    write_grayscale_png(output, width, height, bytes(pixels))


def command_info(font: ArenaFont) -> None:
    print(f"file: {font.path}")
    print(f"height: {font.height}")
    print(f"stored bitmaps: {len(font.glyph_rows)}")
    print(f"active bitmaps: {min(ACTIVE_BITMAPS, len(font.glyph_rows))}")
    print(f"trailing bitmaps: {max(0, len(font.glyph_rows) - ACTIVE_BITMAPS)}")
    widths = [font.derived_width(index) for index in range(min(ACTIVE_BITMAPS, len(font.glyph_rows)))]
    if widths:
        print(f"derived width range: {min(widths)}-{max(widths)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TES Arena DAT 폰트 분석기")
    subparsers = parser.add_subparsers(dest="command", required=True)

    info_parser = subparsers.add_parser("info")
    info_parser.add_argument("font", type=Path)

    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("font", type=Path)
    render_parser.add_argument("output", type=Path)
    render_parser.add_argument("--columns", type=int, default=16)
    render_parser.add_argument("--scale", type=int, default=4)

    args = parser.parse_args(argv)
    try:
        font = ArenaFont.load(args.font)
        if args.command == "info":
            command_info(font)
        else:
            render_sheet(font, args.output, args.columns, args.scale)
            print(f"PNG 저장: {args.output}")
    except (FontError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

