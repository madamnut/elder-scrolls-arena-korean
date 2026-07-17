# 디렉터리 구조

Arena 설치 루트는 Steam 원본, 한글 실행 환경, 공개 개발 소스, 로컬 작업 자료를 분리한다.

```text
The Elder Scrolls Arena/
├─ ARENA/                         Steam 원본 게임 데이터
├─ ARENA_KR/                      로컬에서 생성한 한글 실행 환경
├─ DOSBox-0.74/                   Steam 제공 DOSBox와 실행 설정
├─ Docs/                          Steam 제공 공식 설명서
├─ elder-scrolls-arena-korean/    공개 Git 저장소
└─ arena-korean-work/             배포하지 않는 로컬 작업 자료
```

## 변경 금지 영역

- `ARENA`: 패치 입력이 되는 정품 원본이다. 개발 도구와 설치기는 직접 수정하지 않는다.
- `Docs`: Steam이 설치한 공식 설명서다.
- `DOSBox-0.74`: Steam 실행 설정과 한글 실행 설정을 함께 관리한다. 설치기 작업 전까지 임의로 재배치하지 않는다.

## 한글 실행 환경

`ARENA_KR`은 `ARENA`에서 사용자 PC에 로컬로 생성한 실행 환경이다. 완성 게임 파일을 저장소나 릴리스 ZIP에 포함하지 않는다. 빌드 결과를 적용할 때는 먼저 임시 파일을 검증하고, 검증된 파일만 이 디렉터리에 배치한다.

## 공개 Git 저장소

`elder-scrolls-arena-korean`은 다음 항목의 유일한 기준이다.

- Python 포맷·빌드 도구
- TSR 및 DOS 한글 렌더러 소스
- 공개 가능한 번역 원본
- 설치기와 릴리스 구성
- 개발·검수·역공학 문서

같은 소스 파일을 `arena-korean-work`에 복제해 수정하지 않는다.

사용자에게 바로 보이는 저장소 최상단 구조는 다음과 같다.

```text
elder-scrolls-arena-korean/
├─ Installer.bat
├─ README.md
├─ patcher/
│  ├─ patcher.ps1
│  ├─ manifest.json
│  ├─ patches/
│  └─ payload/
├─ licenses/
├─ tools/
├─ translations/
└─ docs/
```

`patcher/patches`와 `patcher/payload`는 저장소 ZIP에서 설치기가 즉시 동작하기 위한 배포 자원이다. 완성 게임 파일이 아니라 검증된 원본에 적용할 델타와 재배포 가능한 파일만 둔다.

## 로컬 작업 자료

```text
arena-korean-work/
├─ analysis/                 추출·미리보기·진단 결과
├─ build/                    현재 빌드 산출물
├─ backup/                   수동 백업
├─ reference/                외부 도구와 참고 저장소
├─ handoff/                  현재 이미지 작업 전달 자료
├─ artist-handoff/           기존 이미지 작업 전달 자료
├─ translations-private/     원문 포함 카탈로그와 통계
└─ archive/                  과거 시험 산출물과 이전 구조
```

`build` 최상단에는 현재 한글 실행 환경과 대응하는 대표 산출물만 둔다. 시험 과정에서 생성한 이전 BSA·EXE·COM은 `archive`로 이동하며 기본 빌드 입력으로 사용하지 않는다.

## 배포 원칙

최소 구성의 릴리스 ZIP은 공개 Git 저장소의 소스 ZIP과 별도로 생성한다. 어느 쪽에도 Steam 원본, `ARENA_KR`, `arena-korean-work`, 원본 이미지·영상·BSA 전체는 배포하지 않는다.
