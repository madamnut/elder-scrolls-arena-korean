#!/usr/bin/env python3
"""Merge disjoint UTF-8 translation override objects for a staged build."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


TEMPLATE_KEY_RE = re.compile(r";key=(\d+):")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="검증 완료·시험 중 번역 오버라이드 JSON 병합"
    )
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--staged-template-key",
        action="append",
        type=int,
        default=[],
        help="첫 입력은 전부 유지하고 이후 입력에서는 지정한 TEMPLATE 키만 병합",
    )
    parser.add_argument(
        "--only-template-key",
        action="append",
        type=int,
        default=[],
        help="모든 입력에서 지정한 TEMPLATE 키만 병합; A/B 격리 시험용",
    )
    args = parser.parse_args()

    merged: dict[str, str] = {}
    selected = set(args.staged_template_key)
    found: set[int] = set()
    only_selected = set(args.only_template_key)
    only_found: set[int] = set()
    for input_index, path in enumerate(args.inputs):
        values = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            raise ValueError(f"{path}: JSON 객체가 아닙니다.")
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in values.items()):
            raise ValueError(f"{path}: 모든 ID와 번역문은 문자열이어야 합니다.")
        if only_selected:
            filtered: dict[str, str] = {}
            for key, value in values.items():
                match = TEMPLATE_KEY_RE.search(key)
                if match is None:
                    continue
                template_key = int(match.group(1))
                if template_key in only_selected:
                    filtered[key] = value
                    only_found.add(template_key)
            values = filtered
        if selected and input_index > 0:
            filtered: dict[str, str] = {}
            for key, value in values.items():
                match = TEMPLATE_KEY_RE.search(key)
                if match is None:
                    continue
                template_key = int(match.group(1))
                if template_key in selected:
                    filtered[key] = value
                    found.add(template_key)
            values = filtered
        duplicate = sorted(set(merged).intersection(values))
        if duplicate:
            raise ValueError(f"{path}: 중복 ID: {', '.join(duplicate)}")
        merged.update(values)

    missing = sorted(selected - found)
    if missing:
        raise ValueError("시험 입력에서 찾지 못한 TEMPLATE 키: " + ", ".join(map(str, missing)))
    only_missing = sorted(only_selected - only_found)
    if only_missing:
        raise ValueError("전체 입력에서 찾지 못한 TEMPLATE 키: " + ", ".join(map(str, only_missing)))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"merged entries: {len(merged)}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
