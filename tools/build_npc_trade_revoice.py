#!/usr/bin/env python3
"""인덱스 기반 상점 NPC 재번역을 카탈로그 ID 기반 오버라이드로 변환한다."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re


TOKEN_RE = re.compile(r"%[A-Za-z0-9]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def load_catalog(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def tokens(text: str) -> Counter[str]:
    return Counter(TOKEN_RE.findall(text))


def main() -> int:
    args = parse_args()
    catalog = load_catalog(args.catalog)
    spec = json.loads(args.source.read_text(encoding="utf-8"))
    output: dict[str, str] = {}
    errors: list[str] = []

    for container, translations in spec["containers"].items():
        records = [row for row in catalog if row["container"] == container]
        if len(records) != len(translations):
            raise SystemExit(
                f"{container}: 원문 {len(records)}개, 번역 {len(translations)}개"
            )
        for index, (record, translation) in enumerate(zip(records, translations)):
            source_tokens = tokens(str(record["source"]))
            translated_tokens = tokens(translation)
            if source_tokens != translated_tokens:
                errors.append(
                    f"{container} index={index}: {dict(source_tokens)} "
                    f"!= {dict(translated_tokens)}"
                )
                continue
            output[str(record["id"])] = translation

    if errors:
        raise SystemExit("자리표시자 불일치:\n" + "\n".join(errors))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"containers: {len(spec['containers'])}")
    print(f"dialogue records: {len(output)}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
