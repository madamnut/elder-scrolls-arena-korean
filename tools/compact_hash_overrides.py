#!/usr/bin/env python3
"""Compact oversized Korean hash records by removing distributed spaces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from akc_codec import encode as encode_akc


def encoded_size(text: str, newline: str, akc: bool) -> int:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)
    return len(encode_akc(normalized) if akc else normalized.encode("cp437"))


def is_hangul(char: str) -> bool:
    return "가" <= char <= "힣"


def candidate_spaces(text: str) -> list[int]:
    candidates: list[int] = []
    for index, char in enumerate(text):
        if char != " " or index == 0 or index + 1 >= len(text):
            continue
        before = text[index - 1]
        after = text[index + 1]
        if is_hangul(before) or is_hangul(after):
            candidates.append(index)
    return candidates


def distributed_selection(candidates: list[int], count: int) -> set[int]:
    if count > len(candidates):
        raise ValueError(f"줄일 공백 부족: 필요={count}, 후보={len(candidates)}")
    if count == 0:
        return set()
    # Select positions across the whole record instead of making one section
    # completely unspaced.  The draft remains readable enough for in-game QA.
    selected: set[int] = set()
    for step in range(count):
        position = ((2 * step + 1) * len(candidates)) // (2 * count)
        position = min(position, len(candidates) - 1)
        while position in selected:
            position += 1
            if position >= len(candidates):
                position = 0
        selected.add(position)
    return {candidates[position] for position in selected}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arena", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--overrides", type=Path, required=True)
    parser.add_argument("--fixes", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    catalog = [
        json.loads(line)
        for line in args.catalog.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    overrides = json.loads(args.overrides.read_text(encoding="utf-8"))
    output = dict(overrides)
    for path in args.fixes:
        fixes = json.loads(path.read_text(encoding="utf-8"))
        unknown = sorted(set(fixes) - set(output))
        if unknown:
            raise ValueError(f"{path}: 원본 오버라이드에 없는 ID: {', '.join(unknown)}")
        output.update(fixes)
    report: list[dict] = []

    for entry in catalog:
        if entry.get("format") != "hash-record" or entry["id"] not in output:
            continue
        raw = (args.arena / entry["container"]).read_bytes()
        newline = "\r\n" if b"\r\n" in raw else "\n"
        source_size = encoded_size(entry["source"], newline, akc=False)
        value = output[entry["id"]]
        translation_size = encoded_size(value, newline, akc=True)
        excess = translation_size - source_size
        if excess <= 0:
            continue
        candidates = candidate_spaces(value)
        selected = distributed_selection(candidates, excess)
        compacted = "".join(
            char for index, char in enumerate(value) if index not in selected
        )
        compacted_size = encoded_size(compacted, newline, akc=True)
        if compacted_size != source_size:
            raise AssertionError((entry["id"], source_size, compacted_size))
        output[entry["id"]] = compacted
        report.append({
            "id": entry["id"],
            "container": entry["container"],
            "source_bytes": source_size,
            "draft_bytes": translation_size,
            "removed_spaces": excess,
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"compacted entries: {len(report)}")
    print(f"removed spaces: {sum(item['removed_spaces'] for item in report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
