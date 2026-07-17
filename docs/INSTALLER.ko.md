# 단일 CMD 설치기 사양

## 사용자 경험

배포 ZIP의 루트에서 `ArenaKoreanPatch.cmd` 하나만 더블클릭한다. CMD는 내부 `patcher/patcher.ps1`을 호출하고 모든 기능을 텍스트 메뉴로 제공한다.

```text
==================================================
 엘더스크롤 아레나 한글 패치 v0.1.0
 제작: MOMENLIT
==================================================

게임 경로 : C:\...\The Elder Scrolls Arena
게임 버전 : Steam Arena 1.07 CD
패치 상태 : 설치되지 않음

[1] 한글 패치 설치 또는 업데이트
[2] 설치 상태 검사
[3] 원본으로 복구
[4] 한글판 실행
[0] 종료

실행할 작업의 번호를 입력하십시오:
>
```

## CMD 책임

CMD는 UTF-8 콘솔을 설정하고 PowerShell만 실행한다. 패치 로직을 배치 문법으로 구현하지 않는다.

```bat
@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0patcher\patcher.ps1"
```

## 설치 전 검사

1. 패처 파일의 존재와 자체 버전을 확인한다.
2. Steam 기본 경로와 알려진 라이브러리를 탐색한다.
3. 찾지 못하면 Arena 루트 경로를 입력받는다.
4. `ARENA/ACD.EXE`와 `ARENA/GLOBAL.BSA` 존재를 확인한다.
5. DOSBox와 Arena 프로세스가 실행 중이면 종료를 요청한다.
6. 대상 폴더의 쓰기 권한을 시험한다.
7. 필요할 때만 관리자 권한으로 다시 실행한다.
8. 매니페스트의 원본 SHA-256과 실제 파일을 비교한다.
9. 알 수 없는 버전이면 변경 없이 중단한다.

## 설치 트랜잭션

각 파일은 다음 순서를 따른다.

```text
원본 검사
  → 임시 출력 생성
  → 출력 SHA-256 검사
  → 교체 대상 백업
  → 최종 경로로 원자적 이동
```

어느 단계든 실패하면 이번 실행에서 변경한 항목을 역순으로 되돌린다.

## 파일 처리 정책

### 한글 전용 런타임 생성

설치기는 검증된 원본 `ARENA`를 같은 게임 루트의 `ARENA_KR`로 복제한다. 이후 모든 델타 결과와 한글 파일은 `ARENA_KR`에만 적용한다. 원본 `ARENA`에는 파일을 추가하거나 교체하지 않는다.

### 원본에서 파생해 추가

| 원본 | 설치 결과 |
|---|---|
| `ACD.EXE` | `ACDKR.EXE` |
| `GLOBAL.BSA` | `GLOBAL_K.BSA` |
| `INTRO.FLC` | `INTKR.FLC` |
| `TEMPLATE.DAT` | `TEMPL_KR.DAT` |

### 자체 파일 복사

```text
ARENAKR.COM
HANGUL.FNT
HANGUL12.FNT
HANGUL16.FNT
QUEST_KR.TXT
Arena Korean Test (Windowed).bat
arena-korean-test.conf
```

### `ARENA_KR`에서 같은 이름으로 교체

```text
TITLE.IMG
SCROLL03.IMG
TAMRIEL.MNU
```

이 파일들의 원본은 `ARENA`에 그대로 남으므로 별도 복원용 백업을 만들지 않는다.

## 설치 상태 파일

`install-state.json`은 제거·검사에 필요한 사실만 기록한다.

```json
{
  "patchVersion": "0.1.0",
  "gameVersion": "steam-cd-1.07",
  "installedAt": "2026-07-11T00:00:00+09:00",
  "runtimePath": "ARENA_KR",
  "sourcePath": "ARENA",
  "addedFiles": ["ARENA_KR/ACDKR.EXE"],
  "installedFiles": [{"path": "ARENA_KR/TITLE.IMG", "sha256": "..."}]
}
```

## 확인 입력

- 설치는 `INSTALL`을 정확히 입력해야 진행한다.
- 복구는 `RESTORE`를 정확히 입력해야 진행한다.
- 빈 입력은 취소하고 주 메뉴로 돌아간다.

## 상태 검사

상태 검사는 다음을 구분한다.

- 미설치
- 정상 설치
- 일부 파일 누락
- 사용자가 설치 파일을 수정함
- 원본 백업 누락
- 지원하지 않는 원본 버전

검사만 수행할 때는 파일을 생성·복원·삭제하지 않는다.

## 원본 복구

1. 설치 상태를 읽는다.
2. `ARENA_KR`의 세이브·로그와 설치 후 사용자 생성 파일을 별도 보존 대상으로 분류한다.
3. 보존 대상이 있으면 사용자에게 경로를 알리고 삭제 전에 확인한다.
4. 한글 전용 런타임 `ARENA_KR`만 제거한다.
5. 원본 `ARENA`는 생성·복원·삭제 작업을 하지 않는다.
6. DOSBox 캡처는 건드리지 않는다.
7. 복구가 모두 끝난 뒤 상태 파일을 제거한다.

## 업데이트

새 버전도 최초 정품 원본 또는 검증된 원본 백업을 기준으로 생성한다. 이전 한글 출력물을 다음 버전 델타의 입력으로 사용하지 않는다.

## 매니페스트 필수 필드

```json
{
  "source": "ARENA/ACD.EXE",
  "sourceSha256": "...",
  "patch": "patches/acd.xdelta",
  "target": "ARENA_KR/ACDKR.EXE",
  "targetSha256": "...",
  "mode": "create"
}
```

`mode`는 `create`, `replace`, `copy` 중 하나다.
