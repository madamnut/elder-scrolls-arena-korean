# 전체 번역 진행 현황

이 문서는 원본 데이터에서 다시 추출한 카탈로그와 번역 오버라이드를 대조해 생성한다.

현재 모든 대상에는 1차 번역이 들어가 있다. 자동 초벌 번역이 포함되어 있으므로 `번역 적용`은 최종 교정 완료가 아니라 게임에서 문맥·문체·조판을 시험할 수 있는 상태를 뜻한다. 잔존 로마자 분류는 [번역 잔존 영문 감사](TRANSLATION_RESIDUE.ko.md)를 참고한다.

## 전체 집계

| 상태 | 항목 수 | 원문 문자 수 |
|---|---:|---:|
| 번역 적용 | 1,869 | 544,997 |
| 번역 필요 | 0 | 0 |
| 별도 파일로 처리 | 1 | 29,822 |
| 비언어 제어값 | 64 | 64 |

## 파일별 집계

| 원본 컨테이너 | 전체 | 번역 | 필요 | 별도 | 제어값 |
|---|---:|---:|---:|---:|---:|
| `ARTFACT1.DAT` | 240 | 208 | 0 | 0 | 32 |
| `ARTFACT2.DAT` | 240 | 208 | 0 | 0 | 32 |
| `CITYINTR` | 1 | 1 | 0 | 0 | 0 |
| `CITYTXT` | 64 | 64 | 0 | 0 | 0 |
| `DUNGEON.TXT` | 1 | 1 | 0 | 0 | 0 |
| `EQUIP.DAT` | 75 | 75 | 0 | 0 | 0 |
| `GLOBAL.BSA/AGTEMPL.INF` | 10 | 10 | 0 | 0 | 0 |
| `GLOBAL.BSA/BGATE2.INF` | 1 | 1 | 0 | 0 | 0 |
| `GLOBAL.BSA/CASTLE.INF` | 2 | 2 | 0 | 0 | 0 |
| `GLOBAL.BSA/CRYPT1.INF` | 7 | 7 | 0 | 0 | 0 |
| `GLOBAL.BSA/CRYPT3.INF` | 4 | 4 | 0 | 0 | 0 |
| `GLOBAL.BSA/CRYPT4.INF` | 4 | 4 | 0 | 0 | 0 |
| `GLOBAL.BSA/CRYSTAL1.INF` | 2 | 2 | 0 | 0 | 0 |
| `GLOBAL.BSA/CRYSTAL3.INF` | 31 | 31 | 0 | 0 | 0 |
| `GLOBAL.BSA/CRYSTAL4.INF` | 3 | 3 | 0 | 0 | 0 |
| `GLOBAL.BSA/DAGOTH1.INF` | 3 | 3 | 0 | 0 | 0 |
| `GLOBAL.BSA/DAGOTH2.INF` | 12 | 12 | 0 | 0 | 0 |
| `GLOBAL.BSA/DAGOTH3.INF` | 3 | 3 | 0 | 0 | 0 |
| `GLOBAL.BSA/DEMO.INF` | 6 | 6 | 0 | 0 | 0 |
| `GLOBAL.BSA/ELDEN1.INF` | 1 | 1 | 0 | 0 | 0 |
| `GLOBAL.BSA/ELDEN2.INF` | 2 | 2 | 0 | 0 | 0 |
| `GLOBAL.BSA/FANG1.INF` | 16 | 16 | 0 | 0 | 0 |
| `GLOBAL.BSA/FANG2.INF` | 1 | 1 | 0 | 0 | 0 |
| `GLOBAL.BSA/FORTI2.INF` | 1 | 1 | 0 | 0 | 0 |
| `GLOBAL.BSA/GEMIN1.INF` | 3 | 3 | 0 | 0 | 0 |
| `GLOBAL.BSA/GEMIN2.INF` | 4 | 4 | 0 | 0 | 0 |
| `GLOBAL.BSA/HALLS1.INF` | 3 | 3 | 0 | 0 | 0 |
| `GLOBAL.BSA/HALLS2.INF` | 6 | 6 | 0 | 0 | 0 |
| `GLOBAL.BSA/HALLS3.INF` | 3 | 3 | 0 | 0 | 0 |
| `GLOBAL.BSA/IMPPAL1.INF` | 4 | 4 | 0 | 0 | 0 |
| `GLOBAL.BSA/IMPPAL2.INF` | 4 | 4 | 0 | 0 | 0 |
| `GLOBAL.BSA/IMPPAL3.INF` | 4 | 4 | 0 | 0 | 0 |
| `GLOBAL.BSA/IMPPAL4.INF` | 1 | 1 | 0 | 0 | 0 |
| `GLOBAL.BSA/KHU1.INF` | 8 | 8 | 0 | 0 | 0 |
| `GLOBAL.BSA/KHU2.INF` | 5 | 5 | 0 | 0 | 0 |
| `GLOBAL.BSA/KHUTEST.INF` | 1 | 1 | 0 | 0 | 0 |
| `GLOBAL.BSA/LABRNTH1.INF` | 13 | 13 | 0 | 0 | 0 |
| `GLOBAL.BSA/LABRNTH2.INF` | 4 | 4 | 0 | 0 | 0 |
| `GLOBAL.BSA/MAGE.INF` | 2 | 2 | 0 | 0 | 0 |
| `GLOBAL.BSA/MGTEMPL1.INF` | 7 | 7 | 0 | 0 | 0 |
| `GLOBAL.BSA/MGTEMPL2.INF` | 9 | 9 | 0 | 0 | 0 |
| `GLOBAL.BSA/MURK1.INF` | 5 | 5 | 0 | 0 | 0 |
| `GLOBAL.BSA/MURK2.INF` | 2 | 2 | 0 | 0 | 0 |
| `GLOBAL.BSA/NOBLE.INF` | 2 | 2 | 0 | 0 | 0 |
| `GLOBAL.BSA/NOBLE1.INF` | 2 | 2 | 0 | 0 | 0 |
| `GLOBAL.BSA/NOBLE2.INF` | 2 | 2 | 0 | 0 | 0 |
| `GLOBAL.BSA/NOBLE3.INF` | 2 | 2 | 0 | 0 | 0 |
| `GLOBAL.BSA/SD1.INF` | 3 | 3 | 0 | 0 | 0 |
| `GLOBAL.BSA/SD3.INF` | 1 | 1 | 0 | 0 | 0 |
| `GLOBAL.BSA/SELENE1.INF` | 5 | 5 | 0 | 0 | 0 |
| `GLOBAL.BSA/SELENE2.INF` | 3 | 3 | 0 | 0 | 0 |
| `GLOBAL.BSA/SKEEP1.INF` | 8 | 8 | 0 | 0 | 0 |
| `GLOBAL.BSA/SKEEP2.INF` | 8 | 8 | 0 | 0 | 0 |
| `GLOBAL.BSA/START.INF` | 6 | 6 | 0 | 0 | 0 |
| `GLOBAL.BSA/STKEEP1.INF` | 8 | 8 | 0 | 0 | 0 |
| `GLOBAL.BSA/TOWER.INF` | 4 | 4 | 0 | 0 | 0 |
| `GLOBAL.BSA/TOWER1.INF` | 4 | 4 | 0 | 0 | 0 |
| `GLOBAL.BSA/TOWER2.INF` | 2 | 2 | 0 | 0 | 0 |
| `GLOBAL.BSA/TOWER6.INF` | 2 | 2 | 0 | 0 | 0 |
| `GLOBAL.BSA/TOWER8.INF` | 3 | 3 | 0 | 0 | 0 |
| `GLOBAL.BSA/VILPAL.INF` | 2 | 2 | 0 | 0 | 0 |
| `MUGUILD.DAT` | 45 | 45 | 0 | 0 | 0 |
| `QUESTION.TXT` | 1 | 0 | 0 | 1 | 0 |
| `SELLING.DAT` | 75 | 75 | 0 | 0 | 0 |
| `SPELLMKR.TXT` | 43 | 43 | 0 | 0 | 0 |
| `TAVERN.DAT` | 75 | 75 | 0 | 0 | 0 |
| `TEMPLATE.DAT` | 810 | 810 | 0 | 0 | 0 |

## 상태 기준

- 번역 적용: 현재 오버라이드에 ID가 존재한다.
- 번역 필요: 실제 영문 문장이며 아직 오버라이드가 없다.
- 별도 파일로 처리: `QUESTION.TXT`처럼 전용 빌더가 완성본을 만든다.
- 비언어 제어값: `!`처럼 번역할 문장이 아닌 값이다.
