# The Elder Scrolls: Arena 한국어 패치

Steam판 **The Elder Scrolls: Arena 1.07 CD-ROM**을 원본 DOS 엔진 그대로 실행하면서 한국어를 표시하기 위한 비공식 팬 번역 프로젝트다.

이 프로젝트는 Bethesda 또는 Microsoft와 관련이 없다. 사용자는 정식으로 설치한 게임 파일을 직접 보유해야 한다. 공개 배포물에는 게임 전체나 Bethesda 원본 아카이브를 넣지 않고, 지원 버전의 원본 해시를 검사한 뒤 차이만 적용하는 패처를 제공하는 것을 목표로 한다.

## 현재 상태

### 완료 또는 실행 확인

- 2바이트 내부 한글 인코딩 `AKC`
- DOS TSR 기반 한글 비트맵 렌더러
- 원본 ASCII와 한글 혼합 출력
- 글자 폭 계산, 가운데 정렬 및 기본 자동 줄바꿈 연결
- 한글 타이틀 이미지와 원본 저작권 문구 유지
- 타이틀 이후 캐릭터 생성 진입 전까지의 이미지 기반 화면
- 새 게임 메뉴와 오프닝 줄거리 이미지 9장
- 캐릭터 생성 방식 선택 화면
- `생성`, `선택`, `남성`, `여성`
- 직업 판정 안내문
- 직업 판정 질문 40개와 선택지 120개
- 원본 `QUESTION.TXT`를 보존하는 별도 `QUEST_KR.TXT` 로딩
- 원본과 분리된 `GLOBAL_K.BSA`, `INTKR.FLC`, `TEMPL_KR.DAT`
- 직업 선택, 이름·성별·출신 지역 선택, 혈통 안내, 능력치 배분과 외형 선택
- 탐리엘 지역 지도와 지역명, 능력치 UI, 메인 메뉴의 이미지 고정 글자
- 리아 실메인 첫 꿈 키 1400의 한글 자막과 37픽셀 자막 밴드
- 첫 던전 환경 설명과 공통 조작·인벤토리·장비 UI 문구
- 몬스터, 무기·방어구·재질·물약 등 런타임 이름

### 작업 중

- 작은 글꼴에서 한글 행간과 밀도 조정
- 본편 UI, 대화, 퀘스트, 지도, 저장·불러오기
- 첫 본편 리아 실메인 꿈 키 1500·1294 실기 검증과 후속 꿈 키 1295~1302
- 제이거 탄과 엔딩을 포함한 나머지 런타임 컷신 자막
- 설치·검사·복구를 제공하는 단일 CMD 패처

## 지원 대상

| 항목 | 값 |
|---|---|
| 게임 | The Elder Scrolls: Arena |
| 배포판 | Steam CD-ROM판 |
| 게임 버전 | 1.07 |
| 실행 환경 | 포함된 DOSBox 0.74 |
| 원본 `ACD.EXE` SHA-256 | `40dfed48a66154feeda2dc33b9549570b4392874750101f264e7de25ece98a7d` |
| 언팩 EXE SHA-256 | `3d698ac22c1f7da49d87c78d80f89f3c3822ba3f62708b67f98fff3dac300a86` |

해시가 다른 실행 파일에는 패치를 강제로 적용하지 않는다. 다른 언어판이나 GOG판 지원은 별도의 원본 조사와 매니페스트가 필요하다.

## 실행 중인 개발판

현재 작업 폴더에서는 다음 파일을 사용한다.

```text
Arena Korean Test (Windowed).bat
ARENA_KR/ACDKR.EXE
ARENA_KR/ARENAKR.COM
ARENA_KR/HANGUL.FNT
ARENA_KR/HANGUL12.FNT
ARENA_KR/HANGUL16.FNT
ARENA_KR/GLOBAL_K.BSA
ARENA_KR/INTKR.FLC
ARENA_KR/VISION.FLC
ARENA_KR/CHAOSVSN.FLC
ARENA_KR/TEMPL_KR.DAT
ARENA_KR/QUEST_KR.TXT
DOSBox-0.74/arena-korean-test.conf
```

`ARENA_KR`은 정품 설치본 `ARENA`에서 사용자 PC에 로컬로 생성하는 한글 전용 런타임이다. 원본 실행과 한글 실행이 느슨한 이미지 파일을 공유하지 않도록 두 디렉터리를 분리한다. 일반 사용자를 위한 배포판은 아직 완성되지 않았다. 개발판 실행 전에는 DOSBox를 완전히 종료해야 갱신된 TSR이 다시 적재된다.

## 기술 개요

Arena의 원본 글꼴은 ASCII 중심의 가변폭 비트맵이다. 완성형 한글 음절은 프로젝트 전용 `AKC` 2바이트 인코딩으로 저장한다.

```text
S = Unicode 완성형 한글 인덱스 (가=0, 힣=11171)
첫 바이트 = 0x80 + (S >> 7)
둘째 바이트 = 0x80 + (S & 0x7F)
```

패치한 `ACDKR.EXE`의 폭 계산·문자 그리기 루틴은 `INT 60h`를 호출한다. `ARENAKR.COM` TSR은 ASCII를 원본과 호환되게 처리하고 AKC 한글은 현재 영문 글꼴 높이에 맞는 `HANGUL.FNT`, `HANGUL12.FNT`, `HANGUL16.FNT`에서 읽어 화면에 그린다.

자세한 구조는 [아키텍처 문서](docs/ARCHITECTURE.ko.md)와 [역공학 기록](REVERSE_ENGINEERING.md)을 참고한다.

## 문서

- [아키텍처와 런타임 구조](docs/ARCHITECTURE.ko.md)
- [한글 폰트 정책과 라이선스](docs/FONTS.ko.md)
- [단일 CMD 설치기 사양](docs/INSTALLER.ko.md)
- [개발 및 빌드 절차](docs/DEVELOPMENT.ko.md)
- [번역·문체·자리표시자 규칙](docs/TRANSLATION.ko.md)
- [실행 시험과 회귀 테스트](docs/TESTING.ko.md)
- [런타임 컷신 호출 매트릭스](docs/CUTSCENE_MATRIX.ko.md)
- [장면별 컷신 한국어 대사](docs/CUTSCENE_DIALOGUE.ko.md)
- [GitHub 및 릴리스 배포 정책](docs/DISTRIBUTION.ko.md)
- [파일 인벤토리와 소유권](docs/FILE_INVENTORY.ko.md)
- [기여 안내](CONTRIBUTING.ko.md)
- [변경 기록](CHANGELOG.md)
- [컷신 현황](CUTSCENES.md)
- [ACD.EXE 역공학 기록](REVERSE_ENGINEERING.md)

## 저장소에 포함할 것

- 직접 작성한 Python 도구와 어셈블리 소스
- UTF-8 한국어 번역 원본
- 설치기, 매니페스트, 테스트 및 문서
- 라이선스 조건을 지킨 자체 생성 런타임 파일

## 저장소에서 제외할 것

- Bethesda 원본 게임 파일
- 완성 `GLOBAL_K.BSA`, `ACDKR.EXE`, FLC·IMG 수정본
- 원본 그림이 포함된 추출·편집 PNG
- `analysis/`, `build/`, `backup/`, `reference/`, `artist-handoff/`
- 개인 세이브와 DOSBox 캡처

Git LFS는 원본 게임 파일을 공개해도 된다는 허가가 아니므로 해결책으로 사용하지 않는다.

## 라이선스

- 프로젝트 코드의 공개 라이선스는 저장소 공개 전에 별도로 결정한다.
- 한글 글리프 뱅크는 기반 폰트의 SIL Open Font License 1.1 조건을 따르며, 자세한 의무는 [폰트 정책 문서](docs/FONTS.ko.md)에 기록한다.
- xdelta3 실행 파일을 번들할 경우 GPL-2.0 조건과 고지를 따른다.
- 게임 이름, 원본 코드, 그림, 음악, 음성 및 데이터의 권리는 각 권리자에게 있다.

## 안전 원칙

1. 원본 해시가 일치하지 않으면 중단한다.
2. 원본을 직접 패치하지 않고 임시 출력에 적용한다.
3. 출력 해시를 확인한 뒤에만 설치한다.
4. 같은 이름으로 교체해야 하는 파일은 먼저 백업한다.
5. 실패하면 설치 이전 상태로 자동 롤백한다.
6. 세이브 파일은 검사·이동·삭제하지 않는다.
7. 제거기는 설치 상태 파일에 기록된 항목만 복원하거나 삭제한다.
