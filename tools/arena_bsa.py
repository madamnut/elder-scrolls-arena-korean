#!/usr/bin/env python3
"""Inspect, extract, and safely rebuild TES Arena's GLOBAL.BSA archive."""

from __future__ import annotations

import argparse
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
import struct
import sys


HEADER_SIZE = 2
FOOTER_ENTRY_SIZE = 18
NAME_SIZE = 12
INF_KEYS = (0xEA, 0x7B, 0x4E, 0xBD, 0x19, 0xC9, 0x38, 0x99)


class BSAError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    name: str
    offset: int
    size: int
    compressed: int


class ArenaBSA:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        self.entries = self._parse()

    def _parse(self) -> list[Entry]:
        if len(self.data) < HEADER_SIZE:
            raise BSAError("BSA 헤더가 너무 짧습니다.")

        count = struct.unpack_from("<H", self.data, 0)[0]
        footer_offset = len(self.data) - (count * FOOTER_ENTRY_SIZE)
        if footer_offset < HEADER_SIZE:
            raise BSAError("BSA 파일 수와 푸터 크기가 맞지 않습니다.")

        entries: list[Entry] = []
        payload_offset = HEADER_SIZE
        names: set[str] = set()
        for index in range(count):
            record_offset = footer_offset + (index * FOOTER_ENTRY_SIZE)
            raw_name = self.data[record_offset : record_offset + NAME_SIZE]
            raw_name = raw_name.split(b"\0", 1)[0]
            try:
                name = raw_name.decode("ascii")
            except UnicodeDecodeError as exc:
                raise BSAError(f"항목 {index}의 파일명이 ASCII가 아닙니다.") from exc

            compressed, size = struct.unpack_from("<HI", self.data, record_offset + NAME_SIZE)
            if not name:
                raise BSAError(f"항목 {index}의 파일명이 비어 있습니다.")
            normalized = name.upper()
            if normalized in names:
                raise BSAError(f"중복 파일명: {name}")
            names.add(normalized)
            if payload_offset + size > footer_offset:
                raise BSAError(f"항목 {name}이 데이터 영역을 벗어납니다.")

            entries.append(Entry(name, payload_offset, size, compressed))
            payload_offset += size

        if payload_offset != footer_offset:
            raise BSAError(
                f"데이터 끝({payload_offset})과 푸터 시작({footer_offset})이 다릅니다."
            )
        return entries

    def read(self, entry: Entry) -> bytes:
        return self.data[entry.offset : entry.offset + entry.size]

    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def crypt_inf(data: bytes) -> bytes:
    """Encrypt/decrypt a BSA INF file (the operation is symmetric)."""
    output = bytearray(data)
    for index in range(len(output)):
        output[index] ^= ((index & 0xFF) + INF_KEYS[index & 7]) & 0xFF
    return bytes(output)


def safe_output_path(root: Path, archive_name: str) -> Path:
    # Arena archives have flat DOS filenames. Reject path separators anyway.
    if Path(archive_name).name != archive_name or "/" in archive_name or "\\" in archive_name:
        raise BSAError(f"안전하지 않은 BSA 파일명: {archive_name!r}")
    path = (root / archive_name).resolve()
    root_resolved = root.resolve()
    if root_resolved not in path.parents:
        raise BSAError(f"출력 경로가 대상 폴더를 벗어납니다: {path}")
    return path


def command_list(bsa: ArenaBSA) -> None:
    for entry in bsa.entries:
        print(f"{entry.name:12} {entry.size:8} offset={entry.offset:8} compressed={entry.compressed}")


def command_verify(bsa: ArenaBSA) -> None:
    compressed_count = sum(entry.compressed != 0 for entry in bsa.entries)
    print(f"OK: {bsa.path}")
    print(f"entries: {len(bsa.entries)}")
    print(f"size: {len(bsa.data)}")
    print(f"compressed flags: {compressed_count}")
    print(f"sha256: {bsa.sha256()}")


def command_extract(bsa: ArenaBSA, output: Path, decode_inf: bool) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for entry in bsa.entries:
        data = bsa.read(entry)
        if decode_inf and entry.name.upper().endswith(".INF"):
            data = crypt_inf(data)
        path = safe_output_path(output, entry.name)
        path.write_bytes(data)
    print(f"{len(bsa.entries)}개 파일 추출: {output}")


def validate_archive_name(name: str) -> bytes:
    try:
        encoded = name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise BSAError(f"BSA 파일명은 ASCII여야 합니다: {name!r}") from exc
    if not encoded or len(encoded) > NAME_SIZE:
        raise BSAError(f"BSA 파일명은 1–12바이트여야 합니다: {name!r}")
    if Path(name).name != name or "/" in name or "\\" in name:
        raise BSAError(f"BSA 파일명에 경로를 넣을 수 없습니다: {name!r}")
    return encoded


def command_rebuild(
    bsa: ArenaBSA,
    replacements: Path,
    output: Path,
    encode_inf: bool,
) -> None:
    input_resolved = bsa.path.resolve()
    output_resolved = output.resolve()
    if input_resolved == output_resolved:
        raise BSAError("입력 BSA를 직접 덮어쓸 수 없습니다. 별도 출력 경로를 사용하세요.")
    if not replacements.is_dir():
        raise BSAError(f"교체 폴더가 없습니다: {replacements}")

    replacement_lookup = {
        path.name.upper(): path
        for path in replacements.iterdir()
        if path.is_file()
    }
    known_names = {entry.name.upper() for entry in bsa.entries}
    unknown = sorted(set(replacement_lookup) - known_names)
    if unknown:
        raise BSAError("원본 BSA에 없는 교체 파일: " + ", ".join(unknown))

    payloads: list[bytes] = []
    replaced: list[str] = []
    for entry in bsa.entries:
        replacement = replacement_lookup.get(entry.name.upper())
        if replacement is None:
            payloads.append(bsa.read(entry))
            continue
        data = replacement.read_bytes()
        if encode_inf and entry.name.upper().endswith(".INF"):
            data = crypt_inf(data)
        payloads.append(data)
        replaced.append(entry.name)

    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".tmp")
    try:
        with temp.open("wb") as stream:
            stream.write(struct.pack("<H", len(bsa.entries)))
            for payload in payloads:
                stream.write(payload)
            for entry, payload in zip(bsa.entries, payloads):
                name = validate_archive_name(entry.name)
                stream.write(name.ljust(NAME_SIZE, b"\0"))
                stream.write(struct.pack("<HI", entry.compressed, len(payload)))
        os.replace(temp, output)
    finally:
        if temp.exists():
            temp.unlink()

    rebuilt = ArenaBSA(output)
    if len(rebuilt.entries) != len(bsa.entries):
        raise BSAError("재구성한 BSA의 파일 수가 달라졌습니다.")
    print(f"BSA 재구성 완료: {output}")
    print(f"교체 파일: {len(replaced)}")
    for name in replaced:
        print(f"  {name}")
    print(f"sha256: {rebuilt.sha256()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TES Arena GLOBAL.BSA 도구")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("list", "verify"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("bsa", type=Path)

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("bsa", type=Path)
    extract_parser.add_argument("output", type=Path)
    extract_parser.add_argument("--decode-inf", action="store_true")

    rebuild_parser = subparsers.add_parser("rebuild")
    rebuild_parser.add_argument("bsa", type=Path)
    rebuild_parser.add_argument("replacements", type=Path)
    rebuild_parser.add_argument("output", type=Path)
    rebuild_parser.add_argument(
        "--encode-inf",
        action="store_true",
        help="교체 폴더의 평문 INF를 BSA용으로 암호화",
    )

    args = parser.parse_args(argv)
    try:
        bsa = ArenaBSA(args.bsa)
        if args.command == "list":
            command_list(bsa)
        elif args.command == "verify":
            command_verify(bsa)
        elif args.command == "extract":
            command_extract(bsa, args.output, args.decode_inf)
        else:
            command_rebuild(bsa, args.replacements, args.output, args.encode_inf)
    except (BSAError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

