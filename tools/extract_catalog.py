#!/usr/bin/env python3
"""Extract translatable Arena strings to a UTF-8 JSON Lines catalog."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import sys

from arena_bsa import ArenaBSA, BSAError, crypt_inf


NULL_TABLES = (
    "ARTFACT1.DAT",
    "ARTFACT2.DAT",
    "EQUIP.DAT",
    "MUGUILD.DAT",
    "SELLING.DAT",
    "TAVERN.DAT",
)

HASH_RECORD_FILES = (
    "CITYTXT",
    "SPELLMKR.TXT",
    "TEMPLATE.DAT",
)

WHOLE_TEXT_FILES = (
    "CITYINTR",
    "DUNGEON.TXT",
    "QUESTION.TXT",
)

PLACEHOLDER_RE = re.compile(r"%[A-Za-z0-9]+|%%")
HASH_HEADER_RE = re.compile(r"(?m)^#([^\r\n]*)\r?$" )
INF_TEXT_HEADER_RE = re.compile(r"(?mi)^\*TEXT[ \t]+([^\r\n]+)\r?$" )
INF_SECTION_RE = re.compile(r"(?mi)^@[A-Z][A-Z0-9_]*(?:[ \t].*)?\r?$")


@dataclass
class CatalogEntry:
    id: str
    container: str
    format: str
    locator: str
    source: str
    translation: str
    placeholders: list[str]
    status: str


def decode_dos_text(data: bytes, path: str) -> str:
    try:
        return data.decode("cp437")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path}: CP437 텍스트 디코딩 실패") from exc


def make_entry(container: str, fmt: str, locator: str, source: str) -> CatalogEntry:
    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    digest = hashlib.sha1(f"{container}\0{locator}\0{normalized}".encode("utf-8")).hexdigest()[:12]
    return CatalogEntry(
        id=f"{container}:{locator}:{digest}",
        container=container,
        format=fmt,
        locator=locator,
        source=normalized,
        translation="",
        placeholders=sorted(set(PLACEHOLDER_RE.findall(normalized))),
        status="todo",
    )


def extract_null_table(path: Path) -> list[CatalogEntry]:
    data = path.read_bytes()
    chunks = data.split(b"\0")
    entries: list[CatalogEntry] = []
    for index, chunk in enumerate(chunks):
        if not chunk:
            continue
        source = decode_dos_text(chunk, str(path))
        if source.strip() in ("", "?"):
            continue
        entries.append(make_entry(path.name, "nul-table", f"index={index}", source))
    return entries


def split_by_headers(text: str, header_re: re.Pattern[str]):
    matches = list(header_re.finditer(text))
    for index, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[body_start:body_end].lstrip("\r\n").rstrip("\r\n")
        yield match.group(1).strip(), body


def extract_hash_records(path: Path) -> list[CatalogEntry]:
    text = decode_dos_text(path.read_bytes(), str(path))
    entries: list[CatalogEntry] = []
    for record_index, (key, body) in enumerate(split_by_headers(text, HASH_HEADER_RE)):
        if not body.strip():
            continue
        entries.append(make_entry(path.name, "hash-record", f"record={record_index};key={key}", body))
    return entries


def extract_whole_text(path: Path) -> list[CatalogEntry]:
    text = decode_dos_text(path.read_bytes(), str(path))
    return [make_entry(path.name, "whole-text", "file", text)]


def strip_inf_control_prefix(body: str) -> str:
    # '~' is an Arena display marker on the first prose character. Keep other
    # syntax intact so a translator can see riddle answers and formatting codes.
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and lines[0].startswith("~"):
        lines[0] = lines[0][1:]
    return "\n".join(lines).rstrip("\n")


def extract_inf(name: str, encrypted_data: bytes) -> list[CatalogEntry]:
    plaintext = crypt_inf(encrypted_data)
    text = decode_dos_text(plaintext, name)
    marker = re.search(r"(?mi)^@TEXT(?:[ \t].*)?\r?$", text)
    if marker is None:
        return []
    text_section = text[marker.end():]
    # INF files often place @SOUND and other executable sections directly
    # after the final prose block.  Those sections are data, not dialogue;
    # including them in a translation record corrupts filenames and numeric
    # parameters when a whole record is replaced.
    next_section = INF_SECTION_RE.search(text_section)
    if next_section is not None:
        text_section = text_section[:next_section.start()]
    entries: list[CatalogEntry] = []
    for block_index, (key, body) in enumerate(split_by_headers(text_section, INF_TEXT_HEADER_RE)):
        source = strip_inf_control_prefix(body)
        if not source.strip():
            continue
        # Numeric-only control blocks such as '+10' are not prose.
        if re.fullmatch(r"[+\-]?\d+", source.strip()):
            continue
        entries.append(
            make_entry(
                f"GLOBAL.BSA/{name}",
                "inf-text",
                f"block={block_index};key={key}",
                source,
            )
        )
    return entries


def extract_all(arena: Path) -> list[CatalogEntry]:
    entries: list[CatalogEntry] = []
    for filename in NULL_TABLES:
        path = arena / filename
        if path.is_file():
            entries.extend(extract_null_table(path))
    for filename in HASH_RECORD_FILES:
        path = arena / filename
        if path.is_file():
            entries.extend(extract_hash_records(path))
    for filename in WHOLE_TEXT_FILES:
        path = arena / filename
        if path.is_file():
            entries.extend(extract_whole_text(path))

    bsa = ArenaBSA(arena / "GLOBAL.BSA")
    for bsa_entry in bsa.entries:
        if bsa_entry.name.upper().endswith(".INF"):
            entries.extend(extract_inf(bsa_entry.name, bsa.read(bsa_entry)))
    return entries


def write_jsonl(path: Path, entries: list[CatalogEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for entry in entries:
            stream.write(json.dumps(asdict(entry), ensure_ascii=False, separators=(",", ":")))
            stream.write("\n")


def write_stats(path: Path, entries: list[CatalogEntry]) -> None:
    formats: dict[str, int] = {}
    containers: set[str] = set()
    source_characters = 0
    for entry in entries:
        formats[entry.format] = formats.get(entry.format, 0) + 1
        containers.add(entry.container)
        source_characters += len(entry.source)
    stats = {
        "entries": len(entries),
        "containers": len(containers),
        "source_characters": source_characters,
        "formats": dict(sorted(formats.items())),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TES Arena 번역 카탈로그 추출기")
    parser.add_argument("--arena", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        entries = extract_all(args.arena)
        ids = [entry.id for entry in entries]
        if len(ids) != len(set(ids)):
            raise ValueError("카탈로그 ID가 중복되었습니다.")
        write_jsonl(args.output, entries)
        write_stats(args.stats, entries)
    except (BSAError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"catalog entries: {len(entries)}")
    print(f"output: {args.output}")
    print(f"stats: {args.stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
