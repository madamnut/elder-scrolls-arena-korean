#!/usr/bin/env python3
"""Patch the unpacked Arena 1.07 ACD.EXE renderer to call INT 60h.

The output requires ARENAKR.COM to be loaded first. This tool never overwrites
its input and validates the complete original routine bodies before patching.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from pathlib import Path
import re
import struct
import sys

from akc_codec import encode as encode_akc


EXPECTED_UNPACKED_SHA256 = "3d698ac22c1f7da49d87c78d80f89f3c3822ba3f62708b67f98fff3dac300a86"
WIDTH_START = 0x66F6
WIDTH_END = 0x673D
DRAW_START = 0x9E0A
DRAW_END = 0x9EC3
LINE_ADVANCE_START = 0x99C4
LINE_ADVANCE_END = 0x99D6
RACE_METRIC_HELPER_START = 0x670D
RACE_MEASUREMENT_START = 0x99F2
EXPECTED_RACE_MEASUREMENT = bytes.fromhex(
    "06 c4 36 34 b0 26 8a 0c 07 fe c1"
)

QUESTION_SCROLL_PATCHES = (
    # image offset, original bytes, HANGUL9 11px-scroll replacement
    (0x22534, bytes.fromhex("b9 00 50"), bytes.fromhex("b9 80 52")),  # 64 -> 66 rows
    (0x2260C, bytes.fromhex("c7 06 96 12 08 00"), bytes.fromhex("c7 06 96 12 06 00")),
    (0x22612, bytes.fromhex("83 3e 94 12 08"), bytes.fromhex("83 3e 94 12 06")),
    (0x22654, bytes.fromhex("83 c3 08"), bytes.fromhex("83 c3 0b")),  # y += 11
    (0x2266A, bytes.fromhex("2d 07 00"), bytes.fromhex("2d 05 00")),
    (0x226EB, bytes.fromhex("c7 06 9a 12 c0 08"), bytes.fromhex("c7 06 9a 12 80 0c")),
    (0x226FC, bytes.fromhex("bf 00 0a"), bytes.fromhex("bf c0 0d")),
    (0x22726, bytes.fromhex("81 3e 9a 12 c0 08"), bytes.fromhex("81 3e 9a 12 80 0c")),
    (0x22743, bytes.fromhex("be 00 0a"), bytes.fromhex("be c0 0d")),
    (0x22765, bytes.fromhex("83 c1 07"), bytes.fromhex("83 c1 05")),
    (0x22775, bytes.fromhex("bb 38 00"), bytes.fromhex("bb 37 00")),
    (0x2278D, bytes.fromhex("b9 00 46"), bytes.fromhex("b9 c0 44")),
    (0x227C4, bytes.fromhex("ba 08 00"), bytes.fromhex("ba 0b 00")),
)

# The compact bottom-of-screen item list has a fixed 31px viewport at
# y=145..175.  The English layout fits three short rows and then draws
# ``...More`` directly below them.  HANGUL9 occupies all nine glyph rows, so
# use two 11px item rows and reserve the third row for the continuation
# marker.  The quantity/input cursor uses its own row multiplier and must stay
# on the same 11px grid.
ITEM_LIST_GEOMETRY_PATCHES = (
    (0x167E0, bytes.fromhex("83 3e 7e a8 03"), bytes.fromhex("83 3e 7e a8 02")),
    (0x1680B, bytes.fromhex("83 c2 09"), bytes.fromhex("83 c2 0b")),
    (0x16820, bytes.fromhex("bb a9 00"), bytes.fromhex("bb a7 00")),
    (0x168AC, bytes.fromhex("b3 08"), bytes.fromhex("b3 0b")),
)

# The template-expansion path used by runtime cutscenes copies only a small
# ASCII allow-list into its final subtitle buffer. At this last lowercase
# range check, the original unsigned JBE copies 'a'..'z' and rejects every AKC
# byte. Signed JLE preserves 'a'..'z', still rejects 0x7B..0x7F, and also
# copies the signed-negative 0x80..0xFF bytes that form AKC lead/trail pairs.
CUTSCENE_AKC_FILTER_OFFSET = 0x1C00B
CUTSCENE_AKC_FILTER_SOURCE = bytes.fromhex("76 04")
CUTSCENE_AKC_FILTER_REPLACEMENT = bytes.fromhex("7e 04")

CUTSCENE_SUBTITLE_GEOMETRY_PATCHES = (
    # A 37px band (y=163..199) contains three full-height HANGUL9 lines.
    # Glyph rows are 166..174, 177..185, and 188..196, leaving 3px outer
    # margins and 2px between lines.
    (0x23104, bytes.fromhex("bb aa 00"), bytes.fromhex("bb a6 00")),
    (0x23124, bytes.fromhex("83 c3 0a"), bytes.fromhex("83 c3 0b")),
    # Clear all 37 rows of the subtitle band before drawing the next frame.
    (0x231B4, bytes.fromhex("bb a7 00 b9 40 01 ba 20 00"),
        bytes.fromhex("bb a3 00 b9 40 01 ba 25 00")),
)

# Common messages reached immediately after character creation. These are
# fixed NUL-terminated strings in the ACD load image, so each Korean string is
# deliberately kept within the original byte budget and the remaining bytes
# are cleared. Offsets are load-image offsets, not MZ file offsets.
INGAME_MESSAGE_PATCHES = (
    (0x3634B, "%ss cannot equip this item.\r", "%ss: 장비할 수 없다.\r"),
    (0x36368, "Do you wish to drop\rthe %s?\r", "%s\r버리겠습니까?\r"),
    (0x3642B, "Gold", "금화"),
    (0x37712, "it will take %d days to travel here.\r", "이동에는 %d일이 걸립니다.\r"),
    (0x3776C, "You are already in %s.\r", "이미 %s에 있습니다.\r"),
    (0x37784, "You can not travel until you have chosen\ra destination city, town, or village.\r",
        "먼저 목적지를 선택해야 합니다.\r"),
    (0x377D4, "This lock has nothing to fear from you...", "자물쇠가 당신을 비웃는 듯하다..."),
    (0x377FE, "It'd be a miracle if you picked this lock...", "이걸 딴다면 기적일 것이다..."),
    (0x3782B, "This lock looks to be beyond your skills...", "실력으로는 열 수 없을 듯하다..."),
    (0x37857, "You doubt your ability to open this lock...", "열 수 있을지 의심스럽다..."),
    (0x37883, "This lock looks difficult...", "따기 어려워 보인다..."),
    (0x378A0, "You would be challenged by this lock...", "제법 까다로운 자물쇠다..."),
    (0x378C8, "This lock would prove a good challenge...", "도전할 만한 자물쇠다..."),
    (0x378F2, "You think you should be able to pick this lock...", "아마 딸 수 있을 것 같다..."),
    (0x37924, "This lock seems relatively easy...", "비교적 쉬워 보인다..."),
    (0x37947, "You are amused by this lock...", "우스울 만큼 쉬워 보인다..."),
    (0x37966, "You laugh at the amateur quality of this lock...", "서툴게 만든 자물쇠다..."),
    (0x37997, "You see a pathetic excuse for a lock...", "자물쇠라 부르기도 민망하다..."),
    (0x379BF, "This lock is an insult to your abilities...", "당신의 실력을 모욕하는 수준이다..."),
    (0x379EB, "This is a magically held lock...", "마법으로 잠긴 자물쇠다..."),
    (0x38184, "This item will be lost here.\rDrop anyway?\r", "버리면 사라집니다.\r계속합니까?\r"),
    (0x381AF, "There is no room to drop this here.\r", "여기에는 버릴 공간이 없다.\r"),
    (0x381D4, "You can only equip one %s.\r", "%s은 하나만 장비 가능.\r"),
    (0x381F0, "This item can't be equipped.\r", "이 물건은 장비할 수 없다.\r"),
    (0x3820E, "This item can't be dropped.\r", "이 물건은 버릴 수 없다.\r"),
    (0x3822B, "Drop what?\r", "버릴 물건?\r"),
    (0x38237, "You are not a spellcaster!\r", "주문을 쓸 수 없다!\r"),
    (0x38253, "This item is needed to\rcomplete your quest...\rSee your logbook...\r",
        "퀘스트에 필요한 물건이다.\r일지를 확인하라.\r"),
    (0x39423, "%d kgs\r", "%d kg\r"),
    (0x3942B, "Condition: %s\r", "상태: %s\r"),
    (0x3943A, "Damage: %d - %d  Weight: ", "피해: %d - %d  무게: "),
    (0x39454, "-%d to AR   Weight: ", "방어도 -%d   무게: "),
    (0x39469, "%d charge(s) left\r", "충전 %d회 남음\r"),
    (0x3947C, "+%d to %s\r", "+%d %s\r"),
    (0x39487, "-%d to AR   Weight: n/a\r", "방어도 -%d   무게: 없음\r"),
    (0x394A0, "%d use(s) left...\r", "%d회 남음...\r"),
    (0x394B3, "1 use left    Weight: n/a\rCondition: Fragile\r",
        "1회 남음   무게: 없음\r상태: 취약\r"),
    (0x3D3C5, "Your inventory is empty.", "인벤토리가 비었다."),
    (0x3D3DE, "Your inventory is full.", "인벤토리가 가득 찼다."),
    (0x3EB98, "Morning Star", "새벽별"),
    (0x3EBA5, "Sun's Dawn", "해오름"),
    (0x3EBB0, "First Seed", "첫씨앗"),
    (0x3EBBB, "Rain's Hand", "빗손길"),
    (0x3EBC7, "Second Seed", "둘째씨앗"),
    (0x3EBD3, "Mid Year", "한해중반"),
    (0x3EBDC, "Sun's Height", "태양절정"),
    (0x3EBE9, "Last Seed", "끝씨앗"),
    (0x3EBF3, "Hearthfire", "난롯불"),
    (0x3EBFE, "Frostfall", "서리철"),
    (0x3EC08, "Sun's Dusk", "해질녘"),
    (0x3EC13, "Evening Star", "저녁별"),
    (0x3EC2E, "Morndas", "월요일"),
    (0x3EC36, "Tirdas", "화요일"),
    (0x3EC3D, "Middas", "수요일"),
    (0x3EC44, "Turdas", "목요일"),
    (0x3EC4B, "Fredas", "금요일"),
    (0x3EC52, "Loredas", "토요일"),
    (0x3EC5A, "Sundas", "일요일"),
    (0x3F690, "Locked.", "잠김."),
    (0x3FA1C, "Travel distance: %d kilometers", "이동 거리: %d킬로미터"),
    (0x3FBC7, "The magic coffer yields %d gold.", "%d 금화를 얻었다."),
    (0x3FBE8, "You have already used that today...", "오늘은 이미 사용했다..."),
    (0x402E3, "%u hour passed....", "%u시간 경과...."),
    (0x402F6, "%u hours passed...", "%u시간 경과..."),
    (0x40309, "%u hour remaining...", "%u시간 남음..."),
    (0x4031E, "%u hours remaining...", "%u시간 남음..."),
    (0x40336, " CAMP OPTIONS\r", " 휴식 선택\r"),
    (0x40384, "How many hours do you wish to rest?         ", "몇 시간 쉬겠습니까?"),
    (0x403B1, "You are healed...", "회복되었다..."),
    (0x403C3, "You wake up... ", "잠에서 깼다..."),
    (0x403D3, "Your time is up...", "시간이 끝났다..."),
    (0x403E9, "There are enemies nearby...", "근처에 적이 있다..."),
    (0x40405, "You don't need to rest.", "쉴 필요가 없다."),
    (0x40533, "This item will encumber you.", "이 물건은 짐이 된다."),
    (0x405DB, "Imperial Dungeons", "제국 지하감옥"),
    (0x40670, "The %s has nothing usable.", "%s에는 쓸 만한 것이 없다."),
    (0x406A5, "You have found %s key.", "%s 열쇠를 찾았다."),
    (0x406BC, "You open door with %s key.", "%s 열쇠로 문을 열었다."),
    (0x406D7, "There is nothing usable left here.", "더는 쓸 만한 것이 없다."),
    (0x406FA, "You have found %u gold pieces!!", "%u 금화를 찾았다!"),
    (0x40736, "%u gold piece", "%u 금화"),
    (0x40744, "Bag of %u gold pieces", "%u 금화 자루"),
    (0x40838, "%s, %u%s of %s in the year 3E %d\r", "%s, %u%s일 %s, 3E %d년\r"),
    (0x4086D, "early morning", "이른 아침"),
    (0x4087B, "in the morning", "아침"),
    (0x4088A, "noon", "정오"),
    (0x4088F, "in the afternoon", "오후"),
    (0x408A0, "in the evening", "저녁"),
    (0x408AF, "at night", "밤"),
    (0x408B8, "midnight", "자정"),
    (0x409FA, "st", ""),
    (0x409FD, "nd", ""),
    (0x40A00, "rd", ""),
    (0x40A03, "th", ""),
    (0x4155C, "Select target for pilfering...", "훔칠 대상을 선택하십시오..."),
    (0x4157B, "You are in %s.\rIt is %s.\rThe date is %sYou are currently carrying %d kg out of %d kg.\r",
        "현재 위치: %s.\r현재 시각: %s.\r날짜: %s소지 중량: %d / %d kg.\r"),
    (0x416D2, "You can't camp. Enemies are nearby!!!", "적이 가까이 있어 쉴 수 없다!"),
    (0x416F8, "You can't camp here.", "여기서는 쉴 수 없다."),
    (0x4170D, "You cannot travel from here.", "여기서는 이동할 수 없다."),
    (0x4172A, "You cannot travel when monsters are near...", "괴물이 가까이 있어 이동할 수 없다..."),
    (0x41756, "You cannot travel from a boat...", "배에서는 이동할 수 없다..."),
    (0x41843, "Unable to save game properly.\rDisk may be full or bad.\r",
        "게임 저장에 실패했습니다.\r디스크를 확인하십시오.\r"),
    (0x418D1, "You cannot save in a tavern, store or temple...",
        "여기서는 게임을 저장할 수 없다..."),
    (0x4190F, "No game saved here....", "저장 게임이 없다..."),
    (0x42128, "On this body you find %d gold pieces.", "시체에서 %d 금화를 찾았다."),
    (0x433AB, "Locked.", "잠김."),
    (0x433B3, "You are unable to pick the lock...\r", "자물쇠를 따지 못했다...\r"),
    (0x434E0, "You are so fatigued that you\rsimply drop where you stand.\r\nOne hour later....\r",
        "피로에 지쳐\r그 자리에서 쓰러졌다.\r\n한 시간 뒤....\r"),
    (0x4352F, "Fatigue overcomes you and\rsends you to a watery grave....\r",
        "피로에 지쳐\r물속에서 죽고 말았다....\r"),
    (0x4356A, "You drop from exhaustion and\rquickly fall prey to monsters....\r",
        "피로로 쓰러져\r괴물의 먹이가 되었다....\r"),
    (0x435FA, "Failure...", "실패..."),
    (0x43605, "Success...", "성공..."),
    (0x43610, "Critical strike...", "치명타..."),
    (0x43623, "Open locked chest ?", "상자를 엽니까?"),
    (0x43637, "Lock won't budge...", "열리지 않는다..."),
    (0x4364B, "The chest opens...", "상자가 열렸다..."),
    (0x436D3, "You see a worthless key...", "쓸모없는 열쇠다..."),
    (0x43777, "Silence spell prevents spell casting.", "침묵 때문에 주문을 쓸 수 없다."),
    (0x4379D, "Not enough spell points...", "마력이 부족하다..."),
    (0x43935, "Pick spell target...", "주문 대상 선택..."),
    (0x4394A, "Fire spell at target...", "대상에게 주문 시전..."),
    (0x43962, "Release spell in your area...", "주변에 주문 방출..."),
    (0x43ED4, "You see a %s...", "%s 발견..."),
    (0x44261, "Door is locked.", "문이 잠겼다."),
    (0x44271, "Unable to open lock...", "자물쇠 열기 실패..."),
)

# Runtime-composed gameplay names. Each group is a fixed-count sequential
# NUL-string table selected by Arena's common "find the nth string" routine.
# Repacking is safe inside the original aggregate span, but the count and
# order must never change. The monster table also contains the English class
# names after its 23 monsters; those class names intentionally remain English.
GAMEPLAY_NAME_TABLES = (
    (
        0x36DBE,
        (
            "Rat", "Goblin", "Lizard Man", "Wolf", "Snow Wolf", "Orc",
            "Skeleton", "Minotaur", "Spider", "Ghoul", "Hell Hound", "Ghost",
            "Zombie", "Troll", "Wraith", "Homonculus", "Ice Golem",
            "Stone Golem", "Iron Golem", "Fire Daemon", "Medusa", "Vampire",
            "Lich", "Mage", "Spellsword", "Battlemage", "Sorceror", "Healer",
            "Nightblade", "Bard", "Burglar", "Rogue", "Acrobat", "Thief",
            "Assassin", "Monk", "Archer", "Ranger", "Barbarian", "Warrior",
            "Knight", "BattleMage",
        ),
        (
            "쥐", "고블린", "리자드맨", "늑대", "설원 늑대", "오크",
            "스켈레톤", "미노타우로스", "거미", "구울", "헬하운드", "유령",
            "좀비", "트롤", "망령", "호문쿨루스", "얼음 골렘", "돌 골렘",
            "철 골렘", "화염 데몬", "메두사", "뱀파이어", "리치", "Mage",
            "Spellsword", "Battlemage", "Sorceror", "Healer", "Nightblade",
            "Bard", "Burglar", "Rogue", "Acrobat", "Thief", "Assassin",
            "Monk", "Archer", "Ranger", "Barbarian", "Warrior", "Knight",
            "BattleMage",
        ),
        "monster-and-class-name",
    ),
    (
        0x3DC04,
        (
            "Staff", "Dagger", "Shortsword", "Broadsword", "Saber",
            "Longsword", "Claymore", "Tanto", "Wakizashi", "Katana",
            "Dai-Katana", "Mace", "Flail", "War Hammer", "War Axe",
            "Battle Axe", "Short Bow", "Long Bow",
        ),
        (
            "지팡이", "단검", "숏소드", "브로드소드", "세이버", "롱소드",
            "클레이모어", "탄토", "와키자시", "카타나", "다이카타나",
            "메이스", "플레일", "워해머", "워액스", "배틀액스", "숏보우",
            "롱보우",
        ),
        "weapon-name",
    ),
    (
        0x3DD1F,
        (
            "of Strength", "of Shock Resistance", "of Will", "of Agility",
            "of Speed", "of Endurance", "of Fire Resistance", "of Luck",
            "of Lightning", "of Frost Resistance", "of Passwall",
            "of Life Steal", "of Paralyzation", "of Firestorm",
        ),
        (
            "(힘)", "(충격 저항)", "(의지)", "(민첩)", "(속도)", "(인내)",
            "(화염 저항)", "(행운)", "(번개)", "(냉기 저항)", "(벽 통과)",
            "(생명 흡수)", "(마비)", "(화염 폭풍)",
        ),
        "weapon-enchantment",
    ),
    (
        0x3DE24,
        (
            "Cuirass", "Gauntlets", "Greaves", "Pauldron (L)", "Pauldron (R)",
            "Helm", "Boots", "Buckler", "Round Shield", "Kite Shield",
            "Tower Shield",
        ),
        (
            "흉갑", "건틀릿", "각반", "왼쪽 견갑", "오른쪽 견갑", "투구",
            "장화", "버클러", "원형 방패", "카이트 방패", "타워 방패",
        ),
        "armor-name",
    ),
    (
        0x3DE91,
        (
            "Chest", "Hands", "Legs", "Shoulder", "Shoulder", "Head", "Foot",
            "General", "General", "General", "General",
        ),
        (
            "흉부", "손", "다리", "어깨", "어깨", "머리", "발", "일반",
            "일반", "일반", "일반",
        ),
        "equipment-slot-name",
    ),
    (
        0x3DF4D,
        (
            "of Strength", "of Intelligence", "of Willpower", "of Agility",
            "of Speed", "of Endurance", "of Personality", "of Luck",
            "of Jumping", "of Levitation", "of Passwall", "of Invisibility",
            "of Spell Reflection", "of Regeneration",
        ),
        (
            "(힘)", "(지능)", "(의지)", "(민첩)", "(속도)", "(인내)",
            "(매력)", "(행운)", "(도약)", "(공중 부양)", "(벽 통과)",
            "(투명화)", "(주문 반사)", "(재생)",
        ),
        "armor-enchantment",
    ),
    (
        0x3E03F,
        ("Iron", "Steel", "Silver", "Elven", "Dwarven", "Mithril", "Adamantium", "Ebony"),
        ("철", "강철", "은", "엘프제", "드워프제", "미스릴", "아다만티움", "에보니"),
        "equipment-material",
    ),
    (
        0x3E2CD,
        (
            "Potion of Stamina", "Potion of Strength", "Potion of Healing",
            "Potion of Restore Power", "Potion of Resist Fire",
            "Potion of Resist Cold", "Potion of Resist Shock",
            "Potion of Cure Disease", "Potion of Heal True",
            "Potion of Levitation", "Potion of Resist Poison",
            "Potion of Free Action", "Potion of Cure Poison",
            "Potion of Invisibility", "Potion of Purification",
        ),
        (
            "활력 물약", "힘의 물약", "치유 물약", "마력 회복 물약",
            "화염 저항 물약", "냉기 저항 물약", "충격 저항 물약",
            "질병 치료 물약", "완전 치유 물약", "공중 부양 물약",
            "독 저항 물약", "자유 행동 물약", "해독 물약", "투명화 물약",
            "정화 물약",
        ),
        "potion-name",
    ),
    (
        0x3EE2B,
        (
            "a Brass", "an Iron", "a Steel", "a Silver", "a Gold", "a Mithril",
            "an Amethyst", "a Diamond", "an Emerald", "a Ruby", "a Sapphire",
            "a Crystal",
        ),
        (
            "황동", "철", "강철", "은", "금", "미스릴", "자수정", "금강석",
            "에메랄드", "루비", "사파이어", "수정",
        ),
        "key-material",
    ),
    (
        0x417F1,
        (
            "Broken", "Useless", "Battered", "Worn", "Used", "Slightly Used",
            "Almost New", "New", "Potion",
        ),
        (
            "파손", "사용 불가", "심한 손상", "마모", "사용품", "약간 사용",
            "거의 새것", "새것", "물약",
        ),
        "item-condition",
    ),
)

CHARSTAT_GEOMETRY_PATCHES = (
    # Primary values: y = 38 + (index * 11), replacing 52 + (index * 8).
    (0x1279D, bytes.fromhex("bb 34 00"), bytes.fromhex("bb 26 00")),
    (0x127B5, bytes.fromhex("b8 1a 00"), bytes.fromhex("b8 19 00")),
    (0x127BF, bytes.fromhex("83 c3 08"), bytes.fromhex("83 c3 0b")),
    # Status values aligned to the artist-finished Korean CHARSTAT.IMG.
    (0x12738, bytes.fromhex("b8 2d 00"), bytes.fromhex("b8 19 00")),  # gold x: 45 -> 25
    (0x1273B, bytes.fromhex("bb 90 00"), bytes.fromhex("bb a1 00")),  # gold y: 144 -> 161
    (0x127DA, bytes.fromhex("b8 2d 00"), bytes.fromhex("b8 19 00")),  # health x: 45 -> 25
    (0x127DD, bytes.fromhex("bb 7f 00"), bytes.fromhex("bb 8b 00")),  # health y: 127 -> 139
    (0x12805, bytes.fromhex("b8 2d 00"), bytes.fromhex("b8 19 00")),  # vitality x: 45 -> 25
    (0x12808, bytes.fromhex("bb 87 00"), bytes.fromhex("bb 96 00")),  # vitality y: 135 -> 150
    (0x12817, bytes.fromhex("bb 3c 00"), bytes.fromhex("bb 31 00")),  # spell points y
    (0x1281D, bytes.fromhex("b8 2d 00"), bytes.fromhex("b8 56 00")),  # level x
    (0x12820, bytes.fromhex("bb a7 00"), bytes.fromhex("bb 96 00")),  # level y
    (0x12838, bytes.fromhex("b8 2d 00"), bytes.fromhex("b8 56 00")),  # experience x
    (0x1283B, bytes.fromhex("bb 9e 00"), bytes.fromhex("bb 8b 00")),  # experience y
    # Derived values aligned two pixels below their 9px Korean labels.
    (0x1286F, bytes.fromhex("b8 91 00"), bytes.fromhex("b8 93 00")),  # max kilos x
    (0x12872, bytes.fromhex("bb 34 00"), bytes.fromhex("bb 26 00")),  # max kilos y
    (0x1287C, bytes.fromhex("bb 34 00"), bytes.fromhex("bb 26 00")),  # damage y
    (0x1288A, bytes.fromhex("bb 5c 00"), bytes.fromhex("bb 5d 00")),  # health growth y
    (0x12895, bytes.fromhex("b8 91 00"), bytes.fromhex("b8 93 00")),  # healing rate x
    (0x12898, bytes.fromhex("bb 5c 00"), bytes.fromhex("bb 5d 00")),  # healing rate y
    (0x128CD, bytes.fromhex("bb 44 00"), bytes.fromhex("bb 3c 00")),  # magic defense y
    (0x128DA, bytes.fromhex("b8 91 00"), bytes.fromhex("b8 93 00")),  # to defend x
    (0x128DD, bytes.fromhex("bb 4c 00"), bytes.fromhex("bb 47 00")),  # to defend y
    (0x128EB, bytes.fromhex("bb 4c 00"), bytes.fromhex("bb 47 00")),  # to hit y
    (0x128F9, bytes.fromhex("bb 64 00"), bytes.fromhex("bb 68 00")),  # charisma y
    # Remaining-stat counter follows BONUS.IMG from (45,109) to (62,119).
    (0x12C26, bytes.fromhex("b8 5c 00"), bytes.fromhex("b8 6e 00")),
    (0x12C29, bytes.fromhex("bb 71 00"), bytes.fromhex("bb 7d 00")),
    # Selected attribute arrows and their redraw rectangle.
    (0x12BA3, bytes.fromhex("c6 06 97 12 38"), bytes.fromhex("c6 06 97 12 2c")),
    (0x12C5C, bytes.fromhex("bb 30 00"), bytes.fromhex("bb 22 00")),
    (0x12C62, bytes.fromhex("ba 48 00"), bytes.fromhex("ba 5d 00")),
    (0x12C77, bytes.fromhex("c6 06 97 12 38"), bytes.fromhex("c6 06 97 12 2c")),
    (0x12C89, bytes.fromhex("26 c7 44 02 30 00"), bytes.fromhex("26 c7 44 02 22 00")),
    (0x12E1E, bytes.fromhex("bb 30 00"), bytes.fromhex("bb 22 00")),
    (0x12E24, bytes.fromhex("ba 48 00"), bytes.fromhex("ba 5d 00")),
    (0x12E40, bytes.fromhex("b8 08 00"), bytes.fromhex("b8 0b 00")),
    (0x12E4E, bytes.fromhex("05 30 00"), bytes.fromhex("05 22 00")),
    (0x12E5C, bytes.fromhex("05 08 00"), bytes.fromhex("05 0b 00")),
)

CHARSTAT_MENU_IMAGE_OFFSET = 0x37A72
CHARSTAT_MENU_RECORD_SIZE = 0x62
CHARSTAT_MENU_RECTS = (
    ((0, 170, 31, 17), (12, 178, 28, 14)),
    *(( (7, 52 + (index * 8), 30, 8), (3, 36 + (index * 11), 35, 9) ) for index in range(8)),
    ((38, 48, 8, 16), (38, 34, 8, 16)),
)

MAIN_MENU_HITBOX_IMAGE_OFFSET = 0x38A60
MAIN_MENU_HITBOX_RECORD_SIZE = 0x62
MAIN_MENU_HITBOXES = (
    # label, original (x, y, width, height), Korean-menu rectangle
    ("load game", (0, 0, 320, 63), (0, 51, 320, 14)),
    ("start new game", (0, 110, 320, 20), (0, 104, 320, 14)),
    ("exit", (0, 143, 320, 30), (0, 151, 320, 13)),
)

ARENA_DATA_IMAGE_BASE = 0x3BA00
YES_NO_POINTER_TABLE_IMAGE_OFFSET = 0x40563
EXPECTED_YES_NO_POINTER_TABLE = bytes.fromhex("69 4b 6e 4b 00 00")
CHAR_CREATION_PROVINCES_IMAGE_OFFSET = 0x3E906
CHAR_CREATION_PROVINCES = (
    "High Rock",
    "Hammerfell",
    "Skyrim",
    "Morrowind",
    "Summurset",
    "Valenwood",
    "Elsweyr",
    "Black Marsh",
)
PREFERRED_ATTRIBUTES_IMAGE_OFFSET = 0x36034
PREFERRED_ATTRIBUTES = (
    "intelligent and willful",
    "strong and intelligent",
    "quick and intelligent",
    "intelligent and agile",
    "intelligent and willful",
    "agile and intelligent",
    "intelligent and personable",
    "agile and quick",
    "strong and intelligent",
    "agile and quick",
    "agile and intelligent",
    "strong and agile",
    "agile and hardy",
    "strong and agile",
    "strong and intelligent",
    "strong and hardy",
    "strong and hardy",
    "strong and willful",
)
ATTRIBUTE_NAMES_IMAGE_OFFSET = 0x3E500
ATTRIBUTE_NAMES = (
    "Strength",
    "Intelligence",
    "Willpower",
    "Agility",
    "Speed",
    "Endurance",
    "Personality",
    "Luck",
)
RACE_PLURAL_NAMES_IMAGE_OFFSET = 0x3E549
RACE_SINGULAR_NAMES_IMAGE_OFFSET = 0x3E594
RACE_PLURAL_NAMES = (
    "Bretons",
    "Redguards",
    "Nords",
    "Dark Elves",
    "High Elves",
    "Wood Elves",
    "Khajiit",
    "Argonians",
)
RACE_SINGULAR_NAMES = (
    "Breton",
    "Redguard",
    "Nord",
    "Dark Elf",
    "High Elf",
    "Wood Elf",
    "Khajiit",
    "Argonian",
)
RACE_NOTICE_ROUTINE_START = 0x1431E
RACE_NOTICE_ROUTINE_END = 0x143A9
EXPECTED_RACE_NOTICE_ROUTINE_SHA256 = (
    "56a055f011591f9caa575be72d6444e622663d1c47c135544d4cf872ce243d08"
)
RACE_NOTICE_TEXTS = (
    "그대의 종족은 고대 갈렌의\n드루이드에게서 이어졌다.\n재치가 빠르고 신비술에 강하며,\n영리하고 학구적인 백성이다.\n그 재능으로 다른 이들을\n깨달음으로 이끈다...",
    "그대의 종족에게 과거는 없다.\n타이버 전쟁에서 해머펠을 굳게\n지킨 수호자들이기 때문이다.\n세월이 흘러도 피눈물을 흘리며\n지킨 땅을 놓지 않았으니,\n이제 대지와 바위의 힘과 인내가\n그대의 것이 되었다...",
    "그대의 종족은 얼음 빙하를\n휩쓰는 북풍처럼 강인하다.\n혹독한 북극의 추위는 백성을\n삶의 잔혹하고 쓰라린 시련에\n맞설 수 있도록 단련했다...",
    "그대의 종족은 어머니의 품에서만\n피어나는 검은 장미의 가시처럼\n치명적이다. 낮의 형제들이 지닌\n우아함을 모두 간직했으나,\n그대의 어머니는 달이며 그대는\n밤에 태어난 그 자녀들이다...",
    "그대의 종족은 키가 크고 위엄이\n있으며, 군주들 가운데 왕이다.\n이 땅에서 처음 봄바람을 마시고\n바람과 함께 날렵하게 뛰었다.\n밤의 여왕만이 모습을 드러내는\n어둠 속에서도 모든 것을 본다...",
    "그대의 종족은 숲과 그 안의\n생명들과 하나다. 그 힘은 대지의\n어머니에게서 직접 흘러나온다.\n그대는 세계와 하나다...",
    "그대의 종족은 사막에서 태어났다.\n그곳의 삶은 잔혹하고 가혹하며,\n죽음은 독수리의 날개를 타고 온다.\n그대는 날렵한 고양잇과 종족이자\n황무지의 치명적인 사냥꾼이다...",
    "그대의 종족은 늪에서 태어나\n탁 트인 들판을 멀리해 왔다.\n그대는 남들과 다른 사냥꾼으로,\n고요하고 검은 물속에서 먹잇감을\n끈질기게 뒤쫓는다...",
)

EXPECTED_WIDTH = bytes.fromhex(
    "1e0657561e078bfebfa03b8ec726c43e34b033d2f604ff7427803c20750a268a45019803d0"
    "42eb15578a0422c0780d2c2072099803f8268a059803d05f46ebd48bc25e5f071fc3"
)
EXPECTED_DRAW = bytes.fromhex(
    "5506571e50b8a03b8ed858a3b6ad891eb8ad03db8bbfa0a68e0600a91fac22c00f8491002c"
    "20746d7cf31e565750b8a03b8ed858fec88a1e8892538ad832ff32e48be8033eb6adc53634"
    "b08a1432f6508bc303c0f6e28bd8585603f58a4c0132ed5e03f383c65f87ca5b5751508bca"
    "8b2c83c60203ed730326881d47e2f658595f81c74001e2e3bea03b8ede0116b6ad5f5e1feb"
    "881e56bea03b8edec53634b08a440132e4fec0bea03b8ede0106b6ad5e1fe968ff5f075dc3"
)
EXPECTED_LINE_ADVANCE = bytes.fromhex(
    "06 8e 06 36 b0 26 a0 00 00 07 32 e4 fe c0 01 06 50 a8"
)


class PatchError(ValueError):
    pass


def mz_header_size(data: bytes) -> int:
    if len(data) < 28 or data[:2] != b"MZ":
        raise PatchError("입력 파일이 DOS MZ 실행 파일이 아닙니다.")
    return struct.unpack_from("<H", data, 8)[0] * 16


def relocation_offsets(data: bytes) -> set[int]:
    count = struct.unpack_from("<H", data, 6)[0]
    table = struct.unpack_from("<H", data, 24)[0]
    offsets: set[int] = set()
    for index in range(count):
        offset, segment = struct.unpack_from("<HH", data, table + (index * 4))
        offsets.add((segment * 16) + offset)
    return offsets


def make_width_stub(length: int, interrupt: int) -> bytes:
    # Keep the relocated 0x3BA0 immediate at image offset 0x66FF.
    stub = bytes.fromhex(
        "1e 06 57 56 1e 07 8b fe bf a0 3b 8e c7 "
        "ba 00 00"
    ) + bytes((0xCD, interrupt)) + bytes.fromhex("5e 5f 07 1f c3")
    return stub.ljust(length, b"\x90")


def make_draw_stub(length: int, interrupt: int) -> bytes:
    # Keep the relocated 0x3BA0 immediate at image offset 0x9E10. ES receives
    # Arena's data segment while DS:SI remains the caller's text pointer.
    stub = bytes.fromhex("55 06 57 1e 50 b8 a0 3b 8e c0 58 ba 01 00")
    stub += bytes((0xCD, interrupt)) + bytes.fromhex("1f 5f 07 5d c3")
    return stub.ljust(length, b"\x90")


def make_line_advance_stub(interrupt: int) -> bytes:
    # Load the current font height into AL, then ask the TSR for a line
    # advance. LES BX is one byte shorter than the original segment load and
    # leaves enough room for the new API call without moving surrounding code.
    stub = bytes.fromhex("06 c4 1e 34 b0 26 8a 07 07 ba 02 00")
    stub += bytes((0xCD, interrupt)) + bytes.fromhex("01 06 50 a8")
    if len(stub) != LINE_ADVANCE_END - LINE_ADVANCE_START:
        raise AssertionError(len(stub))
    return stub


def apply_question_scroll_geometry(image: memoryview) -> None:
    """Convert the question scroll's private 8px row grid to HANGUL9 11px."""
    for offset, source, replacement in QUESTION_SCROLL_PATCHES:
        if len(source) != len(replacement):
            raise AssertionError((offset, len(source), len(replacement)))
        actual = bytes(image[offset : offset + len(source)])
        if actual != source:
            raise PatchError(
                f"질문 스크롤 코드 0x{offset:X}의 원본 바이트가 예상과 다릅니다: "
                f"{actual.hex()} != {source.hex()}"
            )
        image[offset : offset + len(source)] = replacement


def apply_item_list_geometry(image: memoryview) -> None:
    """Fit item rows and the continuation marker in the 31px HUD list."""
    for offset, source, replacement in ITEM_LIST_GEOMETRY_PATCHES:
        if len(source) != len(replacement):
            raise AssertionError((offset, len(source), len(replacement)))
        actual = bytes(image[offset : offset + len(source)])
        if actual != source:
            raise PatchError(
                f"item-list geometry at 0x{offset:X} differs from the "
                f"supported ACD.EXE: {actual.hex()} != {source.hex()}"
            )
        image[offset : offset + len(source)] = replacement


def apply_cutscene_akc_filter(image: memoryview) -> None:
    """Preserve AKC bytes in the final runtime-cutscene subtitle buffer."""
    offset = CUTSCENE_AKC_FILTER_OFFSET
    source = CUTSCENE_AKC_FILTER_SOURCE
    replacement = CUTSCENE_AKC_FILTER_REPLACEMENT
    actual = bytes(image[offset : offset + len(source)])
    if actual != source:
        raise PatchError(
            f"cutscene AKC filter at 0x{offset:X} differs from the supported ACD.EXE: "
            f"{actual.hex()} != {source.hex()}"
        )
    image[offset : offset + len(replacement)] = replacement


def apply_cutscene_subtitle_geometry(image: memoryview) -> None:
    """Fit three full-height HANGUL9 rows into the expanded subtitle band."""
    for offset, source, replacement in CUTSCENE_SUBTITLE_GEOMETRY_PATCHES:
        if len(source) != len(replacement):
            raise AssertionError((offset, len(source), len(replacement)))
        actual = bytes(image[offset : offset + len(source)])
        if actual != source:
            raise PatchError(
                f"cutscene subtitle geometry at 0x{offset:X} differs from the "
                f"supported ACD.EXE: {actual.hex()} != {source.hex()}"
            )
        image[offset : offset + len(source)] = replacement


def apply_ingame_messages(image: memoryview) -> None:
    """Replace common in-game messages without moving their pointer table."""
    # Match one C printf conversion, not the ordinary letters immediately
    # following it. The status format contains ``%sYou`` (a ``%s`` followed
    # by the next English sentence), which the former broad regex incorrectly
    # treated as one placeholder.
    placeholder_re = re.compile(
        r"%(?:[-+ #0]*\d*(?:\.\d+)?[hlLzjt]*[diuoxXfFeEgGaAcspn%])"
    )
    for offset, source_text, replacement_text in INGAME_MESSAGE_PATCHES:
        source = source_text.encode("ascii")
        replacement = encode_akc(replacement_text)
        source_placeholders = Counter(placeholder_re.findall(source_text))
        replacement_placeholders = Counter(placeholder_re.findall(replacement_text))
        if source_placeholders != replacement_placeholders:
            raise PatchError(
                f"in-game message placeholders differ at 0x{offset:X}: "
                f"{dict(source_placeholders)} != {dict(replacement_placeholders)}"
            )
        if len(replacement) > len(source):
            raise PatchError(
                f"in-game message at 0x{offset:X} exceeds its byte budget: "
                f"{len(replacement)} > {len(source)}"
            )
        actual = bytes(image[offset : offset + len(source) + 1])
        expected = source + b"\0"
        if actual != expected:
            raise PatchError(
                f"in-game message at 0x{offset:X} differs from the supported ACD.EXE: "
                f"{actual.hex()} != {expected.hex()}"
            )
        payload = replacement + b"\0" + bytes(len(source) - len(replacement))
        image[offset : offset + len(source) + 1] = payload


def apply_charstat_geometry(image: memoryview) -> None:
    """Reflow the compact 8px character-stat rows to full-height HANGUL9 rows."""
    for offset, source, replacement in CHARSTAT_GEOMETRY_PATCHES:
        if len(source) != len(replacement):
            raise AssertionError((offset, len(source), len(replacement)))
        actual = bytes(image[offset : offset + len(source)])
        if actual != source:
            raise PatchError(
                f"능력치 UI 코드 0x{offset:X}의 원본 바이트가 예상과 다릅니다: "
                f"{actual.hex()} != {source.hex()}"
            )
        image[offset : offset + len(source)] = replacement


def apply_charstat_menu_rects(data: bytearray) -> None:
    """Align character-stat clicks and the moving arrow to the 11px rows."""
    header_size = mz_header_size(data)
    for index, (source_rect, replacement_rect) in enumerate(CHARSTAT_MENU_RECTS):
        offset = header_size + CHARSTAT_MENU_IMAGE_OFFSET + (index * CHARSTAT_MENU_RECORD_SIZE)
        source = struct.pack("<4H", *source_rect)
        actual = bytes(data[offset : offset + len(source)])
        if actual != source:
            raise PatchError(
                f"능력치 메뉴 레코드 {index}가 예상과 다릅니다: "
                f"{actual.hex()} != {source.hex()}"
            )
        data[offset : offset + len(source)] = struct.pack("<4H", *replacement_rect)


def apply_main_menu_hitboxes(data: bytearray) -> None:
    """Align the three full-width title-menu hitboxes to the Korean labels."""
    header_size = mz_header_size(data)
    for index, (label, source_rect, replacement_rect) in enumerate(MAIN_MENU_HITBOXES):
        offset = header_size + MAIN_MENU_HITBOX_IMAGE_OFFSET + (index * MAIN_MENU_HITBOX_RECORD_SIZE)
        source = struct.pack("<4H", *source_rect)
        actual = bytes(data[offset : offset + len(source)])
        if actual != source:
            raise PatchError(
                f"메인 메뉴 {label} 클릭 영역이 예상과 다릅니다: "
                f"{actual.hex()} != {source.hex()}"
            )
        data[offset : offset + len(source)] = struct.pack("<4H", *replacement_rect)


def replace_fixed(data: bytearray, source: bytes, replacement: bytes) -> None:
    positions: list[int] = []
    start = 0
    while True:
        index = data.find(source, start)
        if index < 0:
            break
        positions.append(index)
        start = index + 1
    if len(positions) != 1:
        raise PatchError(f"시험 문자열 {source!r}의 개수가 {len(positions)}개입니다.")
    if len(replacement) > len(source):
        raise PatchError(f"시험 번역문이 원문 공간보다 큽니다: {source!r}")
    index = positions[0]
    data[index : index + len(source)] = replacement.ljust(len(source), b"\0")


def replace_fixed_at_image_offset(
    data: bytearray,
    image_offset: int,
    source: bytes,
    replacement: bytes,
    label: str,
) -> None:
    if len(replacement) > len(source):
        raise PatchError(f"{label} translation is too large: {len(replacement)} > {len(source)}")
    offset = mz_header_size(data) + image_offset
    actual = bytes(data[offset : offset + len(source)])
    if actual != source:
        raise PatchError(f"{label} differs from the supported ACD.EXE.")
    data[offset : offset + len(source)] = replacement.ljust(len(source), b"\0")


def update_mz_file_size(data: bytearray) -> None:
    """Update the DOS header after appending initialized load-module data."""
    pages, remainder = divmod(len(data), 512)
    if remainder:
        pages += 1
    struct.pack_into("<HH", data, 2, remainder, pages)


def apply_yes_no_labels(data: bytearray) -> None:
    """Point Arena's generic Y/N dialog at AKC-encoded Korean labels."""
    header_size = mz_header_size(data)
    image_size = len(data) - header_size
    stack_segment, stack_pointer = struct.unpack_from("<HH", data, 0x0E)
    stack_top = (stack_segment * 16) + stack_pointer
    if image_size != stack_top:
        raise PatchError(
            f"ACD load-module end 0x{image_size:X} does not match the initial stack top "
            f"0x{stack_top:X}."
        )

    yes = encode_akc("예") + b"\r\0"
    no = encode_akc("아니요") + b"\r\0"
    yes_offset = image_size - ARENA_DATA_IMAGE_BASE
    no_offset = yes_offset + len(yes)
    if yes_offset < 0 or no_offset + len(no) > 0x10000:
        raise PatchError("Korean Y/N labels do not fit in Arena's data segment.")

    table_offset = header_size + YES_NO_POINTER_TABLE_IMAGE_OFFSET
    actual = bytes(data[table_offset : table_offset + len(EXPECTED_YES_NO_POINTER_TABLE)])
    if actual != EXPECTED_YES_NO_POINTER_TABLE:
        raise PatchError(
            "Original Yes/No pointer table differs from the supported ACD.EXE: "
            f"{actual.hex()} != {EXPECTED_YES_NO_POINTER_TABLE.hex()}"
        )

    # The original initialized image ends exactly at SS:SP. Appended bytes are
    # above the downward-growing stack, so they remain stable at runtime.
    data.extend(yes + no)
    struct.pack_into("<HHH", data, table_offset, yes_offset, no_offset, 0)
    update_mz_file_size(data)


def apply_direct_race_notices(data: bytearray) -> None:
    """Render the eight race notices through the same direct path as neighbors."""
    header_size = mz_header_size(data)
    routine_offset = header_size + RACE_NOTICE_ROUTINE_START
    routine_size = RACE_NOTICE_ROUTINE_END - RACE_NOTICE_ROUTINE_START
    original = bytes(data[routine_offset : routine_offset + routine_size])
    if hashlib.sha256(original).hexdigest() != EXPECTED_RACE_NOTICE_ROUTINE_SHA256:
        raise PatchError("혈통 안내문 조립 루틴이 지원하는 ACD.EXE와 다릅니다.")

    image_size = len(data) - header_size
    flag_data_offset = image_size - ARENA_DATA_IMAGE_BASE
    table_data_offset = flag_data_offset + 1
    if flag_data_offset < 0:
        raise PatchError("혈통 안내문 포인터 표가 Arena 데이터 세그먼트 밖입니다.")

    payloads: list[bytes] = []
    for body in RACE_NOTICE_TEXTS:
        lines = body.split("\n")
        text = "그대의 혈통:\r" + "\r".join(lines)
        payloads.append(encode_akc(text) + b"\r\0")

    payload_data_offset = table_data_offset + (2 * len(payloads))
    string_offsets: list[int] = []
    cursor = payload_data_offset
    for payload in payloads:
        string_offsets.append(cursor)
        cursor += len(payload)
    if cursor > 0x10000:
        raise PatchError("8개 혈통 안내문이 Arena 데이터 세그먼트에 들어가지 않습니다.")

    table = struct.pack("<8H", *string_offsets)
    data.extend(b"\0" + table + b"".join(payloads))

    measurement_offset = header_size + RACE_MEASUREMENT_START
    measurement = bytes(
        data[
            measurement_offset : measurement_offset + len(EXPECTED_RACE_MEASUREMENT)
        ]
    )
    if measurement != EXPECTED_RACE_MEASUREMENT:
        raise PatchError("혈통 전용 상자 높이 측정 지점이 원본과 다릅니다.")
    measurement_next_ip = RACE_MEASUREMENT_START + 3
    helper_relative = (RACE_METRIC_HELPER_START - measurement_next_ip) & 0xFFFF
    measurement_patch = b"\xE8" + struct.pack("<H", helper_relative)
    measurement_patch = measurement_patch.ljust(len(EXPECTED_RACE_MEASUREMENT), b"\x90")
    data[
        measurement_offset : measurement_offset + len(EXPECTED_RACE_MEASUREMENT)
    ] = measurement_patch

    # The width-hook replacement leaves this part of its original routine as
    # a verified NOP code cave.  The helper reproduces the original font[0]+1
    # calculation unless the race notice's private flag is active.
    helper = bytes.fromhex("80 3e") + struct.pack("<H", flag_data_offset) + b"\0"
    helper += bytes.fromhex("74 03 b1 0b c3")
    helper += bytes.fromhex("06 c4 36 34 b0 26 8a 0c 07 fe c1 c3")
    helper_offset = header_size + RACE_METRIC_HELPER_START
    if bytes(data[helper_offset : helper_offset + len(helper)]) != b"\x90" * len(helper):
        raise PatchError("혈통 전용 줄높이 도우미 코드 영역이 비어 있지 않습니다.")
    data[helper_offset : helper_offset + len(helper)] = helper

    # BX = selected race * 2; SI = DS:[table + BX]; call the same modal text
    # renderer used immediately before and after this special notice.
    replacement = bytes.fromhex("c6 06") + struct.pack("<H", flag_data_offset) + b"\x01"
    replacement += bytes.fromhex("31 db 8a 1e a8 01 d1 e3 8b b7")
    replacement += struct.pack("<H", table_data_offset)
    call_ip = (RACE_NOTICE_ROUTINE_START + len(replacement) + 3) & 0xFFFF
    renderer_ip = 0x730C
    replacement += b"\xE8" + struct.pack("<H", (renderer_ip - call_ip) & 0xFFFF)
    replacement += bytes.fromhex("c6 06") + struct.pack("<H", flag_data_offset) + b"\x00"
    replacement += b"\xC3"
    if len(replacement) > routine_size:
        raise AssertionError((len(replacement), routine_size))
    data[routine_offset : routine_offset + routine_size] = replacement.ljust(
        routine_size, b"\x90"
    )
    update_mz_file_size(data)


def apply_character_creation_provinces(data: bytearray) -> None:
    """Repack the eight sequential province strings without moving later data."""
    header_size = mz_header_size(data)
    offset = header_size + CHAR_CREATION_PROVINCES_IMAGE_OFFSET
    source = b"\0".join(name.encode("ascii") for name in CHAR_CREATION_PROVINCES) + b"\0"
    actual = bytes(data[offset : offset + len(source)])
    if actual != source:
        raise PatchError(
            "Character-creation province table differs from the supported ACD.EXE."
        )

    translated = (
        "하이 락",
        "해머펠",
        "스카이림",
        "모로윈드",
        "서머셋 섬",
        "발렌우드",
        "엘스웨어",
        "블랙 마쉬",
    )
    replacement = b"\0".join(encode_akc(name) for name in translated) + b"\0"
    if len(replacement) > len(source):
        raise PatchError(
            f"Korean province table is too large: {len(replacement)} > {len(source)}"
        )
    data[offset : offset + len(source)] = replacement.ljust(len(source), b"\0")


def apply_preferred_attributes(data: bytearray) -> None:
    """Translate the 18 sequential class attribute phrases before stat allocation."""
    header_size = mz_header_size(data)
    offset = header_size + PREFERRED_ATTRIBUTES_IMAGE_OFFSET
    source = b"\0".join(value.encode("ascii") for value in PREFERRED_ATTRIBUTES) + b"\0"
    actual = bytes(data[offset : offset + len(source)])
    if actual != source:
        raise PatchError("Preferred-attribute table differs from the supported ACD.EXE.")

    # Arena attributes: INT, WIL, STR, SPD, AGI, PER, END.
    translations = (
        "지능과 의지력",
        "힘과 지능",
        "속도와 지능",
        "지능과 민첩성",
        "지능과 의지력",
        "민첩성과 지능",
        "지능과 매력",
        "민첩성과 속도",
        "힘과 지능",
        "민첩성과 속도",
        "민첩성과 지능",
        "힘과 민첩성",
        "민첩성과 지구력",
        "힘과 민첩성",
        "힘과 지능",
        "힘과 지구력",
        "힘과 지구력",
        "힘과 의지력",
    )
    replacement = b"\0".join(encode_akc(value) for value in translations) + b"\0"
    if len(replacement) > len(source):
        raise PatchError(
            f"Korean preferred-attribute table is too large: {len(replacement)} > {len(source)}"
        )
    data[offset : offset + len(source)] = replacement.ljust(len(source), b"\0")


def repack_string_table(
    data: bytearray,
    image_offset: int,
    source_values: tuple[str, ...],
    translated_values: tuple[str, ...],
    label: str,
) -> None:
    """Repack a fixed-count sequential string table inside its original byte span."""
    if len(source_values) != len(translated_values):
        raise AssertionError((label, len(source_values), len(translated_values)))
    header_size = mz_header_size(data)
    offset = header_size + image_offset
    source = b"\0".join(value.encode("ascii") for value in source_values) + b"\0"
    actual = bytes(data[offset : offset + len(source)])
    if actual != source:
        raise PatchError(f"{label} table differs from the supported ACD.EXE.")
    replacement = b"\0".join(encode_akc(value) for value in translated_values) + b"\0"
    if len(replacement) > len(source):
        raise PatchError(f"Korean {label} table is too large: {len(replacement)} > {len(source)}")
    data[offset : offset + len(source)] = replacement.ljust(len(source), b"\0")


def apply_gameplay_name_tables(data: bytearray) -> None:
    """Translate names that Arena selects from sequential runtime tables."""
    for image_offset, source_values, translated_values, label in GAMEPLAY_NAME_TABLES:
        repack_string_table(
            data,
            image_offset,
            source_values,
            translated_values,
            label,
        )


def apply_attribute_and_race_names(data: bytearray) -> None:
    repack_string_table(
        data,
        ATTRIBUTE_NAMES_IMAGE_OFFSET,
        ATTRIBUTE_NAMES,
        ("힘", "지능", "의지력", "민첩성", "속도", "지구력", "매력", "행운"),
        "attribute-name",
    )
    korean_races = (
        "브레튼",
        "레드가드",
        "노드",
        "다크엘프",
        "하이엘프",
        "우드엘프",
        "카짓",
        "아르고니안",
    )
    repack_string_table(
        data,
        RACE_PLURAL_NAMES_IMAGE_OFFSET,
        RACE_PLURAL_NAMES,
        korean_races,
        "plural-race-name",
    )
    repack_string_table(
        data,
        RACE_SINGULAR_NAMES_IMAGE_OFFSET,
        RACE_SINGULAR_NAMES,
        korean_races,
        "singular-race-name",
    )


def apply_proof_menu(data: bytearray) -> None:
    header_size = mz_header_size(data)
    apply_charstat_geometry(memoryview(data)[header_size:])
    apply_charstat_menu_rects(data)
    apply_main_menu_hitboxes(data)
    for source, korean in (
        (
            b"How do you wish\rto select your class?\r\0",
            "직업을 어떻게\r선택하시겠습니까?",
        ),
        (
            b"10 questions shall be asked that will\r"
            b"determine the path of your destiny.\r"
            b"The scroll bars roll the parchment up\r"
            b"or down. Use the 'A', 'B', or 'C' keys\r"
            b"to answer the questions.\r\0",
            "열 가지 질문으로\r"
            "그대의 운명이 정해집니다.\r"
            "두루마리 막대를 움직여 내용을 보고,\r"
            "A, B, C 키로 답을 선택하십시오.",
        ),
        (
            b"Thou wouldst survive\r"
            b"longest as a %s.\r"
            b"Wilt thou accept this\r"
            b"as thy destiny? \r\0",
            "그대에게 알맞은 직업은\r"
            "%s입니다.\r"
            "이를 운명으로\r"
            "받아들이겠습니까?",
        ),
        (b"Choose thy class...\0", "직업을 선택하라."),
        (b"What will be thy name, %s?\r\0", "%s의 이름은?"),
        (b"Choose thy gender...\r\0", "성별을 선택하십시오."),
        (
            b"From where dost thou hail,\r%s\rthe\r%s?\r\0",
            "출신 지역을 선택하십시오.\r%s / %s",
        ),
        (
            b"Thou hast chosen %s,\r"
            b"land of the %s.\r"
            b"Wouldst thou accept this\r"
            b"as thy home? \r\0",
            "선택한 고향은\r%s입니다.\r받아들이겠습니까?",
        ),
        (
            b"Then thou wilt be known as the %s\r"
            b"%s, who wouldst call %s,\r"
            b"land of the %s, his home.\r\0",
            "직업은 %s,\r이름은 %s.\r%s이(가) 그대의 고향입니다.",
        ),
        (
            b"Thy body and mind must be\r"
            b"%s\r"
            b"if thou art to succeed\r"
            b"as a %s.\r\0",
            "필요한 능력은\r%s.\r%s의 길에서 성공하려면\r이를 명심하십시오.",
        ),
        (
            b"Go ye now in peace.\r"
            b"Let thy fate be written\r"
            b"in the Elder Scrolls...\r\0",
            "이제 평안히 가십시오.\r그대의 운명을\r엘더 스크롤에 새기십시오.",
        ),
        (
            b"Distribute thy points as needed,\r"
            b"keeping in mind the recommendations \r"
            b"for thy chosen class...\r\0",
            "직업에 알맞게\r능력치 점수를 배분하십시오.",
        ),
        (b"Which dost thou choose?\r\0", "선택하십시오."),
        (
            b"Thou wilt now choose thy appearance.\r"
            b"Thy mien canst be altered by clicking thy face.\r"
            b"When thou art finished, select 'Done' to enter\r"
            b"the world of Tamriel, home of the Arena...\r\0",
            "이제 외형을 선택하십시오.\r"
            "얼굴을 클릭하면 모습을 바꿀 수 있습니다.\r"
            "완료되면 '완료'를 눌러\r"
            "탐리엘의 세계로 들어가십시오.",
        ),
        (b"Generate\r\0", "생성"),
        (b"Select\r\0", "선택"),
        (b"Male\r\0", "남성"),
        (b"Female\r\0", "여성"),
    ):
        replace_fixed(data, source, encode_akc(korean) + b"\r\0")
    replace_fixed_at_image_offset(
        data,
        0x3F817,
        b"You must distribute all your bonus points.\0",
        encode_akc("보너스 점수를 모두 배분하십시오.") + b"\r\0",
        "remaining bonus points",
    )
    source = b"Know ye this also:"
    replacement = encode_akc("그대의 혈통:")
    replace_fixed(data, source, replacement.ljust(len(source), b" "))
    replace_fixed(
        data,
        bytes.fromhex("09 fe 53 09 fd") + b"ave stats",
        bytes.fromhex("09 fe 53 09 fd") + b" " + encode_akc("저장"),
    )
    replace_fixed(
        data,
        bytes.fromhex("09 fe 52 09 fd") + b"eroll stats",
        bytes.fromhex("09 fe 52 09 fd") + b" " + encode_akc("다시 굴림"),
    )
    apply_character_creation_provinces(data)
    apply_preferred_attributes(data)
    apply_attribute_and_race_names(data)
    apply_yes_no_labels(data)
    apply_direct_race_notices(data)

def apply_bsa_name(data: bytearray, filename: str) -> None:
    try:
        encoded = filename.encode("ascii")
    except UnicodeEncodeError as exc:
        raise PatchError("BSA 파일명은 ASCII여야 합니다.") from exc
    if not 1 <= len(encoded) <= 12 or "." not in filename:
        raise PatchError("BSA 파일명은 8.3 형식의 최대 12바이트여야 합니다.")
    source = b"global.bsa\0\0\0"
    positions: list[int] = []
    start = 0
    while True:
        index = data.find(source, start)
        if index < 0:
            break
        positions.append(index)
        start = index + 1
    if len(positions) != 1:
        raise PatchError(f"global.bsa 여유 영역의 개수가 {len(positions)}개입니다.")
    replacement = (encoded + b"\0").ljust(len(source), b"\0")
    index = positions[0]
    data[index : index + len(source)] = replacement


def apply_intro_name(data: bytearray, filename: str) -> None:
    try:
        encoded = filename.encode("ascii")
    except UnicodeEncodeError as exc:
        raise PatchError("INTRO 파일명은 ASCII여야 합니다.") from exc
    source = b"intro.flc"
    if len(encoded) != len(source) or not filename.lower().endswith(".flc"):
        raise PatchError("대체 INTRO 파일명은 intro.flc와 같은 9바이트여야 합니다.")
    positions: list[int] = []
    start = 0
    while True:
        index = data.lower().find(source, start)
        if index < 0:
            break
        positions.append(index)
        start = index + 1
    if len(positions) != 1:
        raise PatchError(f"intro.flc 문자열의 개수가 {len(positions)}개입니다.")
    index = positions[0]
    data[index : index + len(source)] = encoded


def apply_template_name(data: bytearray, filename: str) -> None:
    try:
        encoded = filename.encode("ascii")
    except UnicodeEncodeError as exc:
        raise PatchError("TEMPLATE filename must be ASCII.") from exc
    source = b"template.dat"
    if len(encoded) != len(source) or not filename.lower().endswith(".dat"):
        raise PatchError("Replacement TEMPLATE filename must be 12 bytes and end in .DAT.")
    positions: list[int] = []
    start = 0
    while True:
        index = data.lower().find(source, start)
        if index < 0:
            break
        positions.append(index)
        start = index + 1
    if len(positions) != 2:
        raise PatchError(f"Expected 2 template.dat strings, found {len(positions)}.")
    for index in positions:
        data[index : index + len(source)] = encoded


def apply_question_name(data: bytearray, filename: str) -> None:
    try:
        encoded = filename.encode("ascii")
    except UnicodeEncodeError as exc:
        raise PatchError("QUESTION filename must be ASCII.") from exc
    source = b"question.txt"
    if len(encoded) != len(source) or not filename.lower().endswith(".txt"):
        raise PatchError("Replacement QUESTION filename must be 12 bytes and end in .TXT.")
    positions: list[int] = []
    start = 0
    while True:
        index = data.lower().find(source, start)
        if index < 0:
            break
        positions.append(index)
        start = index + 1
    if len(positions) != 1:
        raise PatchError(f"Expected 1 question.txt string, found {len(positions)}.")
    index = positions[0]
    data[index : index + len(source)] = encoded


def patch(
    input_path: Path,
    output_path: Path,
    interrupt: int,
    proof_menu: bool,
    bsa_name: str | None,
    intro_name: str | None,
    template_name: str | None,
    question_name: str | None,
) -> None:
    if input_path.resolve() == output_path.resolve():
        raise PatchError("입력 실행 파일을 직접 덮어쓸 수 없습니다.")
    if not 0x20 <= interrupt <= 0xFF:
        raise PatchError("인터럽트 번호는 0x20–0xFF여야 합니다.")

    data = bytearray(input_path.read_bytes())
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_UNPACKED_SHA256:
        raise PatchError(
            "지원하는 Deark 해제본과 SHA-256이 다릅니다: " + digest
        )
    header_size = mz_header_size(data)
    image = memoryview(data)[header_size:]
    if bytes(image[WIDTH_START:WIDTH_END]) != EXPECTED_WIDTH:
        raise PatchError("폭 계산 함수의 원본 바이트가 예상과 다릅니다.")
    if bytes(image[DRAW_START:DRAW_END]) != EXPECTED_DRAW:
        raise PatchError("글자 그리기 함수의 원본 바이트가 예상과 다릅니다.")
    if bytes(image[LINE_ADVANCE_START:LINE_ADVANCE_END]) != EXPECTED_LINE_ADVANCE:
        raise PatchError("행간 계산 코드의 원본 바이트가 예상과 다릅니다.")

    relocations = relocation_offsets(data)
    if 0x66FF not in relocations or 0x9E10 not in relocations:
        raise PatchError("후킹 스텁에 필요한 데이터 세그먼트 재배치 항목이 없습니다.")

    image[WIDTH_START:WIDTH_END] = make_width_stub(WIDTH_END - WIDTH_START, interrupt)
    image[DRAW_START:DRAW_END] = make_draw_stub(DRAW_END - DRAW_START, interrupt)
    image[LINE_ADVANCE_START:LINE_ADVANCE_END] = make_line_advance_stub(interrupt)
    apply_question_scroll_geometry(image)
    apply_item_list_geometry(image)
    apply_cutscene_akc_filter(image)
    apply_cutscene_subtitle_geometry(image)
    apply_ingame_messages(image)
    del image
    apply_gameplay_name_tables(data)
    if proof_menu:
        apply_proof_menu(data)
    if bsa_name:
        apply_bsa_name(data, bsa_name)
    if intro_name:
        apply_intro_name(data, intro_name)
    if template_name:
        apply_template_name(data, template_name)
    if question_name:
        apply_question_name(data, question_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    print(f"patched: {output_path}")
    print(f"sha256: {hashlib.sha256(data).hexdigest()}")
    print(f"interrupt: 0x{interrupt:02X}")
    print(f"proof menu: {proof_menu}")
    print(f"BSA name: {bsa_name or 'global.bsa'}")
    print(f"INTRO name: {intro_name or 'intro.flc'}")
    print(f"TEMPLATE name: {template_name or 'template.dat'}")
    print(f"QUESTION name: {question_name or 'question.txt'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Arena ACD.EXE 한국어 렌더러 후킹 도구")
    parser.add_argument("input", type=Path, help="Deark로 해제한 321,728바이트 ACD.EXE")
    parser.add_argument("output", type=Path)
    parser.add_argument("--interrupt", type=lambda value: int(value, 0), default=0x60)
    parser.add_argument(
        "--proof-menu",
        action="store_true",
        help="캐릭터 생성 초기 질문·안내·선택 항목을 한국어로 교체",
    )
    parser.add_argument(
        "--bsa-name",
        help="원본 GLOBAL.BSA 대신 읽을 별도 8.3 파일명(예: GLOBAL_K.BSA)",
    )
    parser.add_argument(
        "--intro-name",
        help="원본 intro.flc 대신 읽을 같은 길이의 파일명(예: intkr.flc)",
    )
    parser.add_argument(
        "--template-name",
        help="Use an alternate 12-byte TEMPLATE filename (for example TEMPL_KR.DAT)",
    )
    parser.add_argument(
        "--question-name",
        help="Use an alternate 12-byte QUESTION filename (for example QUEST_KR.TXT)",
    )
    args = parser.parse_args(argv)
    try:
        patch(
            args.input,
            args.output,
            args.interrupt,
            args.proof_menu,
            args.bsa_name,
            args.intro_name,
            args.template_name,
            args.question_name,
        )
    except (PatchError, OSError, struct.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
