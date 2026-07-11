# 파일 인벤토리와 소유권

## 분류 기준

- `source`: 프로젝트가 직접 작성하고 Git에 포함
- `translation`: 프로젝트 번역 원본, Git에 포함
- `generated`: 소스로 재생성 가능, 일반적으로 Git 제외 또는 릴리스 payload
- `original`: 게임 원본, Git·릴리스 제외
- `derived`: 원본을 포함하거나 크게 변형, Git 제외하고 델타만 배포
- `reference`: 외부 도구·저장소, Git 제외

## 프로젝트 파일

| 경로 | 분류 | Git | 릴리스 |
|---|---|---:|---:|
| `tools/*.py` | source | 포함 | 선택 |
| `tsr/arena_kr.asm` | source | 포함 | 선택 |
| `translations/QUEST_KR.utf8.txt` | translation | 포함 | 선택 |
| `docs/*.md` | source | 포함 | README 포함 |
| `ARENAKR.COM` | generated | 제외 | payload |
| `HANGUL.FNT` | generated/OFL | 제외 | payload + OFL |
| `QUEST_KR.TXT` | generated | 제외 | payload |
| `ACDKR.EXE` | derived | 제외 | xdelta 결과 |
| `GLOBAL_K.BSA` | derived | 제외 | xdelta 결과 |
| `INTKR.FLC` | derived | 제외 | xdelta 결과 |
| `TEMPL_KR.DAT` | derived | 제외 | xdelta 결과 |

## 이미지 파일

| 파일 | 비고 |
|---|---|
| `TITLE.IMG` | 느슨한 파일이 우선 로딩됨 |
| `SCROLL03.IMG` | CD판 느슨한 파일이 BSA 항목보다 우선됨 |
| `QUOTE.IMG` | BSA 내부 |
| `SCROLL01.IMG` | BSA 내부 |
| `SCROLL02.IMG` | BSA 내부 |
| `MENU.IMG` | BSA 내부 |
| `INTRO01–09.IMG` | BSA 내부 새 게임 줄거리 |

원본 그림을 포함한 PNG와 IMG는 저장소에 올리지 않는다.

## 텍스트·데이터 파일

| 파일 | 내용 | 전략 |
|---|---|---|
| `QUESTION.TXT` | 직업 판정 질문 | 원본 보존 |
| `QUEST_KR.TXT` | 한국어 질문 | 새 파일 |
| `TEMPLATE.DAT` | 컷신·대사 템플릿 | 원본 보존 |
| `TEMPL_KR.DAT` | 한국어 템플릿 | 새 파일 |
| `CLASSES.DAT` | 직업 판정 수치 | 번역하지 않음 |
| `STARTGAM.MNU` | 캐릭터 생성 배경 | 그림에 글자 없음 |

## 폰트

| 파일 | 소유·용도 |
|---|---|
| `FONT_*.DAT`, `ARENAFNT.DAT` 등 | 게임 원본, 배포 금지 |
| Galmuri 원본 | 외부 OFL 폰트, 전체 reference는 Git 제외 |
| `HANGUL.FNT` | Galmuri 기반 생성물, OFL 고지 필요 |

## 반드시 무시할 디렉터리

```text
analysis/
build/
backup/
reference/
artist-handoff/
```

## 세이브 및 사용자 데이터

패처는 다음 유형을 소유하지 않으며 변경하지 않는다.

```text
*.64
*.65
LOG.*
CITYDATA.*
SPELLS.*
SPELLSG.*
STATES.*
DOSBox-0.74/capture/
```

정확한 세이브 목록을 모르는 상태에서 와일드카드 삭제를 사용하지 않는다.

