#!/usr/bin/env python3
"""NPC 직접 발화 범위와 재번역 상태를 카탈로그에서 계산한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--scope", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def variant_count(text: str) -> int:
    parts = [part.strip() for part in text.split("&")]
    return len([part for part in parts if part]) or 1


def main() -> int:
    args = parse_args()
    rows = [
        json.loads(line)
        for line in args.catalog.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    scope = json.loads(args.scope.read_text(encoding="utf-8"))
    selected: list[tuple[dict[str, object], str, str]] = []

    for item in scope["whole_containers"]:
        matches = [row for row in rows if row["container"] == item["container"]]
        excluded_prefix = item.get("exclude_source_prefix")
        if excluded_prefix:
            matches = [
                row for row in matches
                if not str(row["source"]).startswith(excluded_prefix)
            ]
        selected.extend((row, item["category"], item["status"]) for row in matches)

    template = [row for row in rows if row["container"] == "TEMPLATE.DAT"]
    for item in scope["template_catalog_index_ranges"]:
        for index in range(item["start"], item["end"] + 1):
            if not 0 <= index < len(template):
                raise SystemExit(f"TEMPLATE catalog index={index}가 카탈로그에 없음")
            selected.append((template[index], item["category"], item["status"]))

    ids = [str(row["id"]) for row, _, _ in selected]
    if len(ids) != len(set(ids)):
        raise SystemExit("NPC 범위에 중복 레코드가 있음")

    groups: dict[tuple[str, str], dict[str, int]] = {}
    for row, category, status in selected:
        key = (category, status)
        group = groups.setdefault(key, {"records": 0, "variants": 0})
        group["records"] += 1
        group["variants"] += variant_count(str(row["source"]))

    total_records = len(selected)
    total_variants = sum(variant_count(str(row["source"])) for row, _, _ in selected)
    lines = [
        "# NPC 대사 범위",
        "",
        "이 문서는 `translations/npc-dialogue-scope.json`에서 자동 계산된다.",
        "직접 발화와 그 조립 문구만 포함하며 환경 서술·일지·시스템 안내는 제외한다.",
        "",
        f"- 전체 레코드: {total_records:,}개",
        f"- 전체 무작위 문안: {total_variants:,}개",
        "",
        "| 범주 | 상태 | 레코드 | 문안 |",
        "|---|---:|---:|---:|",
    ]
    for (category, status), counts in groups.items():
        lines.append(
            f"| {category} | {status} | {counts['records']:,} | {counts['variants']:,} |"
        )
    lines.extend([
        "",
        "상태 의미: `revoiced`는 화법별 재번역 완료, `reviewed`는 앞선 실기 검토 완료, "
        "`draft`는 전체 초벌 번역만 적용되어 화자별 재번역이 남았음을 뜻한다.",
        "",
    ])
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"NPC dialogue records: {total_records}")
    print(f"NPC dialogue variants: {total_variants}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
