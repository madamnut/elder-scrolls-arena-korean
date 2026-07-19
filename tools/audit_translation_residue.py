#!/usr/bin/env python3
"""Classify Roman-letter residue in finalized Arena translations."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")
PLACEHOLDER_RE = re.compile(r"%[A-Za-z]+")
CLASS_NAMES = {
    "Mage", "Spellsword", "Battlemage", "Sorceror", "Healer", "Nightblade",
    "Bard", "Burglar", "Rogue", "Acrobat", "Thief", "Assassin", "Monk",
    "Archer", "Ranger", "Barbarian", "Warrior", "Knight",
}


def classify(entry_id: str, line: str, token: str) -> str:
    stripped = line.strip()
    if token in CLASS_NAMES:
        return "intentional_class_name"
    if entry_id.startswith("CITYINTR:") and stripped.startswith("["):
        return "city_section_identifier"
    if ".INF:" in entry_id and stripped.startswith(":"):
        return "riddle_input_answer"
    if token.upper() in {"CORRECT", "WRONG"}:
        return "engine_marker"
    if len(token) == 1 or token.isupper() or re.fullmatch(r"[IVXLCDM]+", token):
        return "map_or_puzzle_code"
    if token in {"x'", "X'", "SW'"}:
        return "map_or_puzzle_code"
    return "review"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overrides", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()

    overrides = json.loads(args.overrides.read_text(encoding="utf-8"))
    counts: Counter[str] = Counter()
    rows: list[dict[str, str]] = []
    for entry_id, translation in overrides.items():
        for line_number, original_line in enumerate(translation.splitlines(), 1):
            line = PLACEHOLDER_RE.sub("", original_line)
            for token in TOKEN_RE.findall(line):
                category = classify(entry_id, line, token)
                counts[category] += 1
                rows.append({
                    "category": category,
                    "id": entry_id,
                    "line": str(line_number),
                    "token": token,
                    "text": original_line,
                })

    report = {
        "overrides": len(overrides),
        "counts": dict(sorted(counts.items())),
        "review": [row for row in rows if row["category"] == "review"],
        "all": rows,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# 번역 잔존 영문 감사",
        "",
        "완성 오버라이드에서 자리표시자를 제외한 로마자를 용도별로 분류한 결과다.",
        "",
        "| 분류 | 토큰 수 |",
        "|---|---:|",
    ]
    labels = {
        "intentional_class_name": "합의에 따라 유지한 직업명",
        "city_section_identifier": "CITYINTR 내부 도시 식별자",
        "riddle_input_answer": "엔진이 비교하는 영문 수수께끼 정답",
        "engine_marker": "INF 엔진 분기 표식",
        "map_or_puzzle_code": "지도·퍼즐 문자 코드",
        "review": "사람이 재검토할 표시 문자열",
    }
    for key in labels:
        lines.append(f"| {labels[key]} | {counts[key]:,} |")
    lines.extend(["", "## 사람이 재검토할 항목", ""])
    review = report["review"]
    if review:
        for row in review:
            lines.append(
                f"- `{row['id']}` {row['line']}행: `{row['token']}` — {row['text']}"
            )
    else:
        lines.append("- 없음")
    lines.extend([
        "",
        "수수께끼 정답과 내부 식별자는 화면 문장 번역 누락이 아니다. 해당 값을 번역하면 원본 엔진의 비교·조회가 실패할 수 있다.",
        "",
    ])
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text("\n".join(lines), encoding="utf-8")
    print("residue: " + ", ".join(f"{key}={counts[key]}" for key in labels))
    return 1 if review else 0


if __name__ == "__main__":
    raise SystemExit(main())
