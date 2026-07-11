# GitHub 및 릴리스 배포 정책

## 저장소와 배포물 분리

Git 저장소는 소스·번역·문서의 이력을 관리한다. GitHub Release는 정품 원본에 적용할 델타와 설치기를 전달한다.

```text
Git 저장소                 GitHub Release
------------------------  --------------------------
Python/ASM 소스           ArenaKoreanPatch.cmd
UTF-8 번역                patcher.ps1
문서와 테스트             manifest.json
라이선스                  patches/*.xdelta
매니페스트 스키마         payload/ 자체 생성 파일
```

## 공개 금지 항목

- Bethesda 원본 실행 파일과 데이터
- 원본 또는 완성 BSA 전체
- 원본 그림을 포함한 IMG·PNG·FLC
- 원본에서 추출한 대량 문자열 카탈로그
- 세이브, 로그, 캡처, 임시 파일
- 외부 저장소의 전체 복사본

델타 패치도 자동으로 법적 안전을 보장하지 않는다. 이 문서는 기술적 위험을 줄이는 배포 구조이며 법률 자문이 아니다.

## 릴리스 패키지

```text
Arena-Korean-Patch-v0.1.0.zip
├─ ArenaKoreanPatch.cmd
├─ README.txt
├─ patcher/
│  ├─ patcher.ps1
│  ├─ manifest.json
│  ├─ patches/
│  ├─ payload/
│  └─ licenses/
```

사용자에게 개별 xdelta 명령을 요구하지 않는다.

## 델타 생성 대상

| 원본 | 결과 |
|---|---|
| `ACD.EXE` | `ACDKR.EXE` |
| `GLOBAL.BSA` | `GLOBAL_K.BSA` |
| `INTRO.FLC` | `INTKR.FLC` |
| `TEMPLATE.DAT` | `TEMPL_KR.DAT` |
| `TITLE.IMG` | 한글 `TITLE.IMG` |
| `SCROLL03.IMG` | 한글 `SCROLL03.IMG` |

`ARENAKR.COM`, `QUEST_KR.TXT`처럼 직접 작성한 파일은 payload로 복사한다. `HANGUL9.FNT`, `HANGUL12.FNT`, `HANGUL16.FNT`처럼 외부 폰트를 변환한 파일은 원저작권 문구, OFL 전문과 출처·변환 기록을 함께 배포한다. 세부 구조는 [폰트 정책 문서](FONTS.ko.md)를 따른다.

## 버전 정책

초기 버전은 SemVer 형태를 사용한다.

```text
0.1.0  캐릭터 생성 이전 + 질문 화면 개발판
0.2.0  캐릭터 생성 전체
0.3.0  시작 던전
1.0.0  목표 범위 전체 검수 완료
```

- 번역·기능 추가: minor
- 충돌·표시 오류 수정: patch
- 지원 원본이나 패치 형식의 비호환 변경: major 검토

## 릴리스 체크리스트

- [ ] 저장소에 원본 자산이 없는지 확인
- [ ] `.gitignore` 검토
- [ ] 원본·결과 SHA-256 기록
- [ ] 깨끗한 Steam 설치에서 설치 시험
- [ ] 제거 뒤 원본 해시 복원 확인
- [ ] 사용한 각 폰트의 원저작권 문구와 OFL 전문 포함
- [ ] 번역 범위와 알려진 문제 작성
- [ ] ZIP 내용물을 별도 폴더에서 재시험
- [ ] 릴리스 태그와 변경 기록 작성

## 저장소 공개 전

1. 별도의 깨끗한 저장소 디렉터리를 만든다.
2. 허용된 파일만 복사한다.
3. 첫 커밋 전에 전체 파일 목록과 크기를 검토한다.
4. 코드 라이선스를 결정한다.
5. 초기에는 비공개로 빌드·문서 링크를 점검한다.
6. 원본이 Git 기록에 들어간 적이 없는지 확인한 뒤 공개한다.

한 번 커밋한 원본 파일은 현재 트리에서 삭제해도 Git 기록에 남는다. 실수했다면 공개 전에 기록을 정리하고 새 저장소로 다시 시작하는 편이 안전하다.
