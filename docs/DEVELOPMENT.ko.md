# 개발 및 빌드 절차

## 작업 환경

- Windows PowerShell
- Python 3
- Pillow
- NASM
- Steam판 Arena 1.07 CD
- 게임에 포함된 DOSBox 0.74
- 분석용 Deark 1.7.2

모든 예시는 Arena 설치 루트에서 실행한다.

## 디렉터리 역할

```text
korean-patch/
├─ tools/          직접 작성한 포맷·빌드 도구
├─ tsr/            DOS 한글 렌더러 소스
├─ translations/   UTF-8 번역 원본
├─ docs/           프로젝트 문서
├─ analysis/       추출·미리보기·진단 결과, Git 제외
├─ build/          생성 결과, Git 제외
├─ backup/         개발 중 수동 백업, Git 제외
├─ reference/      외부 도구·참조 저장소, Git 제외
└─ artist-handoff/ 원본 포함 이미지 작업물, Git 제외
```

## 원본 검증

```powershell
Get-FileHash -Algorithm SHA256 .\ARENA\ACD.EXE
python .\korean-patch\tools\arena_bsa.py verify .\ARENA\GLOBAL.BSA
```

원본이 예상 해시와 다르면 분석·패치를 계속하지 않는다.

## AKC 검사

```powershell
python .\korean-patch\tools\akc_codec.py self-test
python .\korean-patch\tools\akc_codec.py encode "엘더 스크롤" --hex
```

번역 원본에 AKC가 지원하지 않는 문자가 있으면 빌드가 실패해야 정상이다.

## 한글 글꼴 빌드

```powershell
python .\korean-patch\tools\build_hangul_font.py `
  .\korean-patch\reference\galmuri\dist\Galmuri9.bdf `
  .\korean-patch\build\HANGUL.FNT `
  --preview .\korean-patch\analysis\HANGUL-preview.png
```

출력 글꼴의 크기와 글리프 수를 빌드 로그에 기록한다.

## TSR 빌드

```powershell
nasm -f bin `
  .\korean-patch\tsr\arena_kr.asm `
  -o .\korean-patch\build\ARENAKR.COM `
  -l .\korean-patch\analysis\arena_kr.lst
```

렌더러를 수정할 때는 이전 바이너리와 바이트 차이를 확인하고 예상한 함수만 바뀌었는지 검토한다.

## 질문 파일 빌드

```powershell
python .\korean-patch\tools\build_questions.py
```

필수 검증:

- 질문 번호 1–40
- `a)`, `b)`, `c)` 각각 40개
- `(5l)`, `(5c)`, `(5v)` 각각 40개
- AKC 인코딩 성공
- 원본 파일보다 크지 않음
- 안전 폭을 넘는 줄 없음

## ACDKR.EXE 빌드

입력은 항상 검증된 언팩 원본이다.

```powershell
python .\korean-patch\tools\patch_acd.py `
  .\korean-patch\analysis\unpacked\output.000.exe `
  .\korean-patch\build\ACDKR.EXE `
  --proof-menu `
  --bsa-name GLOBAL_K.BSA `
  --intro-name INTKR.FLC `
  --template-name TEMPL_KR.DAT `
  --question-name QUEST_KR.TXT
```

설치된 `ACDKR.EXE`를 입력으로 다시 패치하지 않는다.

## BSA 작업

```powershell
python .\korean-patch\tools\arena_bsa.py list .\ARENA\GLOBAL.BSA
python .\korean-patch\tools\arena_bsa.py verify .\ARENA\GLOBAL.BSA
python .\korean-patch\tools\arena_bsa.py rebuild `
  .\ARENA\GLOBAL.BSA `
  .\korean-patch\build\artist-final `
  .\ARENA\GLOBAL_K.BSA
```

입력과 출력에 같은 경로를 사용하지 않는다.

## 이미지 가져오기

사용자가 조정한 최종 PNG는 320×200이어야 한다.

```powershell
python .\korean-patch\tools\import_artist_images.py
python .\korean-patch\tools\import_title_image.py
```

이미지는 원본 Arena 팔레트에 디더링 없이 양자화한다. 결과는 인덱스 PNG로 미리 확인한 뒤 IMG로 적용한다.

## 개발판 설치 원칙

1. 현재 정상 파일을 `backup/`에 보존한다.
2. `build/`에서 먼저 생성·검증한다.
3. 해시가 일치하는 결과만 `ARENA/`에 복사한다.
4. DOSBox를 완전히 종료하고 다시 실행한다.
5. 사용자가 확인한 화면 단위로 다음 작업을 진행한다.

## 커밋 단위

한 커밋에는 가능한 한 하나의 목적만 둔다.

```text
feat(renderer): AKC 한글 폭 계산 추가
feat(questions): 직업 판정 질문 40개 번역
fix(font): 작은 글꼴 행간 개선
docs(installer): 복구 트랜잭션 명세 추가
```

생성 바이너리나 원본 추출물을 실수로 스테이징하지 않았는지 커밋 전에 반드시 확인한다.
