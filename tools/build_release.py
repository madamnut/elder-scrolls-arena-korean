#!/usr/bin/env python3
"""Build a distributable Arena Korean Patch installer package from verified local files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from arena_delta import build_delta


DEFAULT_VERSION = "0.5.0"
CREATOR = "madamnut"
REPOSITORY = "https://github.com/madamnut/elder-scrolls-arena-korean"

DELTA_FILES = (
    ("ARENA/ACD.EXE", "ARENA_KR/ACDKR.EXE", "acd"),
    ("ARENA/GLOBAL.BSA", "ARENA_KR/GLOBAL_K.BSA", "global"),
    ("ARENA/INTRO.FLC", "ARENA_KR/INTKR.FLC", "intro"),
    ("ARENA/TEMPLATE.DAT", "ARENA_KR/TEMPL_KR.DAT", "template"),
    ("ARENA/ARTFACT1.DAT", "ARENA_KR/ARTFACT1.DAT", "artfact1"),
    ("ARENA/ARTFACT2.DAT", "ARENA_KR/ARTFACT2.DAT", "artfact2"),
    ("ARENA/CITYINTR", "ARENA_KR/CITYINTR", "cityintr"),
    ("ARENA/CITYTXT", "ARENA_KR/CITYTXT", "citytxt"),
    ("ARENA/DUNGEON.TXT", "ARENA_KR/DUNGEON.TXT", "dungeon"),
    ("ARENA/EQUIP.DAT", "ARENA_KR/EQUIP.DAT", "equip"),
    ("ARENA/MUGUILD.DAT", "ARENA_KR/MUGUILD.DAT", "muguild"),
    ("ARENA/SELLING.DAT", "ARENA_KR/SELLING.DAT", "selling"),
    ("ARENA/SPELLMKR.TXT", "ARENA_KR/SPELLMKR.TXT", "spellmkr"),
    ("ARENA/TAVERN.DAT", "ARENA_KR/TAVERN.DAT", "tavern"),
    ("ARENA/TITLE.IMG", "ARENA_KR/TITLE.IMG", "title"),
    ("ARENA/SCROLL03.IMG", "ARENA_KR/SCROLL03.IMG", "scroll03"),
    ("ARENA/TAMRIEL.MNU", "ARENA_KR/TAMRIEL.MNU", "tamriel"),
    ("ARENA/VISION.FLC", "ARENA_KR/VISION.FLC", "vision"),
    ("ARENA/CHAOSVSN.FLC", "ARENA_KR/CHAOSVSN.FLC", "chaosvsn"),
    ("ARENA/JAGAR.FLC", "ARENA_KR/JAGAR.FLC", "jagar"),
    ("ARENA/NUJAGDTH.FLC", "ARENA_KR/NUJAGDTH.FLC", "nujagdth"),
    ("ARENA/NUKING.FLC", "ARENA_KR/NUKING.FLC", "nuking"),
)

COPY_FILES = (
    ("ARENA_KR/ARENAKR.COM", "ARENA_KR/ARENAKR.COM"),
    ("ARENA_KR/CUTSCN.CCH", "ARENA_KR/CUTSCN.CCH"),
    ("ARENA_KR/HANGUL.FNT", "ARENA_KR/HANGUL.FNT"),
    ("ARENA_KR/HANGUL12.FNT", "ARENA_KR/HANGUL12.FNT"),
    ("ARENA_KR/HANGUL16.FNT", "ARENA_KR/HANGUL16.FNT"),
    ("ARENA_KR/QUEST_KR.TXT", "ARENA_KR/QUEST_KR.TXT"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def safe_clean_release_directory(work_root: Path, path: Path) -> None:
    work_release = (work_root / "release").resolve()
    resolved = path.resolve()
    if resolved.parent != work_release:
        raise ValueError(f"release directory is outside the allowed root: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def write_readme(path: Path, version: str) -> None:
    path.write_text(
        f"""엘더스크롤 아레나 한글 패치 v{version}

제작: {CREATOR}
GitHub: {REPOSITORY}

설치 방법
1. 이 ZIP의 압축을 완전히 해제합니다.
2. Installer.bat을 더블클릭합니다.
3. 메뉴에서 1번을 선택하고 안내에 따라 설치합니다.
4. 설치가 끝나면 Steam에서 평소처럼 게임을 실행합니다.

주의
- Steam판 The Elder Scrolls: Arena 1.07 CD-ROM용입니다.
- 정품 원본 파일의 SHA-256이 일치하지 않으면 설치하지 않습니다.
- 게임과 DOSBox를 완전히 종료한 상태에서 설치하십시오.
- 이 배포물은 Bethesda 또는 Microsoft와 관련 없는 비공식 팬 번역입니다.
""",
        encoding="utf-8",
    )


def sync_repository_package(repo: Path, package: Path) -> None:
    """Keep the repository-root installer usable after GitHub Download ZIP."""
    repository_patcher = repo / "patcher"
    package_patcher = package / "patcher"
    repository_patcher.mkdir(parents=True, exist_ok=True)
    shutil.copy2(package_patcher / "manifest.json", repository_patcher / "manifest.json")
    for directory_name in ("patches", "payload"):
        source = package_patcher / directory_name
        destination = repository_patcher / directory_name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)


def build_release(root: Path, version: str) -> tuple[Path, Path]:
    repo = root / "elder-scrolls-arena-korean"
    work = root / "arena-korean-work"
    arena = root / "ARENA"
    arena_kr = root / "ARENA_KR"
    for required in (repo, work, arena, arena_kr):
        if not required.is_dir():
            raise FileNotFoundError(required)

    release_root = work / "release"
    package_name = f"Arena-Korean-Patch-v{version}"
    package = release_root / package_name
    safe_clean_release_directory(work, package)
    (package / "patcher" / "patches").mkdir(parents=True)
    (package / "patcher" / "payload").mkdir(parents=True)

    shutil.copy2(repo / "Installer.bat", package / "Installer.bat")
    shutil.copy2(repo / "patcher" / "patcher.ps1", package / "patcher" / "patcher.ps1")
    shutil.copytree(repo / "licenses", package / "patcher" / "licenses")
    write_readme(package / "README.txt", version)

    files: list[dict[str, object]] = []
    for source_relative, target_relative, slug in DELTA_FILES:
        source = root / source_relative
        target = root / target_relative
        if not source.is_file() or not target.is_file():
            raise FileNotFoundError(f"delta input missing: {source} -> {target}")
        patch_relative = f"patcher/patches/{slug}.akdelta.zip"
        patch = package / patch_relative
        build_delta(source, target, patch, 1024)
        files.append(
            {
                "mode": "delta",
                "source": source_relative,
                "sourceSize": source.stat().st_size,
                "sourceSha256": sha256(source),
                "patch": patch_relative,
                "patchSha256": sha256(patch),
                "target": target_relative,
                "targetSize": target.stat().st_size,
                "targetSha256": sha256(target),
            }
        )

    for source_relative, target_relative in COPY_FILES:
        source = root / source_relative
        if not source.is_file():
            raise FileNotFoundError(source)
        payload_relative = f"patcher/payload/{Path(target_relative).name}"
        payload = package / payload_relative
        shutil.copy2(source, payload)
        files.append(
            {
                "mode": "copy",
                "payload": payload_relative,
                "target": target_relative,
                "targetSize": source.stat().st_size,
                "targetSha256": sha256(source),
            }
        )

    config = root / "DOSBox-0.74" / "arena.conf"
    manifest = {
        "schemaVersion": 1,
        "patchVersion": version,
        "creator": CREATOR,
        "repository": REPOSITORY,
        "steamAppId": "1812290",
        "supportedGame": "Steam Arena 1.07 CD-ROM",
        "config": {
            "path": "DOSBox-0.74/arena.conf",
            "sourceSha256": sha256(config),
        },
        "files": files,
    }
    (package / "patcher" / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    sync_repository_package(repo, package)

    release_root.mkdir(parents=True, exist_ok=True)
    zip_path = release_root / f"{package_name}.zip"
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                archive.write(path, f"{package_name}/{path.relative_to(package).as_posix()}")
    hash_path = zip_path.with_name(zip_path.name + ".sha256")
    hash_path.write_text(f"{sha256(zip_path)}  {zip_path.name}\n", encoding="ascii")
    print(f"package: {package}")
    print(f"zip: {zip_path}")
    print(f"sha256: {sha256(zip_path)}")
    return zip_path, hash_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--version", default=DEFAULT_VERSION)
    args = parser.parse_args()
    build_release(args.root.resolve(), args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
