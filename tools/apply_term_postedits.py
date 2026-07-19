#!/usr/bin/env python3
"""Apply reviewed phrase replacements to a translation override object."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


INF_CONTROL_RE = re.compile(r"^(?:\^[0-9]+(?:[ \t]+[0-9]+)?|:[^\r\n]*|[`'](?:CORRECT|WRONG)|-)$", re.I)
PLACEHOLDER_RE = re.compile(r"(%[A-Za-z0-9]+|%%)")


def replace_terms(text: str, terms: list[tuple[str, str]]) -> str:
    parts = PLACEHOLDER_RE.split(text)
    for index in range(0, len(parts), 2):
        prose = parts[index]
        for source, target in terms:
            pattern = re.compile(
                rf"(?<![A-Za-z]){re.escape(source)}(?![A-Za-z])",
                re.IGNORECASE,
            )
            prose = pattern.sub(target, prose)
        parts[index] = prose
    return "".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--overrides", type=Path, required=True)
    parser.add_argument("--terms", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    catalog = {
        entry["id"]: entry
        for entry in (
            json.loads(line)
            for line in args.catalog.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    overrides = json.loads(args.overrides.read_text(encoding="utf-8"))
    term_object = json.loads(args.terms.read_text(encoding="utf-8"))
    terms = sorted(term_object.items(), key=lambda item: -len(item[0]))
    output: dict[str, str] = {}
    changed = 0

    for entry_id, value in overrides.items():
        entry = catalog[entry_id]
        lines: list[str] = []
        for line in value.split("\n"):
            stripped = line.strip()
            protected = (
                entry["format"] == "inf-text" and INF_CONTROL_RE.fullmatch(stripped)
            ) or (
                entry["container"] == "CITYINTR"
                and stripped.startswith("[")
                and stripped.endswith("]")
            )
            lines.append(line if protected else replace_terms(line, terms))
        replacement = "\n".join(lines)
        output[entry_id] = replacement
        changed += replacement != value

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"post-edited entries: {changed}")
    print(f"terms: {len(terms)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
