#!/usr/bin/env python3
"""Build and validate the Korean character-class question file."""

from __future__ import annotations

import argparse
from pathlib import Path
import re

from akc_codec import encode as encode_akc


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "korean-patch" / "translations" / "QUEST_KR.utf8.txt"
DEFAULT_OUTPUT = ROOT / "korean-patch" / "build" / "QUEST_KR.TXT"
MAX_LINE_PIXELS = 285


def estimated_width(text: str) -> int:
    width = 0
    for char in text:
        if "가" <= char <= "힣":
            width += 10
        elif char == " ":
            width += 4
        else:
            width += 6
    return width


def wrap_line(line: str) -> list[str]:
    if estimated_width(line) <= MAX_LINE_PIXELS:
        return [line]

    leading = line[: len(line) - len(line.lstrip(" "))]
    content = line[len(leading) :]
    prefix = leading
    match = re.match(r"^(\d+\.\s+|[abc]\)\s+)", content)
    if match is not None:
        prefix += match.group(1)
        content = content[match.end() :]
    continuation = " " * max(3, len(prefix))

    output: list[str] = []
    current = prefix
    for word in content.split(" "):
        candidate = current + ("" if current.endswith(" ") else " ") + word
        if current.strip() and estimated_width(candidate) > MAX_LINE_PIXELS:
            output.append(current.rstrip())
            current = continuation + word
        else:
            current = candidate
    if current.strip():
        output.append(current.rstrip())
    return output


def merge_logical_fields(source: str) -> list[str]:
    fields: list[str] = []
    current = ""
    for line in source.splitlines():
        stripped = line.strip()
        if re.match(r"^(\d+\.|[abc]\))\s+", stripped):
            if current:
                fields.append(current)
            current = stripped
        else:
            if not current:
                raise ValueError(f"Continuation line without a field: {line!r}")
            current += " " + stripped
    if current:
        fields.append(current)
    return fields


def validate_structure(text: str) -> None:
    question_numbers = [int(value) for value in re.findall(r"(?m)^(\d+)\.", text)]
    if question_numbers != list(range(1, 41)):
        raise ValueError("Question numbers must be exactly 1 through 40")

    for letter in "abc":
        count = len(re.findall(rf"(?m)^{letter}\)", text))
        if count != 40:
            raise ValueError(f"Expected 40 '{letter})' choices, got {count}")

    for category in "lcv":
        count = text.count(f"(5{category})")
        if count != 40:
            raise ValueError(f"Expected 40 '(5{category})' tags, got {count}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.input.read_text(encoding="utf-8")
    validate_structure(source)
    logical_fields = merge_logical_fields(source)
    if len(logical_fields) != 160:
        raise ValueError(f"Expected 160 logical fields, got {len(logical_fields)}")
    wrapped_lines = [wrapped for field in logical_fields for wrapped in wrap_line(field)]
    wrapped = "\r\n".join(wrapped_lines) + "\r\n"
    encoded = encode_akc(wrapped)

    original_size = (ROOT / "ARENA" / "QUESTION.TXT").stat().st_size
    if len(encoded) > original_size:
        raise ValueError(f"Korean question file exceeds original size: {len(encoded)} > {original_size}")
    if any(estimated_width(line) > MAX_LINE_PIXELS for line in wrapped_lines):
        raise ValueError("A wrapped line still exceeds the safe width")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"questions: 40")
    print(f"choices: 120")
    print(f"lines: {len(wrapped_lines)}")
    print(f"bytes: {len(encoded)} / {original_size}")
    print(f"max estimated width: {max(map(estimated_width, wrapped_lines))}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
