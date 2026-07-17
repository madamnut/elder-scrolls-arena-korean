# GitHub Release 배포 정책

## 배포 원칙

Git 저장소에는 소스, 번역, 문서, 라이선스와 함께 바로 실행 가능한 설치기·델타·payload를 둔다. 따라서 저장소의 `Download ZIP`으로 받은 압축 파일도 최상단의 `Installer.bat`으로 설치할 수 있다. GitHub Release에는 이 가운데 사용자 설치에 필요한 파일만 추린 별도 ZIP을 제공한다.

배포 ZIP에는 Bethesda 원본 게임 파일이나 완성된 `ARENA_KR` 디렉터리를 넣지 않는다. 델타 배포가 법적 안전을 자동으로 보장하는 것은 아니며, 이 문서는 원본 재배포 위험을 줄이기 위한 기술 정책이다.

## 릴리스 생성

저장소 루트의 상위 게임 작업 폴더에서 다음 명령을 실행한다.

```powershell
python .\elder-scrolls-arena-korean\tools\build_release.py --version 0.3.0
```

산출물은 Git에 포함하지 않는 개인 작업 디렉터리에 생성된다.

```text
arena-korean-work/release/
├─ Arena-Korean-Patch-v0.3.0/
├─ Arena-Korean-Patch-v0.3.0.zip
└─ Arena-Korean-Patch-v0.3.0.zip.sha256
```

빌드가 성공하면 같은 버전의 `manifest.json`, `patches/`, `payload/`를 공개 저장소 루트의 `patcher/`에도 동기화한다. 이 파일들은 저장소 ZIP 설치에 필요하므로 Git에서 추적한다.

## ZIP 구조

```text
Arena-Korean-Patch-v0.3.0/
├─ Installer.bat
├─ README.txt
└─ patcher/
   ├─ patcher.ps1
   ├─ manifest.json
   ├─ patches/
   │  └─ *.akdelta.zip
   ├─ payload/
   └─ licenses/
```

사용자는 개별 델타 명령이나 Python을 설치할 필요가 없다. PowerShell 설치기가 자체적으로 델타를 적용한다.

## 델타 형식

`tools/arena_delta.py`가 생성하는 `arena-korean-delta-v1`은 ZIP 컨테이너다. 내부 `delta.json`에는 다음 두 연산만 기록한다.

- `copy`: 원본 파일의 검증된 구간을 복사한다.
- `data`: ZIP 내부에 저장된 변경 데이터를 출력한다.

매니페스트는 원본, 델타와 결과의 경로·크기·SHA-256을 기록한다. 설치기는 원본과 델타를 먼저 검증하고 결과 파일도 다시 검증한다.

## 현재 델타 대상

| 원본 | 설치 결과 |
|---|---|
| `ARENA/ACD.EXE` | `ARENA_KR/ACDKR.EXE` |
| `ARENA/GLOBAL.BSA` | `ARENA_KR/GLOBAL_K.BSA` |
| `ARENA/INTRO.FLC` | `ARENA_KR/INTKR.FLC` |
| `ARENA/TEMPLATE.DAT` | `ARENA_KR/TEMPL_KR.DAT` |
| `ARENA/TITLE.IMG` | `ARENA_KR/TITLE.IMG` |
| `ARENA/SCROLL03.IMG` | `ARENA_KR/SCROLL03.IMG` |
| `ARENA/TAMRIEL.MNU` | `ARENA_KR/TAMRIEL.MNU` |
| `ARENA/VISION.FLC` | `ARENA_KR/VISION.FLC` |
| `ARENA/CHAOSVSN.FLC` | `ARENA_KR/CHAOSVSN.FLC` |

다음 파일은 직접 작성했거나 라이선스 조건에 따라 재배포 가능한 payload다.

```text
ARENAKR.COM
HANGUL.FNT
HANGUL12.FNT
HANGUL16.FNT
QUEST_KR.TXT
```

폰트 payload에는 사용한 각 폰트의 저작권 문구, OFL 전문과 출처·변환 기록을 함께 포함한다. 자세한 내용은 [폰트 정책](FONTS.ko.md)을 따른다.

## GitHub Release 자산 이름

자동 업데이트가 동작하려면 릴리스에 다음 두 파일을 동일한 이름 규칙으로 첨부한다.

```text
Arena-Korean-Patch-v<버전>.zip
Arena-Korean-Patch-v<버전>.zip.sha256
```

릴리스 태그는 `v0.3.0`처럼 작성한다. ZIP 안의 `manifest.json`, 폴더 이름, 태그와 파일 이름의 버전을 일치시킨다.

## 공개 금지 항목

- Bethesda 원본 실행 파일과 데이터 파일
- 완성된 BSA, EXE, FLC, IMG와 `ARENA_KR` 전체
- 원본 그림을 그대로 담은 작업용 PNG
- 원본에서 추출한 대량 문자열·자산 카탈로그
- 세이브, 로그, 캡처, 백업과 임시 파일
- `arena-korean-work` 개인 작업 디렉터리

## 릴리스 전 체크리스트

- [ ] `python tools/build_release.py --version <버전>` 성공
- [ ] ZIP과 `.sha256`의 SHA-256 일치
- [ ] ZIP에 완성 게임 파일이나 작업 디렉터리가 없는지 검사
- [ ] 깨끗한 Steam판에서 `Installer.bat` 설치 성공
- [ ] Steam 전체 화면·창 모드가 모두 한글판으로 연결됨
- [ ] 상태 검사 성공
- [ ] 원본 실행 설정 복구 후 `arena.conf` 해시 일치
- [ ] 설치 실패를 유도했을 때 자동 롤백 성공
- [ ] 복구와 재설치 뒤 `ARENA_KR`의 세이브가 유지됨
- [ ] 폰트별 OFL·저작권·출처 파일 포함
- [ ] 릴리스 노트에 번역 범위와 알려진 문제 작성

## 버전 정책

SemVer 형식을 사용한다.

- 번역 범위나 기능 추가: minor
- 표시 오류, 충돌과 설치기 오류 수정: patch
- 지원 원본 또는 패치 형식의 비호환 변경: major 검토
