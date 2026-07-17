#!/usr/bin/env python3
"""Import an artist-finished AUTOMAP PNG without palette conversion loss."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from PIL import Image

from arena_img import ArenaIMG, decode, encode_uncompressed, palette_8bit, write_png
from localize_ingame_ui import clean_automap


EXPECTED_SIZE = (320, 200)
COMPASS_RECT = (240, 18, 307, 78)
EXIT_RECT = (238, 156, 305, 183)


def contains(rect: tuple[int, int, int, int], x: int, y: int) -> bool:
    x0, y0, x1, y1 = rect
    return x0 <= x < x1 and y0 <= y < y1


def import_pixels(
    png_path: Path,
    source: ArenaIMG,
    cleaned: ArenaIMG,
) -> tuple[bytes, int, int, int]:
    image = Image.open(png_path).convert("RGBA")
    if image.size != EXPECTED_SIZE:
        raise ValueError(f"{png_path.name} 크기 오류: {image.size} != {EXPECTED_SIZE}")
    if source.palette is None:
        raise ValueError("AUTOMAP.IMG에는 내장 팔레트가 있어야 합니다.")

    palette_values = palette_8bit(source.palette)
    palette = [
        tuple(palette_values[index : index + 3])
        for index in range(0, len(palette_values), 3)
    ]
    lookup: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    for palette_index, color in enumerate(palette):
        lookup[color].append(palette_index)

    raw = image.tobytes()
    output = bytearray(cleaned.pixels)
    changed = compass_ink = exit_ink = 0
    for index, base_index in enumerate(cleaned.pixels):
        x, y = index % EXPECTED_SIZE[0], index // EXPECTED_SIZE[0]
        offset = index * 4
        red, green, blue, alpha = raw[offset : offset + 4]
        if alpha != 255:
            raise ValueError(f"투명 픽셀이 있습니다: ({x},{y}) alpha={alpha}")
        color = (red, green, blue)
        if color == palette[base_index]:
            continue
        if not (contains(COMPASS_RECT, x, y) or contains(EXIT_RECT, x, y)):
            raise ValueError(f"허용 영역 밖 픽셀이 바뀌었습니다: ({x},{y}) 색상={color}")
        candidates = lookup.get(color)
        if not candidates:
            raise ValueError(f"AUTOMAP 팔레트에 없는 색상입니다: ({x},{y}) 색상={color}")

        source_index = source.pixels[index]
        if palette[source_index] == color:
            chosen = source_index
        elif contains(COMPASS_RECT, x, y) and color == palette[10]:
            chosen = 10
        elif contains(EXIT_RECT, x, y) and color == palette[6]:
            chosen = 6
        else:
            chosen = candidates[0]
        output[index] = chosen
        changed += 1
        if contains(COMPASS_RECT, x, y) and color == palette[10]:
            compass_ink += 1
        if contains(EXIT_RECT, x, y) and color == palette[6]:
            exit_ink += 1

    if changed == 0:
        raise ValueError("완성본에 깨끗한 바탕과 다른 픽셀이 없습니다.")
    if compass_ink == 0 or exit_ink == 0:
        raise ValueError(
            f"필수 글자색이 없습니다: 나침반={compass_ink}, 종료={exit_ink}"
        )
    return bytes(output), changed, compass_ink, exit_ink


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--png", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()

    source = decode(args.source)
    if (source.width, source.height) != EXPECTED_SIZE or source.palette is None:
        raise ValueError("원본 AUTOMAP.IMG는 팔레트가 있는 320x200 이미지여야 합니다.")
    cleaned = clean_automap(source)
    pixels, changed, compass_ink, exit_ink = import_pixels(
        args.png, source, cleaned
    )
    result = ArenaIMG(
        source.x,
        source.y,
        source.width,
        source.height,
        source.palette,
        pixels,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encode_uncompressed(result, pixels, args.output)
    if decode(args.output) != result:
        raise ValueError("AUTOMAP.IMG 저장 후 왕복 검증에 실패했습니다.")
    if args.preview is not None:
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        write_png(result, args.preview)

    print(f"wrote: {args.output}")
    print(f"changed pixels from clean base: {changed}")
    print(f"ink pixels: compass={compass_ink}, exit={exit_ink}")
    if args.preview is not None:
        print(f"preview: {args.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
