#!/usr/bin/env python3
"""List NUL-terminated text strings and their offsets in a DOS MZ file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import struct


def mz_header_size(data: bytes) -> int | None:
    if len(data) < 0x1C or data[:2] != b"MZ":
        return None
    return struct.unpack_from("<H", data, 8)[0] * 16


def is_text_byte(value: int) -> bool:
    return value in (0x09, 0x0A, 0x0D) or 0x20 <= value <= 0x7E


def iter_strings(data: bytes, minimum: int):
    start = 0
    while start < len(data):
        if not is_text_byte(data[start]):
            start += 1
            continue
        end = start
        while end < len(data) and is_text_byte(data[end]):
            end += 1
        if end < len(data) and data[end] == 0 and end - start >= minimum:
            yield start, data[start:end].decode("ascii")
        start = end + 1


def escaped(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\t", "\\t").replace(
        "\r", "\\r"
    ).replace("\n", "\\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--min-length", type=int, default=4)
    parser.add_argument("--match", help="case-insensitive regular expression")
    parser.add_argument("--jsonl", action="store_true")
    args = parser.parse_args()

    data = args.input.read_bytes()
    header_size = mz_header_size(data)
    pattern = re.compile(args.match, re.IGNORECASE) if args.match else None
    count = 0
    for offset, value in iter_strings(data, args.min_length):
        if pattern and pattern.search(value) is None:
            continue
        image_offset = offset - header_size if header_size is not None else None
        row = {
            "file_offset": offset,
            "image_offset": image_offset if image_offset is not None and image_offset >= 0 else None,
            "byte_length": len(value.encode("ascii")),
            "text": value,
        }
        if args.jsonl:
            print(json.dumps(row, ensure_ascii=False))
        else:
            image = "-" if row["image_offset"] is None else f"0x{row['image_offset']:X}"
            print(f"0x{offset:X}\t{image}\t{row['byte_length']}\t{escaped(value)}")
        count += 1
    if not args.jsonl:
        print(f"strings: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
