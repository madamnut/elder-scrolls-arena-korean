#!/usr/bin/env python3
"""Patch the unpacked Arena 1.07 ACD.EXE renderer to call INT 60h.

The output requires ARENAKR.COM to be loaded first. This tool never overwrites
its input and validates the complete original routine bodies before patching.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct
import sys

from akc_codec import encode as encode_akc


EXPECTED_UNPACKED_SHA256 = "3d698ac22c1f7da49d87c78d80f89f3c3822ba3f62708b67f98fff3dac300a86"
WIDTH_START = 0x66F6
WIDTH_END = 0x673D
DRAW_START = 0x9E0A
DRAW_END = 0x9EC3

EXPECTED_WIDTH = bytes.fromhex(
    "1e0657561e078bfebfa03b8ec726c43e34b033d2f604ff7427803c20750a268a45019803d0"
    "42eb15578a0422c0780d2c2072099803f8268a059803d05f46ebd48bc25e5f071fc3"
)
EXPECTED_DRAW = bytes.fromhex(
    "5506571e50b8a03b8ed858a3b6ad891eb8ad03db8bbfa0a68e0600a91fac22c00f8491002c"
    "20746d7cf31e565750b8a03b8ed858fec88a1e8892538ad832ff32e48be8033eb6adc53634"
    "b08a1432f6508bc303c0f6e28bd8585603f58a4c0132ed5e03f383c65f87ca5b5751508bca"
    "8b2c83c60203ed730326881d47e2f658595f81c74001e2e3bea03b8ede0116b6ad5f5e1feb"
    "881e56bea03b8edec53634b08a440132e4fec0bea03b8ede0106b6ad5e1fe968ff5f075dc3"
)


class PatchError(ValueError):
    pass


def mz_header_size(data: bytes) -> int:
    if len(data) < 28 or data[:2] != b"MZ":
        raise PatchError("입력 파일이 DOS MZ 실행 파일이 아닙니다.")
    return struct.unpack_from("<H", data, 8)[0] * 16


def relocation_offsets(data: bytes) -> set[int]:
    count = struct.unpack_from("<H", data, 6)[0]
    table = struct.unpack_from("<H", data, 24)[0]
    offsets: set[int] = set()
    for index in range(count):
        offset, segment = struct.unpack_from("<HH", data, table + (index * 4))
        offsets.add((segment * 16) + offset)
    return offsets


def make_width_stub(length: int, interrupt: int) -> bytes:
    # Keep the relocated 0x3BA0 immediate at image offset 0x66FF.
    stub = bytes.fromhex(
        "1e 06 57 56 1e 07 8b fe bf a0 3b 8e c7 "
        "ba 00 00"
    ) + bytes((0xCD, interrupt)) + bytes.fromhex("5e 5f 07 1f c3")
    return stub.ljust(length, b"\x90")


def make_draw_stub(length: int, interrupt: int) -> bytes:
    # Keep the relocated 0x3BA0 immediate at image offset 0x9E10. ES receives
    # Arena's data segment while DS:SI remains the caller's text pointer.
    stub = bytes.fromhex("55 06 57 1e 50 b8 a0 3b 8e c0 58 ba 01 00")
    stub += bytes((0xCD, interrupt)) + bytes.fromhex("1f 5f 07 5d c3")
    return stub.ljust(length, b"\x90")


def replace_fixed(data: bytearray, source: bytes, replacement: bytes) -> None:
    positions: list[int] = []
    start = 0
    while True:
        index = data.find(source, start)
        if index < 0:
            break
        positions.append(index)
        start = index + 1
    if len(positions) != 1:
        raise PatchError(f"시험 문자열 {source!r}의 개수가 {len(positions)}개입니다.")
    if len(replacement) > len(source):
        raise PatchError(f"시험 번역문이 원문 공간보다 큽니다: {source!r}")
    index = positions[0]
    data[index : index + len(source)] = replacement.ljust(len(source), b"\0")


def apply_proof_menu(data: bytearray) -> None:
    for source, korean in (
        (
            b"How do you wish\rto select your class?\r\0",
            "직업을 어떻게\r선택하시겠습니까?",
        ),
        (
            b"10 questions shall be asked that will\r"
            b"determine the path of your destiny.\r"
            b"The scroll bars roll the parchment up\r"
            b"or down. Use the 'A', 'B', or 'C' keys\r"
            b"to answer the questions.\r\0",
            "열 가지 질문으로\r"
            "그대의 운명이 정해집니다.\r"
            "두루마리 막대를 움직여 내용을 보고,\r"
            "A, B, C 키로 답을 선택하십시오.",
        ),
        (b"Generate\r\0", "생성"),
        (b"Select\r\0", "선택"),
        (b"Male\r\0", "남성"),
        (b"Female\r\0", "여성"),
    ):
        replace_fixed(data, source, encode_akc(korean) + b"\r\0")


def apply_bsa_name(data: bytearray, filename: str) -> None:
    try:
        encoded = filename.encode("ascii")
    except UnicodeEncodeError as exc:
        raise PatchError("BSA 파일명은 ASCII여야 합니다.") from exc
    if not 1 <= len(encoded) <= 12 or "." not in filename:
        raise PatchError("BSA 파일명은 8.3 형식의 최대 12바이트여야 합니다.")
    source = b"global.bsa\0\0\0"
    positions: list[int] = []
    start = 0
    while True:
        index = data.find(source, start)
        if index < 0:
            break
        positions.append(index)
        start = index + 1
    if len(positions) != 1:
        raise PatchError(f"global.bsa 여유 영역의 개수가 {len(positions)}개입니다.")
    replacement = (encoded + b"\0").ljust(len(source), b"\0")
    index = positions[0]
    data[index : index + len(source)] = replacement


def apply_intro_name(data: bytearray, filename: str) -> None:
    try:
        encoded = filename.encode("ascii")
    except UnicodeEncodeError as exc:
        raise PatchError("INTRO 파일명은 ASCII여야 합니다.") from exc
    source = b"intro.flc"
    if len(encoded) != len(source) or not filename.lower().endswith(".flc"):
        raise PatchError("대체 INTRO 파일명은 intro.flc와 같은 9바이트여야 합니다.")
    positions: list[int] = []
    start = 0
    while True:
        index = data.lower().find(source, start)
        if index < 0:
            break
        positions.append(index)
        start = index + 1
    if len(positions) != 1:
        raise PatchError(f"intro.flc 문자열의 개수가 {len(positions)}개입니다.")
    index = positions[0]
    data[index : index + len(source)] = encoded


def apply_template_name(data: bytearray, filename: str) -> None:
    try:
        encoded = filename.encode("ascii")
    except UnicodeEncodeError as exc:
        raise PatchError("TEMPLATE filename must be ASCII.") from exc
    source = b"template.dat"
    if len(encoded) != len(source) or not filename.lower().endswith(".dat"):
        raise PatchError("Replacement TEMPLATE filename must be 12 bytes and end in .DAT.")
    positions: list[int] = []
    start = 0
    while True:
        index = data.lower().find(source, start)
        if index < 0:
            break
        positions.append(index)
        start = index + 1
    if len(positions) != 2:
        raise PatchError(f"Expected 2 template.dat strings, found {len(positions)}.")
    for index in positions:
        data[index : index + len(source)] = encoded


def apply_question_name(data: bytearray, filename: str) -> None:
    try:
        encoded = filename.encode("ascii")
    except UnicodeEncodeError as exc:
        raise PatchError("QUESTION filename must be ASCII.") from exc
    source = b"question.txt"
    if len(encoded) != len(source) or not filename.lower().endswith(".txt"):
        raise PatchError("Replacement QUESTION filename must be 12 bytes and end in .TXT.")
    positions: list[int] = []
    start = 0
    while True:
        index = data.lower().find(source, start)
        if index < 0:
            break
        positions.append(index)
        start = index + 1
    if len(positions) != 1:
        raise PatchError(f"Expected 1 question.txt string, found {len(positions)}.")
    index = positions[0]
    data[index : index + len(source)] = encoded


def patch(
    input_path: Path,
    output_path: Path,
    interrupt: int,
    proof_menu: bool,
    bsa_name: str | None,
    intro_name: str | None,
    template_name: str | None,
    question_name: str | None,
) -> None:
    if input_path.resolve() == output_path.resolve():
        raise PatchError("입력 실행 파일을 직접 덮어쓸 수 없습니다.")
    if not 0x20 <= interrupt <= 0xFF:
        raise PatchError("인터럽트 번호는 0x20–0xFF여야 합니다.")

    data = bytearray(input_path.read_bytes())
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_UNPACKED_SHA256:
        raise PatchError(
            "지원하는 Deark 해제본과 SHA-256이 다릅니다: " + digest
        )
    header_size = mz_header_size(data)
    image = memoryview(data)[header_size:]
    if bytes(image[WIDTH_START:WIDTH_END]) != EXPECTED_WIDTH:
        raise PatchError("폭 계산 함수의 원본 바이트가 예상과 다릅니다.")
    if bytes(image[DRAW_START:DRAW_END]) != EXPECTED_DRAW:
        raise PatchError("글자 그리기 함수의 원본 바이트가 예상과 다릅니다.")

    relocations = relocation_offsets(data)
    if 0x66FF not in relocations or 0x9E10 not in relocations:
        raise PatchError("후킹 스텁에 필요한 데이터 세그먼트 재배치 항목이 없습니다.")

    image[WIDTH_START:WIDTH_END] = make_width_stub(WIDTH_END - WIDTH_START, interrupt)
    image[DRAW_START:DRAW_END] = make_draw_stub(DRAW_END - DRAW_START, interrupt)
    del image
    if proof_menu:
        apply_proof_menu(data)
    if bsa_name:
        apply_bsa_name(data, bsa_name)
    if intro_name:
        apply_intro_name(data, intro_name)
    if template_name:
        apply_template_name(data, template_name)
    if question_name:
        apply_question_name(data, question_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    print(f"patched: {output_path}")
    print(f"sha256: {hashlib.sha256(data).hexdigest()}")
    print(f"interrupt: 0x{interrupt:02X}")
    print(f"proof menu: {proof_menu}")
    print(f"BSA name: {bsa_name or 'global.bsa'}")
    print(f"INTRO name: {intro_name or 'intro.flc'}")
    print(f"TEMPLATE name: {template_name or 'template.dat'}")
    print(f"QUESTION name: {question_name or 'question.txt'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Arena ACD.EXE 한국어 렌더러 후킹 도구")
    parser.add_argument("input", type=Path, help="Deark로 해제한 321,728바이트 ACD.EXE")
    parser.add_argument("output", type=Path)
    parser.add_argument("--interrupt", type=lambda value: int(value, 0), default=0x60)
    parser.add_argument(
        "--proof-menu",
        action="store_true",
        help="캐릭터 생성 초기 질문·안내·선택 항목을 한국어로 교체",
    )
    parser.add_argument(
        "--bsa-name",
        help="원본 GLOBAL.BSA 대신 읽을 별도 8.3 파일명(예: GLOBAL_K.BSA)",
    )
    parser.add_argument(
        "--intro-name",
        help="원본 intro.flc 대신 읽을 같은 길이의 파일명(예: intkr.flc)",
    )
    parser.add_argument(
        "--template-name",
        help="Use an alternate 12-byte TEMPLATE filename (for example TEMPL_KR.DAT)",
    )
    parser.add_argument(
        "--question-name",
        help="Use an alternate 12-byte QUESTION filename (for example QUEST_KR.TXT)",
    )
    args = parser.parse_args(argv)
    try:
        patch(
            args.input,
            args.output,
            args.interrupt,
            args.proof_menu,
            args.bsa_name,
            args.intro_name,
            args.template_name,
            args.question_name,
        )
    except (PatchError, OSError, struct.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
