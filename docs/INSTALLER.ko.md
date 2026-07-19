# 설치기 구현과 사용법

## 목표

사용자는 GitHub 저장소의 `Download ZIP` 또는 GitHub Releases에서 ZIP을 내려받아 완전히 압축 해제한 뒤 최상단의 `Installer.bat`을 더블클릭한다. 설치가 끝나면 별도의 실행 파일을 찾을 필요 없이 Steam의 기존 전체 화면·창 모드 실행 항목을 그대로 사용한다.

```text
==================================================
 엘더스크롤 아레나 한글 패치 v0.5.0
 제작: madamnut
 GitHub: https://github.com/madamnut/elder-scrolls-arena-korean
==================================================

[1] 한글 패치 설치 또는 현재 패키지로 업데이트
[2] 최신 버전 확인 및 자동 업데이트
[3] 설치 상태 검사
[4] 원본 실행 설정 복구
[0] 종료
```

진행 중에는 다음 형식으로 현재 단계를 표시한다.

```text
[##########----------]  50%  적용 중: ARENA_KR/GLOBAL_K.BSA
```

## 구성

`Installer.bat`은 UTF-8 콘솔을 설정하고 `patcher/patcher.ps1`을 호출하는 진입점이다. 경로 탐색, 파일 검증, 델타 적용, 백업, 복구 및 업데이트 로직은 PowerShell에 있다.

```text
Installer.bat
README.txt
patcher/
├─ patcher.ps1
├─ manifest.json
├─ patches/*.akdelta.zip
├─ payload/ARENAKR.COM, CUTSCN.CCH, HANGUL*.FNT, QUEST_KR.TXT
└─ licenses/
```

## Steam 설치 경로 탐색

1. Windows 레지스트리에서 Steam 설치 경로를 찾는다.
2. `steamapps/libraryfolders.vdf`에 등록된 모든 라이브러리를 읽는다.
3. Arena의 Steam App ID `1812290`에 해당하는 `appmanifest_1812290.acf`를 찾는다.
4. 매니페스트의 `installdir`를 읽고 실제 게임 루트를 검증한다.
5. 자동 탐색에 실패하면 사용자에게 Arena 설치 폴더 전체 경로를 입력받는다.

다음 파일이 있어야 유효한 게임 루트로 인정한다.

```text
ARENA/ACD.EXE
ARENA/GLOBAL.BSA
DOSBox-0.74/arena.conf
Arena (Full Screen).bat
Arena (Windowed).bat
```

## 설치 처리

1. DOSBox가 실행 중인지 검사한다.
2. 원본, 델타와 payload의 SHA-256을 모두 확인한다.
3. `ARENA_KR`이 없으면 원본 `ARENA`를 복제한다.
4. 자체 델타 형식 `arena-korean-delta-v1`으로 한글 파일을 생성한다.
5. 직접 작성하거나 재배포가 허용된 파일을 payload에서 복사한다.
6. 설치 결과 파일의 SHA-256을 다시 확인한다.
7. 원본 `DOSBox-0.74/arena.conf`를 백업한다.
8. `[autoexec]` 구역만 `ARENA_KR`, `ARENAKR.COM`, `ACDKR.EXE`를 사용하도록 바꾼다.
9. `.arena-korean-patch/install-state.json`에 설치 상태를 기록한다.

Steam의 `Arena (Full Screen).bat`과 `Arena (Windowed).bat`은 둘 다 같은 `arena.conf`를 사용하므로 BAT 파일 자체는 수정하지 않는다.

## 트랜잭션과 자동 롤백

설치 중 교체할 파일은 `.arena-korean-patch/transactions/<임시 ID>`에 백업한다. 어느 단계든 실패하면 이번 실행에서 변경한 파일을 역순으로 되돌린다. 최초 설치 중 새로 만든 `ARENA_KR`도 실패 시 제거한다. 성공하거나 롤백이 끝나면 임시 트랜잭션 디렉터리를 삭제한다.

원본 `ARENA`의 게임 파일은 직접 수정하지 않는다.

## 설치 상태 검사

3번 메뉴는 설치 상태 파일, 관리 대상 파일의 SHA-256과 현재 `arena.conf`를 검사한다. 검사는 파일을 변경하지 않는다.

## 원본 실행 설정 복구

4번 메뉴에서 `RESTORE`를 입력하면 백업한 원본 `arena.conf`를 복원한다. Steam은 다시 원본 `ARENA`를 실행한다.

`ARENA_KR`은 세이브 보호를 위해 삭제하지 않는다. 다시 설치하면 기존 `ARENA_KR`을 유지하면서 관리 대상 파일만 검증된 버전으로 갱신한다.

## 자동 업데이트

2번 메뉴는 GitHub의 최신 릴리스를 조회한다. 현재 패키지보다 새 버전이 있으면 다음 두 릴리스 자산을 내려받는다.

```text
Arena-Korean-Patch-v<버전>.zip
Arena-Korean-Patch-v<버전>.zip.sha256
```

ZIP의 SHA-256을 확인한 뒤 게임 폴더 아래 `.arena-korean-patch/updates/<버전>`에 압축을 풀고 새 설치기를 무인 모드로 실행한다. 인터넷 연결이나 GitHub Release가 없으면 현재 패키지를 이용한 1번 설치는 계속 사용할 수 있다.

## 지원 범위와 중단 조건

- Steam판 The Elder Scrolls: Arena 1.07 CD-ROM만 지원한다.
- 원본 파일 또는 원본 `arena.conf`의 SHA-256이 다르면 변경 없이 중단한다.
- 게임이나 DOSBox가 실행 중이면 중단한다.
- ZIP 내부 파일이 손상되거나 결과 해시가 다르면 자동 롤백한다.
- 설치에 관리자 권한이 필요할 수 있으며, 사용자는 Windows의 권한 요청을 직접 승인해야 한다.
