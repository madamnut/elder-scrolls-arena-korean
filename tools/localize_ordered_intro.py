#!/usr/bin/env python3
"""Localize the screens encountered immediately after the preserved title."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from arena_flc import decode as decode_flc
from arena_img import decode as decode_img, encode_uncompressed
from localize_opening_slides import remove_english_glyphs


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "korean-patch" / "analysis" / "bsa-decoded"
OUTPUT = ROOT / "korean-patch" / "build" / "ordered-intro"
PREVIEW = ROOT / "korean-patch" / "analysis" / "ordered-intro-korean"
FONT_PATH = ROOT / "korean-patch" / "reference" / "galmuri" / "dist" / "Galmuri11-Bold.ttf"


SCROLL_TEXT = {
    1: (
        "수백 년 동안 여러 세력은 사소한 전쟁과\n"
        "국경 분쟁을 벌였다. 제3시대 896년,\n"
        "우리엘 셉팀은 모든 반대자를 무너뜨리고\n"
        "황제를 자처했다. 하지만 오랜 전쟁은\n"
        "백성들에게 깊은 상처를 남겼다.\n"
        "엘프어로 '새벽의 아름다움'이라는 뜻의\n"
        "탐리엘은 고통스러운 이들의 입에서\n"
        "사라져 이내 잊히고 말았다."
    ),
    2: (
        "삶과 죽음이 매일 던져지는 동전의\n"
        "양면과 같던 세상에서, 사람들은\n"
        "슬픔의 땅을 '아레나'라 부르기 시작했다...\n"
        "우리엘 셉팀이 평화를 세운 지 492년.\n"
        "우리엘 셉팀 7세 황제가 마흔세 번째\n"
        "생일을 맞은 지금, 아레나에 새로운\n"
        "위협이 다가온다. 질투에 찬 자들은\n"
        "황좌를 탐내며 황제의 몰락을 꾸몄다."
    ),
    3: (
        "희망은 죽음의 날개를 타고\n"
        "날아온다고 한다.\n\n"
        "준비하라.\n"
        "엘더스크롤이 예언했듯,\n"
        "바로 이곳에서 그대의 모험이\n"
        "시작될 것이다..."
    ),
}


def indexed_image(source, palette) -> Image.Image:
    image = Image.frombytes("P", (source.width, source.height), source.pixels)
    image.putpalette([component for color in palette for component in color])
    return image


def save_replacement(source, rgb: Image.Image, palette_image: Image.Image, name: str) -> None:
    indexed = rgb.quantize(palette=palette_image, dither=Image.Dither.NONE)
    indexed.save(PREVIEW / f"{Path(name).stem}.png")
    encode_uncompressed(source, indexed.tobytes(), OUTPUT / name)


def localize_quote(font: ImageFont.FreeTypeFont) -> None:
    source = decode_img(SOURCE / "QUOTE.IMG")
    palette_image = Image.frombytes("P", (source.width, source.height), source.pixels)
    palette_image.putpalette([min(value, 63) * 255 // 63 for value in source.palette])
    rgb = Image.new("RGB", (source.width, source.height), (0, 0, 0))
    draw = ImageDraw.Draw(rgb)
    text = "최고의 기술은\n살아남은 자를 통해 전해진다...\n\n- 가이덴 신지, 검술의 대가\n제1시대 947년"
    box = draw.multiline_textbbox((0, 0), text, font=font, spacing=3, align="center")
    x = (source.width - (box[2] - box[0])) // 2
    y = (source.height - (box[3] - box[1])) // 2 - box[1]
    draw.multiline_text((x, y), text, font=font, fill=(235, 235, 235), spacing=3, align="center")
    save_replacement(source, rgb, palette_image, "QUOTE.IMG")


def localize_scrolls(font: ImageFont.FreeTypeFont) -> None:
    palette = decode_flc(ROOT / "ARENA" / "SCROLL.FLC").frames[-1].palette
    for index, text in SCROLL_TEXT.items():
        source = decode_img(SOURCE / f"SCROLL0{index}.IMG")
        palette_image = indexed_image(source, palette)
        rgb = palette_image.convert("RGB")
        remove_english_glyphs(rgb, (12, 16, 311, 188))
        draw = ImageDraw.Draw(rgb)
        if index == 1:
            # Preserve the illuminated frame but replace its large English T
            # with a Korean ornamental initial, then flow prose around it.
            parchment = rgb.crop((250, 110, 292, 166))
            rgb.paste(parchment, (29, 55))
            ornament_font = ImageFont.truetype(str(FONT_PATH), 28)
            draw = ImageDraw.Draw(rgb)
            draw.text((37, 72), "전", font=ornament_font, fill=(51, 15, 15))
            lines = [
                ((21, 24), "수백 년 동안 여러 세력은 사소한 전쟁과"),
                ((21, 38), "국경 분쟁을 벌였다."),
                ((82, 56), "제3시대 896년,"),
                ((82, 70), "우리엘 셉팀은"),
                ((82, 84), "모든 반대자를"),
                ((82, 98), "무너뜨리고 황제를 자처했다."),
                ((21, 118), "하지만 오랜 전쟁은 백성들에게 깊은"),
                ((21, 132), "상처를 남겼다. 엘프어로 '새벽의"),
                ((21, 146), "아름다움'이라는 뜻의 탐리엘은"),
                ((21, 160), "고통 속에서 이내 잊히고 말았다."),
            ]
            for position, line in lines:
                draw.text(position, line, font=font, fill=(51, 15, 15))
        else:
            draw.multiline_text((21, 25), text, font=font, fill=(51, 15, 15), spacing=2)
        save_replacement(source, rgb, palette_image, f"SCROLL0{index}.IMG")


def localize_menu(font: ImageFont.FreeTypeFont) -> None:
    source = decode_img(SOURCE / "MENU.IMG")
    palette_image = Image.frombytes("P", (source.width, source.height), source.pixels)
    palette_image.putpalette([min(value, 63) * 255 // 63 for value in source.palette])
    rgb = palette_image.convert("RGB")
    edits = [
        ((82, 47, 238, 73), "저장한 게임 불러오기", 51),
        ((80, 94, 246, 120), "새 게임 시작", 98),
        ((130, 143, 190, 168), "종료", 147),
    ]
    clean_texture = rgb.crop((120, 34, 200, 46))
    for rect, _, _ in edits:
        size = (rect[2] - rect[0], rect[3] - rect[1])
        rgb.paste(ImageOps.fit(clean_texture, size, method=Image.Resampling.BILINEAR), (rect[0], rect[1]))
    draw = ImageDraw.Draw(rgb)
    for _, text, y in edits:
        box = draw.textbbox((0, 0), text, font=font)
        x = (source.width - (box[2] - box[0])) // 2
        draw.text((x, y), text, font=font, fill=(128, 16, 16))
    save_replacement(source, rgb, palette_image, "MENU.IMG")


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(str(FONT_PATH), 12)
    localize_quote(font)
    localize_scrolls(font)
    localize_menu(font)
    print("localized immediate post-title flow: QUOTE, SCROLL01-03, MENU")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
