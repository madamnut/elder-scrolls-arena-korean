#!/usr/bin/env python3
"""Build a placeholder-safe Korean machine-translation draft.

This is a first-pass drafting tool.  It never edits retail files.  The output
is an ID-to-text override object that still has to pass apply_catalog.py and
in-game review.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import unicodedata
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from akc_codec import encode as encode_akc


PLACEHOLDER_RE = re.compile(r"%[A-Za-z0-9]+|%%")
INF_CONTROL_RE = re.compile(r"^(?:\^[0-9]+(?:[ \t]+[0-9]+)?|:[^\r\n]*|[`'](?:CORRECT|WRONG))$", re.I)
NONLINGUISTIC_RE = re.compile(r"^[^A-Za-z]*$")
SECTION_HEADER_RE = re.compile(r"(?m)^[ \t]*\[[^\r\n]+\][ \t]*$")
ALLOWED_ASCII = {chr(value) for value in range(0x09, 0x0E)} | {
    chr(value) for value in range(0x20, 0x80)
}
PUNCTUATION_MAP = str.maketrans({
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "-",
    "…": "...",
    " ": " ",
    "·": "/",
    "​": "",
    "⁠": "",
    "﻿": "",
})


class DraftError(ValueError):
    pass


class Translator:
    def __init__(
        self,
        endpoint: str,
        glossary: dict[str, str],
        cache_path: Path,
        timeout: float,
    ) -> None:
        self.endpoint = endpoint
        self.glossary = sorted(glossary.items(), key=lambda item: -len(item[0]))
        self.cache_path = cache_path
        self.timeout = timeout
        self.lock = threading.Lock()
        self.glossary_key = hashlib.sha1(
            json.dumps(glossary, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        if cache_path.is_file():
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            self.cache = data if isinstance(data, dict) else {}
        else:
            self.cache: dict[str, str] = {}

    def save_cache(self) -> None:
        with self.lock:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(self.cache, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.cache_path)

    def _protect(self, text: str) -> tuple[str, dict[str, str]]:
        replacements: dict[str, str] = {}
        serial = 0

        def marker(value: str) -> str:
            nonlocal serial
            token = f"ZXQ{serial:04d}QXZ"
            serial += 1
            replacements[token] = value
            return token

        protected = PLACEHOLDER_RE.sub(lambda match: marker(match.group(0)), text)
        for source, target in self.glossary:
            pattern = re.compile(
                rf"(?<![A-Za-z]){re.escape(source)}(?![A-Za-z])",
                re.IGNORECASE,
            )
            protected = pattern.sub(lambda _match, value=target: marker(value), protected)
        return protected, replacements

    def _request(self, text: str) -> str:
        query = urlencode({
            "client": "gtx",
            "sl": "en",
            "tl": "ko",
            "dt": "t",
            "q": text,
        })
        request = Request(
            f"{self.endpoint}?{query}",
            headers={"User-Agent": "Arena-Korean-Draft/0.1"},
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        try:
            return "".join(part[0] for part in payload[0] if part and part[0])
        except (IndexError, TypeError) as exc:
            raise DraftError("번역 서비스 응답 형식이 예상과 다릅니다.") from exc

    def translate(self, text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text.strip())
        if not text or NONLINGUISTIC_RE.fullmatch(text):
            return text
        key = self.glossary_key + ":" + hashlib.sha1(text.encode("utf-8")).hexdigest()
        with self.lock:
            cached = self.cache.get(key)
        if cached is not None:
            return cached

        protected, replacements = self._protect(text)
        last_error: Exception | None = None
        for attempt in range(5):
            try:
                translated = self._request(protected)
                for token, value in replacements.items():
                    if translated.count(token) != protected.count(token):
                        raise DraftError(f"보호 토큰 유실: {token}")
                    translated = translated.replace(token, value)
                translated = normalize_output(translated)
                encode_akc(translated)
                with self.lock:
                    self.cache[key] = translated
                return translated
            except Exception as exc:  # network errors are retried with backoff
                last_error = exc
                time.sleep(1.0 * (attempt + 1))
        raise DraftError(f"번역 요청 5회 실패: {last_error}")


def normalize_output(text: str) -> str:
    text = unicodedata.normalize("NFC", text).translate(PUNCTUATION_MAP)
    text = re.sub(r"[ \t]+", " ", text).strip()
    unsupported = sorted({
        char
        for char in text
        if char not in ALLOWED_ASCII and not ("가" <= char <= "힣")
    })
    if unsupported:
        rendered = ", ".join(f"U+{ord(char):04X} {char!r}" for char in unsupported)
        raise DraftError("AKC 비지원 문자: " + rendered)
    return text


def split_long(text: str, limit: int = 3000) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text]
    pieces: list[str] = []
    while len(text) > limit:
        candidates = [
            text.rfind(mark, 0, limit)
            for mark in (". ", "? ", "! ", "; ", ", ", " ")
        ]
        split_at = max(candidates)
        if split_at < limit // 2:
            split_at = limit
        else:
            split_at += 1
        pieces.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        pieces.append(text)
    return pieces


def translate_prose(text: str, translator: Translator) -> str:
    # Keep the retail line boundaries.  Besides giving us a useful first-pass
    # layout, this prevents the translation service from treating a location
    # or amount on the preceding line as redundant and dropping its protected
    # placeholder altogether.
    normalized = "\n".join(
        re.sub(r"[ \t]+", " ", line).strip()
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ).strip()
    return "\n".join(translator.translate(piece) for piece in split_long(normalized))


def translate_ampersand_record(source: str, translator: Translator) -> str:
    parts = re.split(r"(&)", source)
    output: list[str] = []
    for part in parts:
        if part == "&":
            output.append("&")
        elif part.strip():
            output.append(translate_prose(part, translator))
    return "\n".join(output).replace("\n&", "&")


def translate_inf(source: str, translator: Translator) -> str:
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output: list[str] = []
    prose: list[str] = []

    def flush() -> None:
        if prose:
            output.append(translate_prose(" ".join(prose), translator))
            prose.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush()
            if output and output[-1] != "":
                output.append("")
        elif stripped == "-" or INF_CONTROL_RE.fullmatch(stripped):
            flush()
            output.append(stripped)
        else:
            prose.append(stripped)
    flush()
    while output and output[-1] == "":
        output.pop()
    return "\n".join(output)


def translate_sections(source: str, translator: Translator) -> str:
    matches = list(SECTION_HEADER_RE.finditer(source))
    if not matches:
        return translate_prose(source, translator)
    output: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        body = source[match.end():end]
        output.append(match.group(0))
        if body.strip():
            output.append(translate_prose(body, translator))
    return "\n".join(output)


def translate_entry(entry: dict, translator: Translator) -> str:
    source = entry["source"]
    if entry["format"] == "inf-text":
        return translate_inf(source, translator)
    if entry["container"] == "CITYINTR":
        return translate_sections(source, translator)
    if entry["container"] == "DUNGEON.TXT":
        return "\n#\n".join(
            translate_prose(section, translator)
            for section in re.split(r"\n#\n", source)
        )
    if "&" in source:
        return translate_ampersand_record(source, translator)
    return translate_prose(source, translator)


def load_existing(paths: list[Path]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            merged.update(data)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--existing", type=Path, action="append", default=[])
    parser.add_argument("--glossary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--errors", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--endpoint",
        default="https://translate.googleapis.com/translate_a/single",
    )
    parser.add_argument("--skip-container", action="append", default=["QUESTION.TXT"])
    parser.add_argument("--only-container", action="append", default=[])
    args = parser.parse_args()

    catalog = [
        json.loads(line)
        for line in args.catalog.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    existing = load_existing(args.existing)
    glossary = json.loads(args.glossary.read_text(encoding="utf-8"))
    translator = Translator(args.endpoint, glossary, args.cache, args.timeout)

    previous = {}
    if args.output.is_file():
        data = json.loads(args.output.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            previous = data
    only_containers = set(args.only_container)
    todo = [
        entry
        for entry in catalog
        if entry["id"] not in existing
        and entry["id"] not in previous
        and (not only_containers or entry["container"] in only_containers)
        and entry["container"] not in set(args.skip_container)
        and not NONLINGUISTIC_RE.fullmatch(entry["source"])
    ]
    results = dict(previous)
    errors: dict[str, str] = {}
    total = len(todo)
    print(f"draft entries already present: {len(previous)}", flush=True)
    print(f"draft entries to translate: {total}", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(translate_entry, entry, translator): entry
            for entry in todo
        }
        for completed, future in enumerate(as_completed(futures), 1):
            entry = futures[future]
            try:
                results[entry["id"]] = future.result()
            except Exception as exc:
                errors[entry["id"]] = str(exc)
            if completed % 25 == 0 or completed == total:
                ordered = {
                    entry["id"]: results[entry["id"]]
                    for entry in catalog
                    if entry["id"] in results
                }
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    json.dumps(ordered, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                args.errors.parent.mkdir(parents=True, exist_ok=True)
                args.errors.write_text(
                    json.dumps(errors, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                translator.save_cache()
                print(
                    f"progress: {completed}/{total}; ok={len(results)}; errors={len(errors)}",
                    flush=True,
                )

    print(f"output entries: {len(results)}", flush=True)
    print(f"errors: {len(errors)}", flush=True)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
