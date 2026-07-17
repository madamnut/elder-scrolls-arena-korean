# 번역 및 문체 규칙

## 기본 원칙

- 의미와 게임 기능을 우선한다.
- Elder Scrolls 세계관의 고유명사는 공식 한국어 표기가 확인되면 그것을 따른다.
- 공식 표기가 없으면 프로젝트 용어집에서 하나를 선택하고 일관되게 쓴다.
- 고어체는 분위기를 살리되 조작 안내와 시스템 문구는 즉시 이해되게 쓴다.
- 320×200 화면과 작은 글꼴을 고려해 영어보다 간결하게 번역한다.

## 문체

| 유형 | 권장 문체 |
|---|---|
| 예언·서사 | 장중한 서술체 |
| NPC 대사 | 인물 성격에 맞는 존대·반말 |
| 선택 질문 | 간결한 서술형 |
| 버튼 | 명사 또는 짧은 동사 |
| 시스템 경고 | 명확한 평서·명령형 |
| 도움말 | 현대적인 설명체 |

예:

```text
How do you wish to select your class?
→ 직업을 어떻게 선택하시겠습니까?

Choose thy class...
→ 직업을 선택하라...
```

## 공통 인게임 용어

첫 던전과 일반 시스템 메시지는 짧고 즉시 이해되는 현대적인 문체를 사용한다.

| 원문 | 번역 |
|---|---|
| Shift Gate | 전이의 문 |
| inventory | 인벤토리 |
| logbook / Journal | 일지 |
| camp / rest | 야영 / 휴식 |
| gold piece | 금화 |
| spell points | 마력 |
| critical strike | 치명타 |
| locked | 잠김 / 잠겼다 |
| pick a lock | 자물쇠를 따다 |
| Exit | 종료 |
| Print | 인쇄 |
| Imperial Dungeons | 제국 지하감옥 |
| Select target for pilfering... | 훔칠 대상을 선택하십시오... |
| You are in / It is / The date is | 현재 위치 / 현재 시각 / 날짜 |
| You are currently carrying | 소지 중량 |

시체·상자에 가져갈 것이 없다는 문장은 단순히 `쓸 것이 없다`고 하지 않고 `쓸 만한 것이 없다`로 통일한다. 예: `고블린에는 쓸 만한 것이 없다.`

아이템명이나 인물명이 `%s`로 삽입되는 짧은 문구는 조사를 억지로 붙이지 않고 `이름 + 명사` 또는 콜론 구조를 우선한다. 영문 아이템명이 들어와도 문장이 이해되어야 한다.

상태창과 일지 날짜에 쓰이는 탐리엘 달력은 제한된 실행 파일 공간 안에서 뜻을 살린 짧은 고유명으로 통일한다. 요일은 즉시 알아볼 수 있도록 현실의 대응 요일로 옮기고, `st/nd/rd/th`는 삭제한 뒤 `일`을 붙인다.

| 원문 | 번역 | 원문 | 번역 |
|---|---|---|---|
| Morning Star | 새벽별 | Sun's Dawn | 해오름 |
| First Seed | 첫씨앗 | Rain's Hand | 빗손길 |
| Second Seed | 둘째씨앗 | Mid Year | 한해중반 |
| Sun's Height | 태양절정 | Last Seed | 끝씨앗 |
| Hearthfire | 난롯불 | Frostfall | 서리철 |
| Sun's Dusk | 해질녘 | Evening Star | 저녁별 |
| Morndas / Tirdas | 월요일 / 화요일 | Middas / Turdas | 수요일 / 목요일 |
| Fredas / Loredas / Sundas | 금요일 / 토요일 / 일요일 | early morning / midnight | 이른 아침 / 자정 |

## 몬스터와 아이템 이름

- 직업명 19개는 영어를 유지하지만 몬스터명과 아이템명은 한글화한다.
- 재질과 기본 아이템명은 `재질 + 공백 + 이름` 순서로 조합한다: `철 단검`, `에보니 타워 방패`.
- 마법 접미사는 조합 순서를 바꾸지 않아도 자연스럽도록 괄호형을 쓴다: `강철 롱소드 (화염 폭풍)`.
- 열쇠 재질 표에는 영문 관사까지 들어 있으므로 관사를 남기지 않는다: `a Ruby → 루비`, 최종 표시는 `루비 열쇠`.
- 내구 상태는 짧은 UI 용어인 `파손`, `사용 불가`, `심한 손상`, `마모`, `사용품`, `약간 사용`, `거의 새것`, `새것`을 사용한다.

| 원문 | 번역 | 원문 | 번역 |
|---|---|---|---|
| Rat | 쥐 | Goblin | 고블린 |
| Lizard Man | 리자드맨 | Snow Wolf | 설원 늑대 |
| Wraith | 망령 | Homonculus | 호문쿨루스 |
| Fire Daemon | 화염 데몬 | Lich | 리치 |
| Staff | 지팡이 | Dagger | 단검 |
| Shortsword | 숏소드 | Broadsword | 브로드소드 |
| Cuirass | 흉갑 | Gauntlets | 건틀릿 |
| Greaves | 각반 | Pauldron | 견갑 |
| Potion of Stamina | 활력 물약 | Potion of Healing | 치유 물약 |
| Iron | 철 | Dwarven | 드워프제 |
| Adamantium | 아다만티움 | Ebony | 에보니 |

장비 상세 UI는 `Condition / Damage / AR / Weight / charge / use`를 각각 `상태 / 피해 / 방어도 / 무게 / 충전 / 사용 횟수`로 표기한다. `n/a`는 `없음`으로 쓴다.

## 본편 퀘스트와 컷신 용어

| 원문 | 번역 |
|---|---|
| Staff of Chaos | 혼돈의 지팡이 |
| Fang Lair | 팽 레어 |
| Dwarves of Kragen | 크라겐의 드워프 |
| Dragon's Teeth | 용의 이빨 산맥 |
| Great Wyrm | 거대한 고룡 |
| Jagar Tharn / Tharn | 제이거 탄 / 탄 |
| Glamorill | 글래모릴 |
| Labyrinthian | 라비린시안 |
| Fortress of Ice | 얼음 요새 |
| Elden Grove | 엘든 그로브 |
| Halls of Colossus | 콜로서스의 전당 |
| Great Divide | 대단층 |
| Crystal Tower | 수정탑 |
| Crypt of Hearts | 하츠 묘지 |
| Murkwood | 머크우드 |
| Dagoth-Ur | 다고스 우르 |
| Jewel of Fire | 불의 보석 |

리아 실메인의 꿈 대사는 장중하지만 짧은 명령형과 평서형을 사용한다. 플레이어 이름 치환자 앞뒤의 호칭은 문장마다 억지로 반복하지 않으며, `Staff`가 혼돈의 지팡이를 가리키는 본편 문맥에서는 일반 아이템 `지팡이`와 구분해 전체 이름을 쓴다.

## 자리표시자

원문의 자리표시자는 종류, 개수, 순서를 함부로 바꾸지 않는다.

```text
%s
%u
%d
%ra
%mm
%0
```

변경이 필요하면 해당 포맷 함수를 먼저 역공학하고 테스트를 추가한다.

## 제어 문자

- `\r`: Arena의 명시적 줄바꿈
- `\n`: 외부 텍스트 파일 줄 종료
- `0x09`: 문맥에 따라 색상 제어일 수 있음
- `0x0C`: 문맥에 따라 글꼴 전환일 수 있음

번역자가 임의로 제어 문자를 삭제하지 않는다.

## AKC 허용 문자

- ASCII `TAB`, `LF`, `CR`, `0x20–0x7F`
- 완성형 한글 `가–힣`

금지 또는 별도 처리 대상:

- 스마트 따옴표 `“ ” ‘ ’`
- 긴 대시와 특수 말줄임표
- 조합되지 않은 한글 자모
- 한자와 기타 유니코드 기호

따옴표는 ASCII `'` 또는 `"`, 말줄임표는 `...`를 사용한다.

## 직업명 참고표

게임에 표시되는 18개 직업명은 영어 원문을 유지한다. 아래 번역은 의미 확인과 번역 문맥을 위한 참고표이며 실행 파일에는 적용하지 않는다.

| 원문 | 번역 | 원문 | 번역 |
|---|---|---|---|
| Mage | 법사 | Spellsword | 마검사 |
| Battlemage | 전투마법사 | Sorceror | 소서러 |
| Healer | 치유사 | Nightblade | 밤의검객 |
| Bard | 악사 | Burglar | 절도범 |
| Rogue | 로그 | Acrobat | 곡예사 |
| Thief | 도적 | Assassin | 암살자 |
| Monk | 승려 | Archer | 궁수 |
| Ranger | 레인저 | Barbarian | 야만전사 |
| Warrior | 전사 | Knight | 기사 |

`Mage`, `Sorceror`, `Bard`, `Nightblade`처럼 역할이 겹치고 한국어 번역만으로 원본 직업을 구분하기 어려우므로 영어 표기를 보존한다.

## 능력치 배분 화면 용어

| 원문 | 번역 | 원문 | 번역 |
|---|---|---|---|
| Strength | 힘 | Intelligence | 지능 |
| Willpower | 의지 | Agility | 민첩 |
| Speed | 속도 | Endurance | 인내 |
| Personality | 매력 | Luck | 행운 |
| Damage | 근접 피해 | Max Kilos | 소지 한도 |
| Spell Pts. | 마력 | Magic Def. | 마법 저항 |
| To Hit | 명중 | To Def. | 회피 |
| Health (END modifier) | 성장 체력 | Heal Mod | 회복률 |
| Charisma | 카리스마 | Bonus Pts. | 잔여 스탯 |
| Health (current) | 체력 | Fatigue | 활력 |
| Gold | 금화 | Experience | 경험치 |
| Level | 레벨 | Done | 완료 |

`Fatigue`는 수치가 높을수록 활동 여유가 많은 자원이므로 누적된 피로처럼 읽히는 `피로` 대신 `활력`을 사용한다. `Bonus Pts.`는 한국 게임의 스탯 배분 문맥을 우선해 `잔여 스탯`으로 표기한다. END 옆의 `Health`는 현재 체력이 아니라 캐릭터 생성과 레벨 상승 때 더해지는 체력량이므로 `성장 체력`으로 구분한다.

## 지도 진입 전 캐릭터 생성 문구

| 원문 | 번역 |
|---|---|
| Choose thy class... | 직업을 선택하라. |
| What will be thy name, %s? | %s의 이름은? |
| Choose thy gender... | 성별을 선택하십시오. |

`%s`에는 영어로 유지한 선택 직업명이 들어간다. 원본 이름 입력기는 영문자와 공백만 받으므로 캐릭터 이름 자체의 한글 입력 지원은 별도 기능으로 다룬다.

## 질문 파일 규칙

`QUEST_KR.utf8.txt`는 다음 구조를 보존한다.

```text
1. 질문 본문
a) 선택지 (5v)
b) 선택지 (5l)
c) 선택지 (5c)
```

- 질문 번호는 1–40이다.
- 각 질문에는 `a)`, `b)`, `c)`가 하나씩 있다.
- `(5l)`, `(5c)`, `(5v)` 판정 태그는 각각 총 40개다.
- 판정 태그는 의미를 번역하거나 순서를 변경하지 않는다.
- 줄바꿈은 빌더가 화면 폭에 맞춰 재계산한다.

판정 의미:

| 태그 | 내부 범주 | 대략적 성향 |
|---|---|---|
| `l` | Logical | 마법·판단 중심 |
| `c` | Clever | 책략·도적 중심 |
| `v` | Violent | 전투·무력 중심 |

## 이미지 번역

- 원본 구도, 인물, 배경, 장식과 팔레트를 보존한다.
- 지정된 영어만 한국어로 교체한다.
- 저작권 문구 등 보존 범위를 작업 전에 명시한다.
- AI 편집 결과의 잘못된 추가 문구와 철자를 사람이 확인한다.
- 최종 해상도는 정확히 320×200으로 맞춘다.
- Arena 팔레트 양자화 결과를 별도로 확인한다.

## 검수 항목

- 오탈자와 띄어쓰기
- 고유명사 일관성
- 자리표시자 보존
- 줄바꿈과 화면 경계
- 버튼 의미와 실제 동작 일치
- 남성·여성 문법
- 숫자 단수·복수
- 저장 데이터에 영향을 주는 명칭 변경 여부
