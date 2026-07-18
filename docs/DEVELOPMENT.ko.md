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
elder-scrolls-arena-korean/  공개 Git 저장소
├─ tools/                    포맷·빌드 도구
├─ tsr/                      DOS 한글 렌더러 소스
├─ translations/             배포 가능한 UTF-8 번역 원본
└─ docs/                     프로젝트 문서

arena-korean-work/           로컬 전용 작업 자료
├─ analysis/                 추출·미리보기·진단 결과
├─ build/                    현재 생성 결과
├─ backup/                   개발 중 수동 백업
├─ reference/                외부 도구·참조 저장소
├─ handoff/                  이미지 작업 전달 자료
├─ artist-handoff/           기존 이미지 작업 전달 자료
├─ translations-private/     원문 포함 비공개 카탈로그
└─ archive/                  과거 시험 산출물과 이전 구조
```

공개 저장소를 소스와 문서의 유일한 기준으로 삼는다. `arena-korean-work`에는 Git 저장소에 올릴 수 없는 원본 파생 자료와 재생성 가능한 결과만 둔다. 전체 역할은 [디렉터리 구조 문서](DIRECTORY_LAYOUT.ko.md)를 따른다.

## 원본 검증

```powershell
Get-FileHash -Algorithm SHA256 .\ARENA\ACD.EXE
python .\elder-scrolls-arena-korean\tools\arena_bsa.py verify .\ARENA\GLOBAL.BSA
```

원본이 예상 해시와 다르면 분석·패치를 계속하지 않는다.

## AKC 검사

```powershell
python .\elder-scrolls-arena-korean\tools\akc_codec.py self-test
python .\elder-scrolls-arena-korean\tools\akc_codec.py encode "엘더 스크롤" --hex
```

번역 원본에 AKC가 지원하지 않는 문자가 있으면 빌드가 실패해야 정상이다.

## 한글 글꼴 빌드

```powershell
python .\elder-scrolls-arena-korean\tools\build_hangul_font.py `
  .\arena-korean-work\reference\galmuri\dist\Galmuri9.bdf `
  .\arena-korean-work\build\HANGUL.FNT `
  --preview .\arena-korean-work\analysis\HANGUL-preview.png

python .\elder-scrolls-arena-korean\tools\build_hangul_banks.py `
  --mulmaru-pfp .\arena-korean-work\reference\font-candidates\mulmaru\release\MulmaruMono.pfp `
  --neodgm-ttf .\arena-korean-work\reference\font-candidates\neodgm\release\neodgm.ttf `
  --output-dir .\arena-korean-work\build `
  --metadata-dir .\arena-korean-work\build\font-metadata
```

출력 글꼴의 크기와 글리프 수를 빌드 로그에 기록한다. 세 파일은 각각 357,504바이트여야 한다.

## 예·아니요 선택지 빌드

추천 직업 결과창의 `Yes / No`는 이미지가 아니라 ACD.EXE 내부 문자열이다. `patch_acd.py --proof-menu`가 AKC `예`, `아니요`를 실행 파일 적재 이미지 끝에 추가하고 공용 Y/N 대화상자의 표시 포인터를 바꾼다. 선택 키 `Y/N`은 원본대로 유지한다. 별도의 이미지 변환 단계는 없다.

## TSR 빌드

```powershell
$keys = 1294..1302 + 1392..1399 + 1400,1402,1403,1404,1405,1406,1407,1447,1500
$args = @(
  '.\elder-scrolls-arena-korean\tools\build_cutscene_cache_pack.py',
  '.\arena-korean-work\build\all-cutscenes.json',
  '.\arena-korean-work\build\HANGUL.FNT',
  '.\arena-korean-work\build\CUTSCN.CCH',
  '.\elder-scrolls-arena-korean\tsr\vision_h9_cache.inc',
  '--ascii-font', '.\ARENA\ARENAFNT.DAT'
)
foreach ($key in $keys) { $args += '--template-key', [string]$key }
python @args

nasm -f bin `
  .\elder-scrolls-arena-korean\tsr\arena_kr.asm `
  -I .\elder-scrolls-arena-korean\tsr\ `
  -o .\arena-korean-work\build\ARENAKR.COM `
  -l .\arena-korean-work\analysis\arena_kr.lst
```

FLC 재생 중에는 Arena가 EMS 프레임을 사용하므로 자막 콜백에서 글꼴 EMS를 다시 호출하지 않는다. 빌더는 각 `--template-key`에 16KiB 페이지 하나를 배정한 `CUTSCN.CCH`를 만들고, TSR은 재생 직전에 해당 페이지의 글리프만 256항목 고정 버퍼로 옮긴다. 한 장면의 고유 한글이 256개를 넘거나 실제 전진폭이 320픽셀을 넘으면 빌드를 중단한다. 컷신 번역이 바뀌면 `CUTSCN.CCH`, `vision_h9_cache.inc`, `ARENAKR.COM`을 함께 다시 빌드한다.

## 컷신 자막 데이터와 FLC 빌드

`opening-overrides.json`에는 실기 통과한 컷신과 캐릭터 생성 번역만 둔다. `cutscene-staging-overrides.json`의 진행 꿈·사망 장면은 기본 빌드에 자동으로 포함하지 않는다. 시험할 때만 두 파일을 `build/` 아래의 임시 JSON으로 병합한다.

대사를 수정한 뒤 장면별 대사 문서를 다시 만든다.

```powershell
python .\elder-scrolls-arena-korean\tools\build_cutscene_dialogue_doc.py `
  --catalog .\arena-korean-work\translations-private\catalog.jsonl `
  --stable .\elder-scrolls-arena-korean\translations\opening-overrides.json `
  --staging .\elder-scrolls-arena-korean\translations\cutscene-staging-overrides.json `
  --active .\elder-scrolls-arena-korean\translations\cutscene-active-test.json `
  --output .\elder-scrolls-arena-korean\docs\CUTSCENE_DIALOGUE.ko.md
```

```powershell
$staged = 1295..1302 + 1392..1399 + 1402,1403,1404,1405,1406,1407,1447
$args = @(
  '.\elder-scrolls-arena-korean\tools\merge_overrides.py',
  '.\elder-scrolls-arena-korean\translations\opening-overrides.json',
  '.\elder-scrolls-arena-korean\translations\cutscene-staging-overrides.json',
  '--output', '.\arena-korean-work\build\all-cutscenes.json'
)
foreach ($key in $staged) { $args += '--staged-template-key', [string]$key }
python @args
```

격리 시험은 `--staged-template-key`로 한 키씩 만들 수 있다. 현재 통합 시험판은 staging의 23개 키를 모두 병합하고 stable의 키 1294·1400·1500까지 합친 26개 장면 파일을 사용한다. `TEMPL_KR.DAT`, `CUTSCN.CCH`, `vision_h9_cache.inc`, `ARENAKR.COM`의 키 집합은 항상 같아야 한다.

```powershell
python .\elder-scrolls-arena-korean\tools\apply_catalog.py `
  --arena .\ARENA `
  --catalog .\arena-korean-work\translations-private\catalog.jsonl `
  --overrides .\elder-scrolls-arena-korean\translations\opening-overrides.json `
  --output .\arena-korean-work\build\opening-data `
  --bsa-output .\arena-korean-work\build\GLOBAL_K-opening-base.BSA

python .\elder-scrolls-arena-korean\tools\localize_vision_band.py `
  .\ARENA\VISION.FLC `
  .\arena-korean-work\build\VISION.FLC `
  --expected-frames 20

python .\elder-scrolls-arena-korean\tools\localize_vision_band.py `
  .\ARENA\CHAOSVSN.FLC `
  .\arena-korean-work\build\CHAOSVSN.FLC `
  --expected-frames 31

python .\elder-scrolls-arena-korean\tools\localize_vision_band.py `
  .\ARENA\JAGAR.FLC `
  .\arena-korean-work\build\JAGAR.FLC `
  --expected-frames 28

python .\elder-scrolls-arena-korean\tools\localize_vision_band.py `
  .\ARENA\NUJAGDTH.FLC `
  .\arena-korean-work\build\NUJAGDTH.FLC `
  --expected-frames 62

python .\elder-scrolls-arena-korean\tools\localize_vision_band.py `
  .\ARENA\NUKING.FLC `
  .\arena-korean-work\build\NUKING.FLC `
  --expected-frames 17
```

`opening-data\loose\TEMPLATE.DAT`는 런타임에서 실행 파일이 요청하는 이름인 `TEMPL_KR.DAT`로 배치한다. Arena는 해시 레코드 본문의 원본 파일 오프셋을 유지하므로 번역 레코드를 가변 길이로 다시 붙이면 안 된다. 빌더는 짧은 번역의 `&` 종료표식 뒤에 공백을 채우고, 원본보다 긴 번역은 거부한다. 출력 파일 크기와 모든 `#키` 헤더의 바이트 오프셋이 원본과 정확히 같아야 한다. FLC 도구는 320×200 영상의 Y=0~162 픽셀, 프레임별 팔레트, 프레임 수와 재생 속도를 보존하고 Y=163~199만 검게 만든 뒤 다시 디코딩해 검증한다. `VISION.FLC`는 20프레임·171ms, `CHAOSVSN.FLC`는 31프레임·114ms, `JAGAR.FLC`는 28프레임·128ms, `NUJAGDTH.FLC`는 62프레임·142ms, `NUKING.FLC`는 17프레임·114ms를 유지해야 한다.

## 질문 파일 빌드

```powershell
python .\elder-scrolls-arena-korean\tools\build_questions.py
```

필수 검증:

- 질문 번호 1–40
- `a)`, `b)`, `c)` 각각 40개
- `(5l)`, `(5c)`, `(5v)` 각각 40개
- AKC 인코딩 성공
- 원본 파일보다 크지 않음
- `FONT_B` 실제 문자폭으로 계산한 원본 최대 줄 폭을 넘지 않음
- 원본 최장 문항의 세로 배치량을 넘지 않음
- 자동 이어줄에 강제 들여쓰기가 없음
- 원본 `QUESTION.TXT`와 같은 `공백 + LF` 줄 끝을 사용하고 CRLF나 후행 공백 없는 LF를 넣지 않음
- 질문 본문마다 선택지 구분자 `:`이 정확히 하나 있음
- 엔진 방식으로 세 번째 판정 태그 6바이트 뒤가 다음 문항 번호 또는 파일 끝과 일치함

## ACDKR.EXE 빌드

입력은 항상 검증된 언팩 원본이다.

```powershell
python .\elder-scrolls-arena-korean\tools\patch_acd.py `
  .\arena-korean-work\analysis\unpacked\output.000.exe `
  .\arena-korean-work\build\ACDKR.EXE `
  --proof-menu `
  --bsa-name GLOBAL_K.BSA `
  --intro-name INTKR.FLC `
  --template-name TEMPL_KR.DAT `
  --question-name QUEST_KR.TXT
```

설치된 `ACDKR.EXE`를 입력으로 다시 패치하지 않는다.

사망 자막 주소 문제를 진행값 분기 우회로 해결하지 않는다. `patch_acd.py`에는 새 게임 뒤 `DS:[0x0F77]`을 강제로 바꾸는 훅이 없어야 한다. 장면 캐시 훅은 공통 FLC 실행기의 기존 재배치 far call 대상만 바꾸며, 직전 검증 실행본과의 차이는 코드 동굴 10바이트와 call 대상 2바이트뿐이어야 한다.

## 마을 주민 인사말 빌드

```powershell
python .\elder-scrolls-arena-korean\tools\apply_catalog.py `
  --arena .\ARENA `
  --catalog .\arena-korean-work\translations-private\catalog.jsonl `
  --overrides .\elder-scrolls-arena-korean\translations\city-greetings-overrides.json `
  --output .\arena-korean-work\build\city-greetings `
  --bsa-output .\arena-korean-work\build\city-greetings\GLOBAL-unchanged.BSA
```

`loose\CITYTXT`를 `ARENA_KR\CITYTXT`로 배치한다. 64개 레코드는 원문과 같은 행 수를 유지하며, 출력은 원본과 같은 10,669바이트이고 모든 `#키` 헤더 오프셋이 같아야 한다. 휴식 선택지와 주민 대화 메뉴는 `CITYTXT`가 아니라 `patch_acd.py`의 제어 문자열 패치이므로 `ACDKR.EXE`도 함께 다시 빌드한다.

## 마을 주민 답변 빌드

`누구인가?`, 일반 소문, 일거리의 실제 답변은 `translations\npc-dialogue-overrides.json`에서 관리한다. 현재 리아 실메인 26개 장면이 들어 있는 통합 오버라이드와 먼저 병합한 뒤 `TEMPLATE.DAT`를 빌드해야 한다. NPC 파일만 따로 적용하면 컷신 번역이 사라진다.

```powershell
python .\elder-scrolls-arena-korean\tools\merge_overrides.py `
  .\arena-korean-work\build\dynamic-cutscene-cache-final\all-cutscenes.json `
  .\elder-scrolls-arena-korean\translations\npc-dialogue-overrides.json `
  --output .\arena-korean-work\build\npc-dialogue-combined\all-overrides.json

python .\elder-scrolls-arena-korean\tools\apply_catalog.py `
  --arena .\ARENA `
  --catalog .\arena-korean-work\translations-private\catalog.jsonl `
  --overrides .\arena-korean-work\build\npc-dialogue-combined\all-overrides.json `
  --output .\arena-korean-work\build\npc-dialogue-combined\data `
  --bsa-output .\arena-korean-work\build\npc-dialogue-combined\GLOBAL-unchanged.BSA
```

결과 `data\loose\TEMPLATE.DAT`를 `ARENA_KR\TEMPL_KR.DAT`로 배치한다. 통합 오버라이드는 컷신 26개와 주민 답변 54개, 총 80개 레코드여야 한다. 출력 크기는 원본과 같은 395,981바이트이고 모든 `#키` 헤더의 바이트 오프셋이 같아야 한다. 주민 답변은 일반 인게임 렌더러를 사용하므로 `CUTSCN.CCH`는 다시 만들지 않는다. `apply_catalog.py`는 이름·장소 등 일반 자리표시자의 종류와 횟수를 엄격히 검증하지만, `TEMPLATE.DAT`의 절차 생성 영문 조각 `%oc`, `%doc`, `%jok`, `%oth`는 번역이 의미를 대신할 때에만 원문보다 적게 사용할 수 있다. 번역 쪽에서 새로 추가하는 것은 허용하지 않는다. 장소 목록 두 표와 `%di`의 8방향 표는 `patch_acd.py`의 `GAMEPLAY_NAME_TABLES`에 있으므로 `ACDKR.EXE`도 함께 다시 빌드한다.

## BSA 작업

```powershell
python .\elder-scrolls-arena-korean\tools\arena_bsa.py list .\ARENA\GLOBAL.BSA
python .\elder-scrolls-arena-korean\tools\arena_bsa.py verify .\ARENA\GLOBAL.BSA
python .\elder-scrolls-arena-korean\tools\arena_bsa.py rebuild `
  .\ARENA\GLOBAL.BSA `
  .\arena-korean-work\build\artist-final `
  .\ARENA_KR\GLOBAL_K.BSA
```

입력과 출력에 같은 경로를 사용하지 않는다.

### 첫 던전과 공통 인게임 UI

`poc-overrides.json`에서 시작 던전 `START.INF`의 AKC 평문을 만든다.

```powershell
python .\elder-scrolls-arena-korean\tools\apply_catalog.py `
  --arena .\ARENA `
  --catalog .\arena-korean-work\translations-private\catalog.jsonl `
  --overrides .\elder-scrolls-arena-korean\translations\poc-overrides.json `
  --output .\arena-korean-work\build\first-dungeon-data `
  --bsa-output .\arena-korean-work\build\GLOBAL_K-first-dungeon-base.BSA
```

자동지도와 일지의 고정 문구는 원본 BSA 추출물과 한글 글리프 뱅크에서 만든다.

```powershell
python .\elder-scrolls-arena-korean\tools\localize_ingame_ui.py `
  .\arena-korean-work\analysis\bsa-decoded `
  .\arena-korean-work\build\ingame-ui-replacements `
  --font9 .\arena-korean-work\build\HANGUL.FNT `
  --font16 .\arena-korean-work\build\HANGUL16.FNT `
  --charsht-col .\ARENA\CHARSHT.COL `
  --preview-dir .\arena-korean-work\analysis\ingame-ui-localized `
  --automap-workpack-dir .\arena-korean-work\handoff\embedded-text\AUTOMAP `
  --equip-workpack-dir .\arena-korean-work\handoff\embedded-text\EQUIP
```

### 이미지 고정 글자 작업 인계

영문이 이미지 픽셀에 박힌 화면은 최종 합성을 임의로 확정하지 않고 작업 묶음을 만든다. 묶음에는 실제 1배 해상도의 원본 PNG, 영문만 제거한 PNG, HANGUL 원본 크기의 투명 단어 PNG, 모든 단어를 한 장에 모은 실제 크기 아틀라스와 좌표 JSON, 좌상단 배치 좌표, 자동 배치 참고본을 넣는다. 글자 이미지를 새로 만들 때는 개별 PNG와 아틀라스를 항상 함께 생성하며, 확대 미리보기는 만들지 않는다.

장비 화면 작업자는 `handoff/embedded-text/EQUIP/02_EQUIP-clean.png`를 바탕으로 작업하고, `words/`의 개별 단어 또는 `04_EQUIP-text-atlas-actual-size.png`를 참고해 `완성본-넣는곳/EQUIP-final.png`에 171×200 완성본을 둔다. 아틀라스의 정확한 사각형은 `04_EQUIP-text-atlas.json`에 기록한다. 원본 게임 이미지가 포함된 `handoff` 작업 묶음은 개발용 비공개 폴더이며 공개 저장소나 배포 ZIP에 넣지 않는다. 완성본을 가져올 때는 `CHARSHT.COL`로 디더링 없이 양자화하고, 변환한 `EQUIP.IMG`만 현재 한글 BSA에 합친다.

자동지도 작업자는 `handoff/embedded-text/AUTOMAP/02_AUTOMAP-clean.png`를 바탕으로 작업하고, `words/` 또는 실제 크기 `04_AUTOMAP-text-atlas-actual-size.png`를 사용해 `완성본-넣는곳/AUTOMAP-final.png`에 320×200 완성본을 둔다. 이미지 고정 글자는 `N/E/S/W`, `Exit`뿐이며 상단 장소명·지도 선·플레이어 표시는 동적 출력이므로 완성본에 넣지 않는다. 정확한 좌표와 팔레트 번호는 `04_AUTOMAP-text-atlas.json`과 작업 묶음의 `README.ko.md`에 기록한다.

```powershell
python .\elder-scrolls-arena-korean\tools\import_automap_image.py `
  --png .\arena-korean-work\handoff\embedded-text\AUTOMAP\완성본-넣는곳\AUTOMAP-final.png `
  --source .\arena-korean-work\analysis\bsa-decoded\AUTOMAP.IMG `
  --output .\arena-korean-work\build\automap-artist-final\AUTOMAP.IMG `
  --preview .\arena-korean-work\build\automap-artist-final\AUTOMAP-preview-320x200.png
```

가져오기 도구는 320×200 완전 불투명 이미지, 원본 내장 팔레트 색상만 허용한다. 깨끗한 바탕과의 차이는 나침반 `(240,18)–(306,77)`과 종료 `(238,156)–(304,182)` 영역 안에만 있어야 하며, 나침반 팔레트 10번과 종료 팔레트 6번 글자색이 모두 존재해야 한다.

```powershell
python .\elder-scrolls-arena-korean\tools\import_equip_image.py `
  --png .\arena-korean-work\handoff\embedded-text\EQUIP\완성본-넣는곳\EQUIP-final.png `
  --source .\arena-korean-work\analysis\bsa-decoded\EQUIP.IMG `
  --palette .\ARENA\CHARSHT.COL `
  --output .\arena-korean-work\build\equip-artist-final\EQUIP.IMG `
  --preview .\arena-korean-work\build\equip-artist-final\EQUIP-preview-171x200.png
```

가져오기 도구는 171×200·불투명 이미지만 허용하고, 깨끗한 바탕과 달라진 픽셀이 팔레트 253번 금색 또는 31번 짙은 갈색인지 검사한다. 현재 확정 배치는 `레벨:` `(105,22)`, `장비` `(74,39)`, `종료` `(14,190)`, `마법서` `(71,190)`, `버리기` `(133,190)`이다.

최종 BSA는 반드시 현재 한글 BSA를 입력으로 삼아 두 단계로 합친다. 원본 `GLOBAL.BSA`에서 다시 시작하면 이전 이미지 교체가 사라진다.

```powershell
python .\elder-scrolls-arena-korean\tools\arena_bsa.py rebuild `
  .\ARENA_KR\GLOBAL_K.BSA `
  .\arena-korean-work\build\first-dungeon-data\inf-plain `
  .\arena-korean-work\build\GLOBAL_K-text.BSA `
  --encode-inf

python .\elder-scrolls-arena-korean\tools\arena_bsa.py rebuild `
  .\arena-korean-work\build\GLOBAL_K-text.BSA `
  .\arena-korean-work\build\ingame-ui-replacements `
  .\arena-korean-work\build\GLOBAL_K-ingame.BSA
```

새 단계를 처음 적용하는 기준 BSA와 최종 결과를 항목별로 비교했을 때 `START.INF`, `AUTOMAP.IMG`, `LOGBOOK.IMG`, `EQUIP.IMG`만 달라야 한다. 이미 앞의 세 파일이 적용된 현재 개발 BSA를 기준으로 다시 만들면 `EQUIP.IMG` 하나만 달라야 한다. 공통 실행 파일 문구 125개와 런타임 이름 표 10개는 별도 명령이 아니라 `patch_acd.py`의 기본 검증 패치에 포함된다.

## 이미지 가져오기

사용자가 조정한 최종 PNG는 320×200이어야 한다.

```powershell
python .\elder-scrolls-arena-korean\tools\import_artist_images.py
python .\elder-scrolls-arena-korean\tools\import_title_image.py
```

이미지는 원본 Arena 팔레트에 디더링 없이 양자화한다. 결과는 인덱스 PNG로 미리 확인한 뒤 IMG로 적용한다.

능력치 화면은 `tools/export_clean_charstat.py`로 글자 없는 171×200 `CHARSTAT`과 77×16 `BONUS` PNG를 만들고, HANGUL9 글자 아틀라스를 참고해 사람이 최종 배치한다. 완성 PNG는 `tools/import_charstat_images.py`로 원본 IMG 헤더와 `CHARSHT.COL` 팔레트를 보존한 채 가져온다. 최종 `BONUS.IMG` 헤더 좌표는 `(62,119)`이며, 생성한 두 IMG만 현재 한글 `GLOBAL_K.BSA`에 교체해 기존 한글 자원을 보존한다. 출력과 검수는 모두 실제 1배 해상도로 진행하며 확대 복제본은 만들지 않는다.

메인 메뉴 한 장만 다시 가져올 때는 `tools/import_menu_image.py`를 사용한다. 완성 PNG는 320×200이어야 하며 원본 `MENU.IMG`의 내장 팔레트에 디더링 없이 양자화한다. `SCROLL.FLC` 팔레트로 픽셀 인덱스를 만든 뒤 원본 메뉴 팔레트를 붙이면 게임에서 색이 뒤틀리므로, 출력 IMG의 픽셀 인덱스와 내장 팔레트는 반드시 같은 원본 메뉴 팔레트를 기준으로 한다. 조선100년체 폰트 파일은 패치에 포함하지 않고, 폰트로 만든 최종 비트맵 결과만 `MENU.IMG`로 배포한다.

ESC 설정 메뉴는 `GLOBAL.BSA/OP.IMG` 한 장이며 완성 PNG 크기는 320×147이다. `OP.IMG`에는 팔레트가 없으므로 `tools/import_esc_menu_image.py`로 `ARENA/PAL.COL`에 무디더링 양자화하고 원본 좌표 `(0,0)`과 IMG 헤더를 보존한다. 현재 개발 BSA에 적용할 때는 기존 `GLOBAL_K.BSA`를 입력으로 삼아 `OP.IMG`만 든 별도 교체 폴더로 재구성한다. 적용 전후 항목 비교에서 `OP.IMG` 하나만 달라야 한다.

## 개발판 설치 원칙

1. 현재 정상 파일을 `arena-korean-work/backup/`에 보존한다.
2. `arena-korean-work/build/`에서 먼저 생성·검증한다.
3. 해시가 일치하는 결과만 한글 전용 런타임 `ARENA_KR/`에 복사한다.
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
