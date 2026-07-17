#!/usr/bin/env python3
"""Import an artist-finished EQUIP PNG without palette conversion loss."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from arena_img import ArenaIMG, decode, encode_uncompressed, write_png
from localize_ingame_ui import clean_equip


EXPECTED_SIZE = (171, 200)
INK_INDICES = {
    (191, 115, 0): 253,
    (41, 0, 0): 31,
}


def import_pixels(
    png_path: Path,
    clean_source: ArenaIMG,
    palette: list[tuple[int, int, int]],
) -> tuple[bytes, int]:
    image = Image.open(png_path).convert("RGBA")
    if image.size != EXPECTED_SIZE:
        raise ValueError(f"{png_path.name} 크기 오류: {image.size} != {EXPECTED_SIZE}")

    raw = image.tobytes()
    output = bytearray(clean_source.pixels)
    changed = 0
    for index, base_index in enumerate(clean_source.pixels):
        offset = index * 4
        red, green, blue, alpha = raw[offset : offset + 4]
        if alpha != 255:
            raise ValueError(f"{png_path.name}에는 투명 픽셀이 없어야 합니다.")
        color = (red, green, blue)
        if color == palette[base_index]:
            continue
        ink_index = INK_INDICES.get(color)
        if ink_index is None:
            raise ValueError(
                f"깨끗한 바탕과 다른 픽셀에 허용되지 않은 색상이 있습니다: "
                f"위치=({index % EXPECTED_SIZE[0]},{index // EXPECTED_SIZE[0]}), 색상={color}"
            )
        if palette[ink_index] != color:
            raise ValueError(f"CHARSHT.COL 팔레트 {ink_index}번 색상이 예상과 다릅니다.")
        output[index] = ink_index
        changed += 1
    if changed == 0:
        raise ValueError("완성본에 깨끗한 바탕과 다른 글자 픽셀이 없습니다.")
    return bytes(output), changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--png", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--palette", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()

    palette_data = args.palette.read_bytes()
    if len(palette_data) != 776:
        raise ValueError(f"CHARSHT.COL 크기가 올바르지 않습니다: {len(palette_data)}")
    raw_palette = palette_data[8:]
    palette = [tuple(raw_palette[index : index + 3]) for index in range(0, 768, 3)]

    source = decode(args.source)
    if (source.width, source.height) != EXPECTED_SIZE or source.palette is not None:
        raise ValueError("원본 EQUIP.IMG는 팔레트 없는 171x200 이미지여야 합니다.")
    cleaned = clean_equip(source)
    pixels, changed = import_pixels(args.png, cleaned, palette)
    result = ArenaIMG(
        source.x,
        source.y,
        source.width,
        source.height,
        source.palette,
        pixels,
    )
    encode_uncompressed(result, pixels, args.output)
    if decode(args.output) != result:
        raise ValueError("EQUIP.IMG 저장 후 왕복 검증에 실패했습니다.")
    if args.preview is not None:
        write_png(result, args.preview, palette)

    print(f"wrote: {args.output}")
    print(f"changed pixels from clean base: {changed}")
    if args.preview is not None:
        print(f"preview: {args.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
