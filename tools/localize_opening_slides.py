#!/usr/bin/env python3
"""Replace the nine pre-character-creation story slides with Korean artwork."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from arena_flc import decode as decode_flc
from arena_img import decode as decode_img, encode_uncompressed


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "korean-patch" / "analysis" / "bsa-decoded"
OUTPUT = ROOT / "korean-patch" / "build" / "opening-slides"
PREVIEW = ROOT / "korean-patch" / "analysis" / "opening-slides-korean"
FONT = ROOT / "korean-patch" / "reference" / "galmuri" / "dist" / "Galmuri11-Bold.ttf"


# (cover rectangle, text origin, Korean text)
SLIDES = {
    1: [((10, 20, 151, 116), (16, 28), "탐리엘의 황제\n우리엘 셉팀 7세는\n제국 근위대장 탈린과\n함께 서 있었다...")],
    2: [((17, 48, 202, 128), (25, 57), "두 사람은 반역의 소문을\n조사하던 제국 전투마법사\n제이거 탄의 부름을 받았다...")],
    3: [((17, 20, 137, 70), (25, 28), "황제는\n배신당했다...")],
    4: [((154, 20, 310, 88), (161, 28), "그리고 탄이 선택한\n다른 차원으로\n추방되었다...")],
    5: [((7, 18, 288, 59), (14, 25), "수개월간 준비를 마친 제이거 탄은\n마침내 황좌를 차지했다...")],
    6: [
        ((12, 18, 158, 103), (19, 26), "탄의 옛 제자\n리아 실메인은..."),
        ((90, 165, 141, 182), (90, 165), ""),
        ((133, 126, 312, 181), (141, 132), "제이거 탄의 배신을\n원로원에 알리기도 전에\n붙잡히고 말았다..."),
    ],
    7: [
        ((12, 18, 199, 109), (19, 26), "마법의 본질을 조종한 탄은\n진정한 황제를 대신해\n세상을 지배하려 했다..."),
        ((195, 18, 238, 39), (195, 18), ""),
    ],
    8: [
        ((12, 18, 148, 108), (19, 26), "제국의 마법사는\n곧바로 자신의\n하수인들을 모았다..."),
        ((140, 18, 176, 39), (140, 18), ""),
    ],
    9: [((17, 18, 195, 96), (25, 26), "그리고 그들을\n황제의 근위대를 닮은\n뒤틀린 존재로 만들었다...")],
}

FORCE_CLEAN = {
    2: [(17, 100, 52, 121)],
    5: [(225, 18, 251, 37)],
    6: [(88, 161, 141, 183)],
}


def remove_english_glyphs(
    image: Image.Image,
    rect: tuple[int, int, int, int],
    force: bool = False,
) -> None:
    """Remove small dark connected components while preserving large line art."""
    width, height = image.size
    pixels = image.load()
    x0, y0, x1, y1 = rect
    candidates: set[tuple[int, int]] = set()
    for y in range(max(0, y0), min(height, y1)):
        for x in range(max(0, x0), min(width, x1)):
            r, g, b = pixels[x, y]
            if r < 135 and g < 95 and b < 70:
                candidates.add((x, y))

    if force:
        mask = set(candidates)
    else:
        mask: set[tuple[int, int]] = set()
        while candidates:
            seed = candidates.pop()
            component = {seed}
            stack = [seed]
            while stack:
                x, y = stack.pop()
                for ny in range(y - 1, y + 2):
                    for nx in range(x - 1, x + 2):
                        point = (nx, ny)
                        if point in candidates:
                            candidates.remove(point)
                            component.add(point)
                            stack.append(point)
            xs = [point[0] for point in component]
            ys = [point[1] for point in component]
            component_width = max(xs) - min(xs) + 1
            component_height = max(ys) - min(ys) + 1
            if component_width <= 20 and component_height <= 18 and len(component) <= 150:
                mask.update(component)

    # Grow only into other dark ink pixels, catching disconnected antialiasing
    # without eating the light parchment or broad illustration strokes.
    grown = set(mask)
    for x, y in mask:
        for ny in range(max(y0, y - 1), min(y1, y + 2)):
            for nx in range(max(x0, x - 1), min(x1, x + 2)):
                r, g, b = pixels[nx, ny]
                if r < 145 and g < 105 and b < 80:
                    grown.add((nx, ny))
    mask = grown

    # Peel the mask from its boundary inward. Each removed ink pixel receives
    # the median-like average of nearby surviving pixels, reconstructing the
    # local parchment/line-art texture instead of pasting a rectangle.
    remaining = set(mask)
    while remaining:
        updates: list[tuple[int, int, tuple[int, int, int]]] = []
        for x, y in remaining:
            neighbors = []
            for ny in range(max(0, y - 1), min(height, y + 2)):
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    if (nx, ny) not in remaining:
                        neighbors.append(pixels[nx, ny])
            if neighbors:
                count = len(neighbors)
                color = tuple(sum(value[channel] for value in neighbors) // count for channel in range(3))
                updates.append((x, y, color))
        if not updates:
            break
        for x, y, color in updates:
            pixels[x, y] = color
            remaining.remove((x, y))


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    palette = decode_flc(ROOT / "ARENA" / "SCROLL.FLC").frames[-1].palette
    flat_palette = [component for color in palette for component in color]
    font = ImageFont.truetype(str(FONT), 12)

    for index, edits in SLIDES.items():
        source = decode_img(SOURCE / f"INTRO0{index}.IMG")
        source_p = Image.frombytes("P", (source.width, source.height), source.pixels)
        source_p.putpalette(flat_palette)
        rgb = source_p.convert("RGB")
        for rect, origin, text in edits:
            remove_english_glyphs(rgb, rect)
        for rect in FORCE_CLEAN.get(index, []):
            remove_english_glyphs(rgb, rect, force=True)
        draw = ImageDraw.Draw(rgb)
        for rect, origin, text in edits:
            draw.text(origin, text, font=font, fill=(51, 15, 15), spacing=2)

        indexed = rgb.quantize(palette=source_p, dither=Image.Dither.NONE)
        indexed.save(PREVIEW / f"INTRO0{index}.png")
        encode_uncompressed(source, indexed.tobytes(), OUTPUT / f"INTRO0{index}.IMG")
        print(f"localized INTRO0{index}.IMG")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
