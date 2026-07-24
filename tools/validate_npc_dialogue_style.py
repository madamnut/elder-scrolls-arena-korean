#!/usr/bin/env python3
"""Validate NPC role metadata and first/repeat dialogue revoice overrides."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re


KEY_RE = re.compile(r"(?:^|;)key=([0-9A-Fa-f]+)(?::|;|$)")
PLACEHOLDER_RE = re.compile(r"%[A-Za-z0-9]+|%%")
EXPECTED_KEYS = {f"{key:04d}" for key in range(100, 130)}


def variants(text: str) -> list[str]:
    return [part.strip() for part in text.split("&") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--style", type=Path, required=True)
    parser.add_argument("--overrides", type=Path, required=True)
    args = parser.parse_args()

    catalog: dict[str, dict] = {}
    for line in args.catalog.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("container") != "TEMPLATE.DAT":
            continue
        match = KEY_RE.search(entry["id"])
        if match:
            catalog[match.group(1).zfill(4)] = entry

    style = json.loads(args.style.read_text(encoding="utf-8"))["records"]
    overrides = json.loads(args.overrides.read_text(encoding="utf-8"))
    by_key: dict[str, tuple[str, str]] = {}
    for entry_id, translation in overrides.items():
        match = KEY_RE.search(entry_id)
        if not match:
            raise ValueError(f"TEMPLATE 키가 없는 오버라이드 ID: {entry_id}")
        key = match.group(1).zfill(4)
        if key in by_key:
            raise ValueError(f"중복 TEMPLATE 키: {key}")
        by_key[key] = (entry_id, translation)

    missing_style = sorted(EXPECTED_KEYS - set(style))
    missing_override = sorted(EXPECTED_KEYS - set(by_key))
    extra_override = sorted(set(by_key) - EXPECTED_KEYS)
    if missing_style or missing_override or extra_override:
        raise ValueError(
            f"키 불일치: style 누락={missing_style}, override 누락={missing_override}, "
            f"override 초과={extra_override}"
        )

    total_variants = 0
    for key in sorted(EXPECTED_KEYS):
        source = catalog[key]["source"]
        entry_id, translation = by_key[key]
        source_variants = variants(source)
        translated_variants = variants(translation)
        tones = style[key]["tones"]
        if len(source_variants) != len(translated_variants):
            raise ValueError(
                f"{key}: 변형 수 불일치 원문={len(source_variants)} "
                f"번역={len(translated_variants)}"
            )
        if len(tones) != len(source_variants):
            raise ValueError(
                f"{key}: 태도 수 불일치 원문={len(source_variants)} 태도={len(tones)}"
            )
        source_tokens = Counter(PLACEHOLDER_RE.findall(source))
        translated_tokens = Counter(PLACEHOLDER_RE.findall(translation))
        optional = {"%doc", "%jok", "%oc", "%oth"}
        for token in optional:
            source_tokens.pop(token, None)
            translated_tokens.pop(token, None)
        if source_tokens != translated_tokens:
            raise ValueError(
                f"{key}: 자리표시자 불일치 원문={dict(source_tokens)} "
                f"번역={dict(translated_tokens)} ({entry_id})"
            )
        total_variants += len(source_variants)

    print(f"NPC dialogue keys: {len(EXPECTED_KEYS)}")
    print(f"NPC dialogue variants: {total_variants}")
    print("style metadata, variant counts, and placeholders: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
