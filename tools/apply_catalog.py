#!/usr/bin/env python3
"""Build AKC-encoded Arena replacement files from a translation catalog."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

from akc_codec import AKCError, encode as encode_akc
from arena_bsa import ArenaBSA, BSAError, command_rebuild, crypt_inf
from extract_catalog import (
    HASH_HEADER_RE,
    INF_TEXT_HEADER_RE,
    INF_SECTION_RE,
    PLACEHOLDER_RE,
    strip_inf_control_prefix,
)


class CatalogError(ValueError):
    pass


CUTSCENE_TEMPLATE_KEYS = {
    1294, 1295, 1296, 1297, 1298, 1299, 1300, 1301, 1302,
    1392, 1393, 1394, 1395, 1396, 1397, 1398, 1399,
    1400, 1402, 1403, 1404, 1405, 1406, 1407, 1447, 1500,
}

# These TEMPLATE.DAT macros expand to separate English procedural tables.
# A translation may deliberately omit them when the surrounding Korean line
# already carries the same meaning.  All names, locations, pronouns, numbers,
# and printf-style placeholders remain mandatory.
OPTIONAL_PROCEDURAL_TEMPLATE_TOKENS = {"%doc", "%jok", "%oc", "%oth"}


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def load_catalog(path: Path, overrides_path: Path | None) -> list[dict]:
    entries: list[dict] = []
    ids: set[str] = set()
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CatalogError(f"{path}:{line_number}: 잘못된 JSON") from exc
            entry_id = entry.get("id")
            if not isinstance(entry_id, str) or entry_id in ids:
                raise CatalogError(f"{path}:{line_number}: 없거나 중복된 ID")
            ids.add(entry_id)
            entries.append(entry)

    if overrides_path is not None:
        overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
        if not isinstance(overrides, dict):
            raise CatalogError("오버라이드 파일은 {ID: 번역문} JSON 객체여야 합니다.")
        by_id = {entry["id"]: entry for entry in entries}
        unknown = sorted(set(overrides) - set(by_id))
        if unknown:
            raise CatalogError("카탈로그에 없는 오버라이드 ID: " + ", ".join(unknown))
        for entry_id, translation in overrides.items():
            if not isinstance(translation, str):
                raise CatalogError(f"{entry_id}: 번역문은 문자열이어야 합니다.")
            by_id[entry_id]["translation"] = translation
    return entries


def validate_translation(entry: dict) -> None:
    source = entry["source"]
    translation = entry.get("translation", "")
    if not translation:
        return
    source_tokens = Counter(PLACEHOLDER_RE.findall(source))
    translation_tokens = Counter(PLACEHOLDER_RE.findall(translation))
    tokens_match = source_tokens == translation_tokens
    if not tokens_match and entry.get("container") == "TEMPLATE.DAT":
        optional_not_added = all(
            translation_tokens[token] <= source_tokens[token]
            for token in OPTIONAL_PROCEDURAL_TEMPLATE_TOKENS
        )
        required_source = Counter({
            token: count
            for token, count in source_tokens.items()
            if token not in OPTIONAL_PROCEDURAL_TEMPLATE_TOKENS
        })
        required_translation = Counter({
            token: count
            for token, count in translation_tokens.items()
            if token not in OPTIONAL_PROCEDURAL_TEMPLATE_TOKENS
        })
        tokens_match = optional_not_added and required_source == required_translation
    if not tokens_match:
        raise CatalogError(
            f"{entry['id']}: 자리표시자가 달라졌습니다. "
            f"원문={dict(source_tokens)}, 번역={dict(translation_tokens)}"
        )
    key_match = re.search(r"(?:^|;)key=(\d+)(?:;|$)", entry.get("locator", ""))
    if key_match and int(key_match.group(1)) in CUTSCENE_TEMPLATE_KEYS:
        source_lines = normalize_newlines(source).splitlines()
        translation_lines = normalize_newlines(translation).splitlines()
        if len(source_lines) != len(translation_lines):
            raise CatalogError(
                f"{entry['id']}: 컷신 행 수가 다릅니다. "
                f"원문={len(source_lines)}, 번역={len(translation_lines)}"
            )
    try:
        encode_akc(translation)
    except AKCError as exc:
        raise CatalogError(f"{entry['id']}: {exc}") from exc


def locator_values(locator: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for part in locator.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        values[key] = value
    return values


def translated(entry: dict) -> str | None:
    value = entry.get("translation", "")
    return normalize_newlines(value) if value else None


def build_nul_table(source_path: Path, entries: list[dict]) -> bytes:
    chunks = source_path.read_bytes().split(b"\0")
    for entry in entries:
        value = translated(entry)
        if value is None:
            continue
        index = int(locator_values(entry["locator"])["index"])
        if not 0 <= index < len(chunks):
            raise CatalogError(f"{entry['id']}: NUL 테이블 인덱스 범위 초과")
        original = normalize_newlines(chunks[index].decode("cp437"))
        if original != normalize_newlines(entry["source"]):
            raise CatalogError(f"{entry['id']}: 원본 NUL 문자열이 카탈로그와 다릅니다.")
        chunks[index] = encode_akc(value)
    return b"\0".join(chunks)


def split_records(text: str, header_re: re.Pattern[str]):
    matches = list(header_re.finditer(text))
    records = []
    for index, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        records.append((match, body_start, body_end))
    return records


def replace_record_body(text: str, start: int, end: int, value: str, keep_tilde: bool) -> str:
    original = text[start:end]
    leading_match = re.match(r"\n*", original)
    trailing_match = re.search(r"\n*$", original)
    leading = leading_match.group(0) if leading_match else ""
    trailing = trailing_match.group(0) if trailing_match else ""
    prefix = "~" if keep_tilde else ""
    return text[:start] + leading + prefix + value.rstrip("\n") + trailing + text[end:]


def pad_hash_record_value(original: str, value: str, newline: str, entry_id: str) -> str:
    """Keep the next hash-record header at its original byte offset.

    Arena's hash-record lookup retains the original body offsets. A shorter
    Korean record therefore makes a later key read from the middle of the
    following record. Put inert ASCII padding immediately after the final
    ``&`` terminator so the displayed text is unchanged while every following
    header remains at its retail offset.
    """
    leading_match = re.match(r"\n*", original)
    trailing_match = re.search(r"\n*$", original)
    leading = leading_match.group(0) if leading_match else ""
    trailing = trailing_match.group(0) if trailing_match else ""
    core = value.rstrip("\n")

    original_size = len(encode_akc(original.replace("\n", newline)))
    replacement = leading + core + trailing
    replacement_size = len(encode_akc(replacement.replace("\n", newline)))
    if replacement_size > original_size:
        raise CatalogError(
            f"{entry_id}: 해시 레코드 번역이 원본 영역보다 큽니다. "
            f"원본={original_size}바이트, 번역={replacement_size}바이트"
        )

    padding = original_size - replacement_size
    if not padding:
        return core
    terminator = core.rfind("&")
    insert_at = terminator + 1 if terminator >= 0 else len(core)
    padded = core[:insert_at] + (" " * padding) + core[insert_at:]
    final_size = len(
        encode_akc((leading + padded + trailing).replace("\n", newline))
    )
    if final_size != original_size:
        raise AssertionError((entry_id, original_size, final_size))
    return padded


def build_hash_file(source_path: Path, entries: list[dict]) -> bytes:
    raw = source_path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = normalize_newlines(raw.decode("cp437"))
    # Work backwards so offsets remain valid.
    changes: list[tuple[int, int, str]] = []
    records = split_records(text, HASH_HEADER_RE)
    for entry in entries:
        value = translated(entry)
        if value is None:
            continue
        loc = locator_values(entry["locator"])
        index = int(loc["record"])
        if not 0 <= index < len(records):
            raise CatalogError(f"{entry['id']}: 해시 레코드 인덱스 범위 초과")
        _, start, end = records[index]
        body = text[start:end].lstrip("\n").rstrip("\n")
        if normalize_newlines(body) != normalize_newlines(entry["source"]):
            raise CatalogError(f"{entry['id']}: 원본 해시 레코드가 카탈로그와 다릅니다.")
        original = text[start:end]
        padded_value = pad_hash_record_value(original, value, newline, entry["id"])
        changes.append((start, end, padded_value))
    for start, end, value in sorted(changes, reverse=True):
        text = replace_record_body(text, start, end, value, keep_tilde=False)
    output = encode_akc(text.replace("\n", newline))
    header_bytes_re = re.compile(br"(?m)^#([^\r\n]*)\r?$")
    source_headers = [
        (match.group(1), match.start()) for match in header_bytes_re.finditer(raw)
    ]
    output_headers = [
        (match.group(1), match.start()) for match in header_bytes_re.finditer(output)
    ]
    if len(output) != len(raw) or output_headers != source_headers:
        raise CatalogError(
            f"{source_path.name}: 해시 레코드의 원본 바이트 위치가 바뀌었습니다."
        )
    return output


def build_whole_file(source_path: Path, entries: list[dict]) -> bytes:
    if len(entries) != 1:
        raise CatalogError(f"{source_path.name}: whole-text 항목 수가 1이 아닙니다.")
    entry = entries[0]
    value = translated(entry)
    if value is None:
        return source_path.read_bytes()
    original = normalize_newlines(source_path.read_bytes().decode("cp437"))
    if original != normalize_newlines(entry["source"]):
        raise CatalogError(f"{entry['id']}: 원본 전체 텍스트가 카탈로그와 다릅니다.")
    return encode_akc(value)


def build_inf(plain_data: bytes, name: str, entries: list[dict]) -> bytes:
    text = normalize_newlines(plain_data.decode("cp437"))
    marker = re.search(r"(?mi)^@TEXT(?:[ \t].*)?$", text)
    if marker is None:
        raise CatalogError(f"{name}: @TEXT 섹션이 없습니다.")
    section_start = marker.end()
    section = text[section_start:]
    next_section = INF_SECTION_RE.search(section)
    translatable_section = (
        section[:next_section.start()] if next_section is not None else section
    )
    records = split_records(translatable_section, INF_TEXT_HEADER_RE)
    changes: list[tuple[int, int, str, bool]] = []
    for entry in entries:
        value = translated(entry)
        if value is None:
            continue
        loc = locator_values(entry["locator"])
        index = int(loc["block"])
        if not 0 <= index < len(records):
            raise CatalogError(f"{entry['id']}: INF 블록 인덱스 범위 초과")
        _, local_start, local_end = records[index]
        body = section[local_start:local_end]
        source = strip_inf_control_prefix(body)
        if normalize_newlines(source) != normalize_newlines(entry["source"]):
            raise CatalogError(f"{entry['id']}: 원본 INF 문장이 카탈로그와 다릅니다.")
        stripped = body.lstrip("\n")
        keep_tilde = stripped.startswith("~")
        changes.append((section_start + local_start, section_start + local_end, value, keep_tilde))
    for start, end, value, keep_tilde in sorted(changes, reverse=True):
        text = replace_record_body(text, start, end, value, keep_tilde)
    return encode_akc(text.replace("\n", "\r\n"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Arena 한국어 번역 재삽입기")
    parser.add_argument("--arena", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--overrides", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bsa-output", type=Path, required=True)
    parser.add_argument(
        "--bsa-base",
        type=Path,
        help="번역 INF를 덮을 BSA. 생략하면 --arena/GLOBAL.BSA를 사용합니다.",
    )
    args = parser.parse_args(argv)

    try:
        entries = load_catalog(args.catalog, args.overrides)
        for entry in entries:
            validate_translation(entry)
        changed = [entry for entry in entries if entry.get("translation", "")]
        grouped: dict[str, list[dict]] = defaultdict(list)
        for entry in changed:
            grouped[entry["container"]].append(entry)

        loose_dir = args.output / "loose"
        inf_dir = args.output / "inf-plain"
        loose_dir.mkdir(parents=True, exist_ok=True)
        inf_dir.mkdir(parents=True, exist_ok=True)
        bsa = ArenaBSA(args.arena / "GLOBAL.BSA")
        bsa_entries = {entry.name.upper(): entry for entry in bsa.entries}

        changed_loose = changed_inf = 0
        for container, container_entries in grouped.items():
            fmt = container_entries[0]["format"]
            if container.startswith("GLOBAL.BSA/"):
                name = container.split("/", 1)[1]
                bsa_entry = bsa_entries.get(name.upper())
                if bsa_entry is None:
                    raise CatalogError(f"BSA에 없는 파일: {name}")
                plain = crypt_inf(bsa.read(bsa_entry))
                output_data = build_inf(plain, name, container_entries)
                (inf_dir / name).write_bytes(output_data)
                changed_inf += 1
                continue

            source_path = args.arena / container
            if fmt == "nul-table":
                output_data = build_nul_table(source_path, container_entries)
            elif fmt == "hash-record":
                output_data = build_hash_file(source_path, container_entries)
            elif fmt == "whole-text":
                output_data = build_whole_file(source_path, container_entries)
            else:
                raise CatalogError(f"지원하지 않는 형식: {fmt}")
            (loose_dir / container).write_bytes(output_data)
            changed_loose += 1

        rebuild_bsa = ArenaBSA(args.bsa_base) if args.bsa_base else bsa
        command_rebuild(rebuild_bsa, inf_dir, args.bsa_output, encode_inf=True)
        print(f"translated entries: {len(changed)}")
        print(f"loose replacement files: {changed_loose}")
        print(f"INF replacement files: {changed_inf}")
        print(f"loose output: {loose_dir}")
    except (CatalogError, BSAError, AKCError, OSError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
