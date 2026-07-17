#!/usr/bin/env python3
"""Generate the scene-by-scene Korean cutscene dialogue reference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


SCENES = (
    (1400, "새 게임 시작 — 리아 실메인", "캐릭터 생성 완료", "VISION.FLC", "VISION.XMI (0x809A)", "고정"),
    (1500, "첫 본편 꿈 — 혼돈의 지팡이", "첫 본편 꿈에서 [0x01AA]=1", "CHAOSVSN.FLC", "VISION.XMI (0x809A)", "고정"),
    (1294, "리아 진행 꿈 P=0 — 팽 레어", "P=[0x0F77]=0", "VISION.FLC", "VISION.XMI (0x809A)", "1294+P"),
    (1295, "리아 진행 꿈 P=1 — 라비린시안", "P=[0x0F77]=1", "VISION.FLC", "VISION.XMI (0x809A)", "1294+P"),
    (1296, "리아 진행 꿈 P=2 — 엘든 그로브", "P=[0x0F77]=2", "VISION.FLC", "VISION.XMI (0x809A)", "1294+P"),
    (1297, "리아 진행 꿈 P=3 — 콜로서스의 전당", "P=[0x0F77]=3", "VISION.FLC", "VISION.XMI (0x809A)", "1294+P"),
    (1298, "리아 진행 꿈 P=4 — 수정탑", "P=[0x0F77]=4", "VISION.FLC", "VISION.XMI (0x809A)", "1294+P"),
    (1299, "리아 진행 꿈 P=5 — 하츠 묘지", "P=[0x0F77]=5", "VISION.FLC", "VISION.XMI (0x809A)", "1294+P"),
    (1300, "리아 진행 꿈 P=6 — 머크우드", "P=[0x0F77]=6", "VISION.FLC", "VISION.XMI (0x809A)", "1294+P"),
    (1301, "리아 진행 꿈 P=7 — 다고스 우르", "P=[0x0F77]=7", "VISION.FLC", "VISION.XMI (0x809A)", "1294+P"),
    (1302, "리아 진행 꿈 P=8 — 불의 보석과 제국 궁전", "P=[0x0F77]=8", "VISION.FLC", "VISION.XMI (0x809A)", "1294+P"),
    (1392, "제이거 탄 방해 P=1", "P=[0x0F77]=1", "JAGAR.FLC", "VISION.XMI (0x80A5)", "1391+P"),
    (1393, "제이거 탄 방해 P=2", "P=[0x0F77]=2", "JAGAR.FLC", "VISION.XMI (0x80A5)", "1391+P"),
    (1394, "제이거 탄 방해 P=3", "P=[0x0F77]=3", "JAGAR.FLC", "VISION.XMI (0x80A5)", "1391+P"),
    (1395, "제이거 탄 방해 P=4", "P=[0x0F77]=4", "JAGAR.FLC", "VISION.XMI (0x80A5)", "1391+P"),
    (1396, "제이거 탄 방해 P=5", "P=[0x0F77]=5", "JAGAR.FLC", "VISION.XMI (0x80A5)", "1391+P"),
    (1397, "제이거 탄 방해 P=6", "P=[0x0F77]=6", "JAGAR.FLC", "VISION.XMI (0x80A5)", "1391+P"),
    (1398, "제이거 탄 방해 P=7", "P=[0x0F77]=7", "JAGAR.FLC", "VISION.XMI (0x80A5)", "1391+P"),
    (1399, "제이거 탄 방해 P=8", "P=[0x0F77]=8", "JAGAR.FLC", "VISION.XMI (0x80A5)", "1391+P"),
    (1402, "P=0 사망 — 리아 실메인", "P=[0x0F77]=0에서 사망; 원본 새 게임·첫 조각 전 도달 확인", "VISION.FLC", "VISION.XMI (0x809A)", "고정"),
    (1403, "P=1~8 사망 — 제이거 탄", "1<=P=[0x0F77]<=8에서 사망; 첫 조각 전에는 호출되지 않음", "JAGAR.FLC", "VISION.XMI (0x80A5)", "고정"),
)

KEY_RE = re.compile(r"(?:^|;)key=(\d+)(?:;|$)")
PLACEHOLDER_RE = re.compile(r"%[A-Za-z0-9]+|%%")
def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def load_json(path: Path) -> dict[str, str]:
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError(f"{path}: JSON 객체가 아닙니다.")
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in values.items()):
        raise ValueError(f"{path}: 모든 ID와 번역문은 문자열이어야 합니다.")
    return values


def key_from_id(entry_id: str) -> int | None:
    match = re.search(r";key=(\d+):", entry_id)
    return int(match.group(1)) if match else None


def catalog_by_key(path: Path) -> dict[int, dict]:
    result: dict[int, dict] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("container") != "TEMPLATE.DAT":
            continue
        match = KEY_RE.search(entry.get("locator", ""))
        if match is None:
            continue
        key = int(match.group(1))
        if key in result:
            raise ValueError(f"{path}:{line_number}: TEMPLATE 키 {key} 중복")
        result[key] = entry
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="장면별 컷신 대사 문서 생성")
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--stable", required=True, type=Path)
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--active", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    stable = load_json(args.stable)
    staging = load_json(args.staging)
    active_values = json.loads(args.active.read_text(encoding="utf-8"))
    if not isinstance(active_values, list) or any(not isinstance(value, int) for value in active_values):
        raise ValueError(f"{args.active}: TEMPLATE 키 정수 배열이 아닙니다.")
    active = set(active_values)
    if len(active) != len(active_values):
        raise ValueError(f"{args.active}: 중복 TEMPLATE 키가 있습니다.")
    overlap = sorted(set(stable).intersection(staging))
    if overlap:
        raise ValueError("안정·시험 번역 ID 중복: " + ", ".join(overlap))

    translations: dict[int, tuple[str, str, str]] = {}
    staging_keys: set[int] = set()
    for status, values in (("실기 통과·기본 빌드", stable), ("시험 대기·기본 빌드 제외", staging)):
        for entry_id, text in values.items():
            key = key_from_id(entry_id)
            if key is not None:
                translations[key] = (status, entry_id, normalize(text))
                if values is staging:
                    staging_keys.add(key)

    unknown_active = sorted(active - staging_keys)
    if unknown_active:
        raise ValueError("시험 대기 번역에 없는 활성 키: " + ", ".join(map(str, unknown_active)))

    catalog = catalog_by_key(args.catalog)
    lines = [
        "# 장면별 컷신 대사",
        "",
        "이 문서는 번역 JSON에서 자동 생성한다. 대사를 수정한 뒤 생성 명령을 다시 실행하며, 이 파일만 직접 고치지 않는다.",
        "",
        "- `&`는 원문 레코드의 종료 표식이므로 삭제하지 않는다.",
        "- `%pcf`, `%pcn`은 플레이어 이름·성별형 치환자이므로 위치와 개수를 유지한다.",
        "- 원문 영어 전문은 공개 문서에 중복하지 않는다. 대신 카탈로그 ID, 원문 행 수와 SHA 기반 ID를 기록한다.",
        "- 현재 기본 실행본에는 `실기 통과·기본 빌드` 장면만 들어간다.",
        "",
    ]

    for key, title, condition, flc, xmi, formula in SCENES:
        if key not in catalog:
            raise ValueError(f"카탈로그에 TEMPLATE 키 {key}가 없습니다.")
        if key not in translations:
            raise ValueError(f"번역 파일에 TEMPLATE 키 {key}가 없습니다.")
        entry = catalog[key]
        status, entry_id, translation = translations[key]
        if key in active:
            status = "현재 ARENA_KR 단일 시험 배치·기본 빌드 제외"
        if entry_id != entry["id"]:
            raise ValueError(f"키 {key}: 번역 ID와 카탈로그 ID가 다릅니다.")
        source = normalize(entry["source"])
        source_lines = len(source.split("\n"))
        translation_lines = len(translation.split("\n"))
        if source_lines != translation_lines:
            raise ValueError(
                f"키 {key}: 원문 {source_lines}행과 한국어 {translation_lines}행이 다릅니다."
            )
        if source.rstrip().endswith("&") != translation.rstrip().endswith("&"):
            raise ValueError(f"키 {key}: 종료 표식 & 보존 상태가 다릅니다.")
        if PLACEHOLDER_RE.findall(source) != PLACEHOLDER_RE.findall(translation):
            raise ValueError(f"키 {key}: 자리표시자의 종류·개수·순서가 다릅니다.")
        placeholders = ", ".join(entry.get("placeholders", [])) or "없음"
        lines.extend(
            [
                f"## {title}",
                "",
                f"- 템플릿 키: `{key}` (`{formula}`)",
                f"- 발동 조건: {condition}",
                f"- 영상: `{flc}`",
                f"- 음악: `{xmi}`",
                f"- 상태: **{status}**",
                f"- 원문 검증 ID: `{entry_id}`",
                f"- 행 수: 원문 {source_lines} / 한국어 {translation_lines}",
                f"- 자리표시자: {placeholders}",
                "",
                "```text",
                translation,
                "```",
                "",
            ]
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"scenes: {len(SCENES)}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
