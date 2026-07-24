#!/usr/bin/env python3
"""TEMPLATE 카탈로그 인덱스 기반 NPC 재번역을 ID 오버라이드로 변환한다."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re


TOKEN_RE = re.compile(r"%[A-Za-z0-9]+")
OPTIONAL_TOKENS = {"%doc", "%jok", "%oc", "%oth"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def tokens(text: str) -> Counter[str]:
    return Counter(TOKEN_RE.findall(text))


def variants(text: str) -> list[str]:
    return [part.strip() for part in text.split("&") if part.strip()]


def main() -> int:
    args = parse_args()
    catalog = [
        json.loads(line)
        for line in args.catalog.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    template = [row for row in catalog if row["container"] == "TEMPLATE.DAT"]
    spec = json.loads(args.source.read_text(encoding="utf-8"))
    output: dict[str, str] = {}
    errors: list[str] = []

    for index_text, item in spec["entries"].items():
        index = int(index_text)
        if not 0 <= index < len(template):
            errors.append(f"index={index}: 카탈로그 범위 밖")
            continue
        row = template[index]
        source = str(row["source"])
        if "variants" in item:
            translated_variants = item["variants"]
            if len(variants(source)) != len(translated_variants):
                errors.append(
                    f"index={index}: 문안 수 {len(variants(source))} "
                    f"!= {len(translated_variants)}"
                )
                continue
            translation = "&\n\n".join(translated_variants) + "&"
        else:
            translation = item["translation"]

        source_tokens = tokens(source)
        translated_tokens = tokens(translation)
        required_source = Counter({
            token: count for token, count in source_tokens.items()
            if token not in OPTIONAL_TOKENS
        })
        required_translation = Counter({
            token: count for token, count in translated_tokens.items()
            if token not in OPTIONAL_TOKENS
        })
        optional_ok = all(
            translated_tokens[token] <= source_tokens[token] for token in OPTIONAL_TOKENS
        )
        if required_source != required_translation or not optional_ok:
            errors.append(
                f"index={index}: 자리표시자 {dict(source_tokens)} "
                f"!= {dict(translated_tokens)}"
            )
            continue
        output[str(row["id"])] = translation

    if errors:
        raise SystemExit("검증 실패:\n" + "\n".join(errors))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"TEMPLATE NPC records: {len(output)}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
