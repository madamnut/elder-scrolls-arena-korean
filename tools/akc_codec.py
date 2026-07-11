#!/usr/bin/env python3
"""Arena Korean Codec (AKC).

ASCII is preserved as one byte. Precomposed modern Hangul syllables are
encoded as two high-bit bytes. This is a project-local encoding intended for
the future patched Arena text renderer; the unmodified game cannot display it.
"""

from __future__ import annotations

import argparse
import sys


HANGUL_BASE = 0xAC00
HANGUL_END = 0xD7A3
LEAD_BASE = 0x80
TRAIL_BASE = 0x80
TRAIL_BITS = 7
MAX_LEAD = LEAD_BASE + ((HANGUL_END - HANGUL_BASE) >> TRAIL_BITS)


class AKCError(ValueError):
    pass


def encode(text: str) -> bytes:
    out = bytearray()
    for position, char in enumerate(text):
        codepoint = ord(char)
        if codepoint in (0x09, 0x0A, 0x0D) or 0x20 <= codepoint <= 0x7F:
            out.append(codepoint)
            continue

        if HANGUL_BASE <= codepoint <= HANGUL_END:
            syllable_index = codepoint - HANGUL_BASE
            out.append(LEAD_BASE + (syllable_index >> TRAIL_BITS))
            out.append(TRAIL_BASE + (syllable_index & 0x7F))
            continue

        raise AKCError(
            f"AKC로 표현할 수 없는 문자 U+{codepoint:04X} {char!r} "
            f"(문자 위치 {position})"
        )

    return bytes(out)


def decode(data: bytes) -> str:
    chars: list[str] = []
    index = 0
    while index < len(data):
        first = data[index]
        if first < 0x80:
            if first not in (0x09, 0x0A, 0x0D) and first < 0x20:
                raise AKCError(f"허용되지 않은 제어 바이트 0x{first:02X} (바이트 위치 {index})")
            chars.append(chr(first))
            index += 1
            continue

        if first > MAX_LEAD:
            raise AKCError(f"잘못된 AKC 선행 바이트 0x{first:02X} (바이트 위치 {index})")
        if index + 1 >= len(data):
            raise AKCError(f"AKC 후행 바이트가 없음 (바이트 위치 {index})")

        second = data[index + 1]
        if not 0x80 <= second <= 0xFF:
            raise AKCError(f"잘못된 AKC 후행 바이트 0x{second:02X} (바이트 위치 {index + 1})")

        syllable_index = ((first - LEAD_BASE) << TRAIL_BITS) | (second - TRAIL_BASE)
        codepoint = HANGUL_BASE + syllable_index
        if codepoint > HANGUL_END:
            raise AKCError(f"한글 음절 범위를 벗어난 AKC 쌍 (바이트 위치 {index})")
        chars.append(chr(codepoint))
        index += 2

    return "".join(chars)


def self_test() -> None:
    samples = [
        "Arena 1.07",
        "가나다라마바사아자차카타파하",
        "엘더스크롤: 아레나",
        "체력 100%\n마력 42",
        "가힣",
    ]
    for sample in samples:
        encoded = encode(sample)
        decoded = decode(encoded)
        if decoded != sample:
            raise AssertionError((sample, encoded, decoded))

    all_syllables = "".join(chr(codepoint) for codepoint in range(HANGUL_BASE, HANGUL_END + 1))
    if decode(encode(all_syllables)) != all_syllables:
        raise AssertionError("11,172개 현대 한글 음절 왕복 시험 실패")

    print("AKC self-test: OK (ASCII + 현대 한글 11,172자)")


def parse_hex_bytes(value: str) -> bytes:
    compact = "".join(value.split()).replace("0x", "")
    try:
        return bytes.fromhex(compact)
    except ValueError as exc:
        raise AKCError(f"잘못된 16진수 입력: {value!r}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Arena Korean Codec (AKC) 변환기")
    subparsers = parser.add_subparsers(dest="command", required=True)

    encode_parser = subparsers.add_parser("encode", help="UTF-8 인수를 AKC로 변환")
    encode_parser.add_argument("text")
    encode_parser.add_argument("--hex", action="store_true", help="원시 바이트 대신 16진수 출력")

    decode_parser = subparsers.add_parser("decode", help="16진수 AKC를 UTF-8로 변환")
    decode_parser.add_argument("hex_bytes")

    subparsers.add_parser("self-test", help="전체 현대 한글 음절 왕복 시험")
    args = parser.parse_args(argv)

    try:
        if args.command == "encode":
            encoded = encode(args.text)
            if args.hex:
                print(encoded.hex(" "))
            else:
                sys.stdout.buffer.write(encoded)
        elif args.command == "decode":
            print(decode(parse_hex_bytes(args.hex_bytes)))
        else:
            self_test()
    except AKCError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

