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
FONT_B_PATH = ROOT / "ARENA" / "FONT_B.DAT"
QUESTION_PATH = ROOT / "ARENA" / "QUESTION.TXT"
HANGUL_ADVANCE = 10
HANGUL_LINE_ADVANCE = 11
QUESTION_TEXT_X = 20
QUESTION_RIGHT_EDGE = 310


def load_font_b_widths() -> tuple[bytes, int]:
    font = FONT_B_PATH.read_bytes()
    if len(font) < 95:
        raise ValueError("FONT_B.DAT is too short to contain its width table")
    if font[0] != 6:
        raise ValueError(f"Unexpected FONT_B height: {font[0]}")
    return font[:95], font[0] + 1


FONT_B_WIDTHS, FONT_B_LINE_ADVANCE = load_font_b_widths()


def pixel_width(text: str) -> int:
    width = 0
    for char in text:
        if "가" <= char <= "힣":
            width += HANGUL_ADVANCE
        elif char == " ":
            width += FONT_B_WIDTHS[1] + 1
        elif 0x21 <= ord(char) <= 0x7E:
            width += FONT_B_WIDTHS[ord(char) - 0x20]
        else:
            raise ValueError(f"Unsupported question character: {char!r}")
    return width


def wrap_line(line: str, max_line_pixels: int) -> list[str]:
    if pixel_width(line) <= max_line_pixels:
        return [line]

    leading = line[: len(line) - len(line.lstrip(" "))]
    content = line[len(leading) :]
    prefix = leading
    match = re.match(r"^(\d+\.\s+|[abc]\)\s+)", content)
    if match is not None:
        prefix += match.group(1)
        content = content[match.end() :]
    # Arena centers every CR-terminated line independently. Leading spaces on
    # continuation lines therefore shift the visible text away from the true
    # center instead of producing a stable left-aligned hanging indent.
    continuation = ""

    output: list[str] = []
    current = prefix
    for word in content.split(" "):
        candidate = current + ("" if current.endswith(" ") else " ") + word
        if current.strip() and pixel_width(candidate) > max_line_pixels:
            output.append(current.rstrip())
            current = continuation + word
        else:
            current = candidate
    if current.strip():
        output.append(current.rstrip())

    # Keep scoring tags with Korean text. A tag-only continuation would be an
    # ASCII-only line and Arena's transitional line hook would fall back to the
    # original 7px FONT_B line advance instead of HANGUL9's 11px line box.
    if len(output) >= 2 and re.fullmatch(r"\(5[lcv]\)", output[-1]):
        previous_words = output[-2].split(" ")
        moved = previous_words.pop()
        output[-2] = " ".join(previous_words)
        output[-1] = f"{moved} {output[-1]}"
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


def add_question_delimiter(field: str) -> str:
    """Add the colon that Arena uses to locate the first answer."""
    field = field.rstrip()
    if field.endswith((".", "?", "!")):
        field = field[:-1].rstrip()
    if ":" in field:
        raise ValueError(f"Question stem already contains an internal colon: {field!r}")
    return field + ":"


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


def original_layout_limits() -> tuple[int, int]:
    lines = QUESTION_PATH.read_text(encoding="ascii").splitlines()
    # Preserve trailing spaces here because Arena's width routine measures them
    # and uses the result when centering the complete line.
    max_line_pixels = max(pixel_width(line) for line in lines)

    question_line_counts: list[int] = []
    current = 0
    for line in lines:
        if re.match(r"^\d+\.", line):
            if current:
                question_line_counts.append(current)
            current = 0
        current += 1
    if current:
        question_line_counts.append(current)
    if len(question_line_counts) != 40:
        raise ValueError(
            f"Expected 40 original question blocks, got {len(question_line_counts)}"
        )
    max_block_pixels = max(question_line_counts) * FONT_B_LINE_ADVANCE
    return max_line_pixels, max_block_pixels


def validate_engine_records(encoded: bytes) -> None:
    """Reproduce Arena's colon/tag record-boundary scan for all 40 records."""
    line_starts = [0]
    line_starts.extend(index + 1 for index, value in enumerate(encoded) if value == 0x0A)
    marker_offsets: dict[int, int] = {}
    for offset in line_starts:
        match = re.match(rb"(\d+)\.", encoded[offset:])
        if match is not None:
            marker_offsets[int(match.group(1))] = offset
    if sorted(marker_offsets) != list(range(1, 41)):
        raise ValueError("Encoded question markers are not exactly 1 through 40")

    for number in range(1, 41):
        start = marker_offsets[number]
        colon = encoded.find(b":", start)
        if colon < 0:
            raise ValueError(f"Question {number} has no engine delimiter colon")
        cursor = colon + 1
        tag_positions: list[int] = []
        for _ in range(3):
            cursor = encoded.find(b"(", cursor)
            if cursor < 0:
                raise ValueError(f"Question {number} has fewer than three scoring tags")
            if re.match(rb"\(5[lcv]\) \n", encoded[cursor:]) is None:
                raise ValueError(
                    f"Question {number} has an invalid scoring-tag terminator at byte {cursor}"
                )
            tag_positions.append(cursor)
            cursor += 1

        engine_end = tag_positions[-1] + 6
        expected_end = marker_offsets.get(number + 1, len(encoded))
        if engine_end != expected_end:
            raise ValueError(
                f"Question {number} engine boundary mismatch: {engine_end} != {expected_end}"
            )


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
    logical_fields = [
        add_question_delimiter(field) if index % 4 == 0 else field
        for index, field in enumerate(logical_fields)
    ]
    original_line_pixels, max_block_pixels = original_layout_limits()
    max_line_pixels = min(
        original_line_pixels,
        QUESTION_RIGHT_EDGE - QUESTION_TEXT_X,
    )
    trailing_space_pixels = FONT_B_WIDTHS[1] + 1
    content_line_pixels = max_line_pixels - trailing_space_pixels
    wrapped_fields = [wrap_line(field, content_line_pixels) for field in logical_fields]
    wrapped_questions = [
        [line for field in wrapped_fields[index : index + 4] for line in field]
        for index in range(0, len(wrapped_fields), 4)
    ]
    wrapped_lines = [line for question in wrapped_questions for line in question]
    # Every original line ends in exactly the significant sequence SPACE+LF.
    # The question parser uses the trailing space after a (5x) tag when finding
    # the current record boundary. CRLF or a bare LF changes the file grammar.
    wrapped = " \n".join(wrapped_lines) + " \n"
    encoded = encode_akc(wrapped)
    validate_engine_records(encoded)

    original_size = QUESTION_PATH.stat().st_size
    if len(encoded) > original_size:
        raise ValueError(f"Korean question file exceeds original size: {len(encoded)} > {original_size}")
    if any(pixel_width(line) + trailing_space_pixels > max_line_pixels for line in wrapped_lines):
        raise ValueError("A wrapped line still exceeds the safe width")
    ascii_only_lines = [
        line for line in wrapped_lines if not any("가" <= char <= "힣" for char in line)
    ]
    if ascii_only_lines:
        raise ValueError(
            "A Korean question contains ASCII-only lines with inconsistent line advance: "
            f"{ascii_only_lines[:3]!r}"
        )
    question_heights = [len(question) * HANGUL_LINE_ADVANCE for question in wrapped_questions]
    if max(question_heights) > max_block_pixels:
        raise ValueError(
            "A Korean question exceeds the original vertical layout budget: "
            f"{max(question_heights)} > {max_block_pixels} pixels"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"questions: 40")
    print(f"choices: 120")
    print(f"lines: {len(wrapped_lines)}")
    print(f"bytes: {len(encoded)} / {original_size}")
    print(f"line width limit: {max_line_pixels} pixels")
    print(
        "max exact width: "
        f"{max(map(pixel_width, wrapped_lines)) + trailing_space_pixels} pixels "
        "(including required trailing space)"
    )
    print(f"block height limit: {max_block_pixels} pixels")
    print(f"max Korean block height: {max(question_heights)} pixels")
    tallest = [index + 1 for index, height in enumerate(question_heights) if height == max(question_heights)]
    print(f"tallest questions: {', '.join(map(str, tallest))}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
