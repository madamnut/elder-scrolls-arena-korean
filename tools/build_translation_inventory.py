#!/usr/bin/env python3
"""Summarize Arena translation coverage without touching game data."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re


WORD_RE = re.compile(r"[A-Za-z]")
EXTERNAL_CONTAINERS = {"QUESTION.TXT"}


def load_catalog(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_overrides(paths: list[Path]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            merged.update(data)
    return merged


def classify(entry: dict, overrides: dict[str, str]) -> str:
    if entry["id"] in overrides:
        return "translated"
    if entry["container"] in EXTERNAL_CONTAINERS:
        return "external"
    if not WORD_RE.search(entry["source"]):
        return "nonlinguistic"
    return "todo"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--overrides", type=Path, action="append", default=[])
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()

    catalog = load_catalog(args.catalog)
    overrides = load_overrides(args.overrides)
    known_ids = {entry["id"] for entry in catalog}
    unknown = sorted(set(overrides) - known_ids)
    if unknown:
        raise ValueError("카탈로그에 없는 번역 ID: " + ", ".join(unknown))

    status_counts: Counter[str] = Counter()
    by_container: dict[str, Counter[str]] = defaultdict(Counter)
    source_characters: Counter[str] = Counter()
    for entry in catalog:
        status = classify(entry, overrides)
        status_counts[status] += 1
        by_container[entry["container"]][status] += 1
        source_characters[status] += len(entry["source"])

    report = {
        "entries": len(catalog),
        "status": dict(sorted(status_counts.items())),
        "source_characters": dict(sorted(source_characters.items())),
        "containers": {
            name: dict(sorted(counts.items()))
            for name, counts in sorted(by_container.items())
        },
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# 전체 번역 진행 현황",
        "",
        "이 문서는 원본 데이터에서 다시 추출한 카탈로그와 번역 오버라이드를 대조해 생성한다.",
        "",
        "## 전체 집계",
        "",
        "| 상태 | 항목 수 | 원문 문자 수 |",
        "|---|---:|---:|",
    ]
    labels = {
        "translated": "번역 적용",
        "todo": "번역 필요",
        "external": "별도 파일로 처리",
        "nonlinguistic": "비언어 제어값",
    }
    for status in ("translated", "todo", "external", "nonlinguistic"):
        lines.append(
            f"| {labels[status]} | {status_counts[status]:,} | "
            f"{source_characters[status]:,} |"
        )
    lines.extend([
        "",
        "## 파일별 집계",
        "",
        "| 원본 컨테이너 | 전체 | 번역 | 필요 | 별도 | 제어값 |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for name, counts in sorted(
        by_container.items(),
        key=lambda item: (-item[1]["todo"], item[0]),
    ):
        total = sum(counts.values())
        lines.append(
            f"| `{name}` | {total:,} | {counts['translated']:,} | "
            f"{counts['todo']:,} | {counts['external']:,} | "
            f"{counts['nonlinguistic']:,} |"
        )
    lines.extend([
        "",
        "## 상태 기준",
        "",
        "- 번역 적용: 현재 오버라이드에 ID가 존재한다.",
        "- 번역 필요: 실제 영문 문장이며 아직 오버라이드가 없다.",
        "- 별도 파일로 처리: `QUESTION.TXT`처럼 전용 빌더가 완성본을 만든다.",
        "- 비언어 제어값: `!`처럼 번역할 문장이 아닌 값이다.",
        "",
    ])
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text("\n".join(lines), encoding="utf-8")
    print(f"catalog entries: {len(catalog)}")
    print("status: " + ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
