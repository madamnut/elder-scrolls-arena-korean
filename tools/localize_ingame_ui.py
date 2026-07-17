#!/usr/bin/env python3
"""Localize fixed labels in Arena's common in-game parchment screens."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

from PIL import Image

from arena_img import ArenaIMG, decode, encode_uncompressed, write_png


HANGUL_BASE = 0xAC00
GLYPH_BYTES = 32
EQUIP_ATLAS_WIDTH = 130
EQUIP_ATLAS_GUTTER = 2


def clone_rect(
    pixels: bytearray,
    width: int,
    source: tuple[int, int, int, int],
    destination: tuple[int, int],
) -> None:
    sx0, sy0, sx1, sy1 = source
    dx, dy = destination
    block = [bytes(pixels[y * width + sx0 : y * width + sx1]) for y in range(sy0, sy1)]
    for row, values in enumerate(block):
        start = (dy + row) * width + dx
        pixels[start : start + len(values)] = values


def draw_text(
    pixels: bytearray,
    canvas_width: int,
    canvas_height: int,
    font_data: bytes,
    text: str,
    x: int,
    y: int,
    glyph_width: int,
    glyph_height: int,
    advance: int,
    palette_index: int,
) -> None:
    cursor = x
    for char in text:
        if char == " ":
            cursor += max(1, advance // 2)
            continue
        index = ord(char) - HANGUL_BASE
        if not 0 <= index < 11172:
            raise ValueError(f"unsupported fixed-UI character: {char!r}")
        rows = struct.unpack_from("<16H", font_data, index * GLYPH_BYTES)
        for gy in range(glyph_height):
            py = y + gy
            if not 0 <= py < canvas_height:
                continue
            row = rows[gy]
            for gx in range(glyph_width):
                px = cursor + gx
                if 0 <= px < canvas_width and row & (0x8000 >> gx):
                    pixels[py * canvas_width + px] = palette_index
        cursor += advance


def localized_image(source: ArenaIMG, pixels: bytearray) -> ArenaIMG:
    return ArenaIMG(
        x=source.x,
        y=source.y,
        width=source.width,
        height=source.height,
        palette=source.palette,
        pixels=bytes(pixels),
    )


def replace_index_from_row(
    pixels: bytearray,
    width: int,
    bounds: tuple[int, int, int, int],
    palette_index: int,
    source_y: int,
) -> None:
    """Erase one flat text color while retaining the surrounding texture."""
    x0, y0, x1, y1 = bounds
    for y in range(y0, y1):
        for x in range(x0, x1):
            offset = y * width + x
            if pixels[offset] == palette_index:
                pixels[offset] = pixels[source_y * width + x]


def clean_equip(source: ArenaIMG) -> ArenaIMG:
    if (source.width, source.height) != (171, 200) or source.palette is not None:
        raise ValueError("EQUIP.IMG must be the unpaletted 171x200 character-sheet overlay")
    pixels = bytearray(source.pixels)

    # The fixed English labels are flat-color bitmap text. Restore texture from
    # adjacent clean rows/columns, then draw full-size HANGUL9 glyphs. Dynamic
    # values and item descriptions remain engine-rendered and are patched in
    # patch_acd.py.
    clone_rect(pixels, source.width, (75, 22, 100, 31), (104, 22))
    replace_index_from_row(pixels, source.width, (12, 191, 41, 199), 253, 190)
    replace_index_from_row(pixels, source.width, (60, 191, 119, 199), 253, 190)
    replace_index_from_row(pixels, source.width, (137, 191, 166, 199), 253, 190)

    header_fill = {41: 87, 42: 87, 43: 180, 44: 87, 45: 87, 46: 253}
    for y, fill in header_fill.items():
        for x in range(62, 114):
            offset = y * source.width + x
            if pixels[offset] == 31:
                pixels[offset] = fill

    return localized_image(source, pixels)


def localize_equip(source: ArenaIMG, font9: bytes) -> ArenaIMG:
    cleaned = clean_equip(source)
    pixels = bytearray(cleaned.pixels)

    draw_text(pixels, 171, 200, font9, "레벨", 105, 22, 9, 9, 10, 253)
    pixels[(24 * 171) + 125] = 253
    pixels[(28 * 171) + 125] = 253
    draw_text(pixels, 171, 200, font9, "장비", 74, 39, 9, 9, 10, 31)
    draw_text(pixels, 171, 200, font9, "종료", 14, 190, 9, 9, 10, 253)
    draw_text(pixels, 171, 200, font9, "마법서", 71, 190, 9, 9, 10, 253)
    draw_text(pixels, 171, 200, font9, "버리기", 133, 190, 9, 9, 10, 253)
    return localized_image(source, pixels)


def write_word_png(
    font9: bytes,
    text: str,
    path: Path,
    rgb: tuple[int, int, int],
) -> Image.Image:
    has_colon = text.endswith(":")
    body = text[:-1] if has_colon else text
    width = ((len(body) - 1) * 10) + 9 + (2 if has_colon else 0)
    mask = bytearray(width * 9)
    draw_text(mask, width, 9, font9, body, 0, 0, 9, 9, 10, 1)
    if has_colon:
        colon_x = len(body) * 10
        mask[(2 * width) + colon_x] = 1
        mask[(6 * width) + colon_x] = 1
    rgba = Image.new("RGBA", (width, 9), (0, 0, 0, 0))
    rgba.putdata([(*rgb, 255) if value else (0, 0, 0, 0) for value in mask])
    rgba.save(path)
    return rgba


def write_word_atlas(
    sprites: list[tuple[str, str, tuple[int, int, int], Image.Image]],
    output_dir: Path,
    asset_name: str,
    screen_placements: dict[str, tuple[int, int, int]] | None = None,
) -> None:
    placements: list[tuple[int, int, str, str, tuple[int, int, int], Image.Image]] = []
    x = y = EQUIP_ATLAS_GUTTER
    row_height = 9
    for filename, text, rgb, sprite in sprites:
        if x + sprite.width + EQUIP_ATLAS_GUTTER > EQUIP_ATLAS_WIDTH:
            x = EQUIP_ATLAS_GUTTER
            y += row_height + EQUIP_ATLAS_GUTTER
        placements.append((x, y, filename, text, rgb, sprite))
        x += sprite.width + EQUIP_ATLAS_GUTTER

    atlas_height = y + row_height + EQUIP_ATLAS_GUTTER
    atlas = Image.new("RGBA", (EQUIP_ATLAS_WIDTH, atlas_height), (0, 0, 0, 0))
    metadata = {
        "asset": asset_name,
        "canvas": [EQUIP_ATLAS_WIDTH, atlas_height],
        "glyph": {"source": "HANGUL9", "size": [9, 9], "scale": 1},
        "spacing": {
            "hangul_advance": 10,
            "atlas_gutter": EQUIP_ATLAS_GUTTER,
        },
        "sprites": [],
    }
    for px, py, filename, text, rgb, sprite in placements:
        atlas.alpha_composite(sprite, (px, py))
        item = {
            "text": text,
            "rect": [px, py, sprite.width, sprite.height],
            "rgb": list(rgb),
            "file": f"words/{filename}",
        }
        if screen_placements is not None and filename in screen_placements:
            screen_x, screen_y, palette_index = screen_placements[filename]
            item["screen_top_left"] = [screen_x, screen_y]
            item["palette_index"] = palette_index
        metadata["sprites"].append(item)

    atlas.save(output_dir / f"04_{asset_name}-text-atlas-actual-size.png")
    (output_dir / f"04_{asset_name}-text-atlas.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_equip_workpack(
    source: ArenaIMG,
    font9: bytes,
    palette_path: Path,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    words_dir = output_dir / "words"
    words_dir.mkdir(parents=True, exist_ok=True)

    write_external_palette_png(source, output_dir / "01_EQUIP-original.png", palette_path)
    write_external_palette_png(
        clean_equip(source), output_dir / "02_EQUIP-clean.png", palette_path
    )
    write_external_palette_png(
        localize_equip(source, font9),
        output_dir / "03_EQUIP-placement-reference.png",
        palette_path,
    )

    gold = (191, 115, 0)  # CHARSHT.COL index 253
    dark_brown = (41, 0, 0)  # CHARSHT.COL index 31
    sprites = []
    for filename, text, rgb in (
        ("01_level.png", "레벨:", gold),
        ("02_equipment.png", "장비", dark_brown),
        ("03_exit.png", "종료", gold),
        ("04_spellbook.png", "마법서", gold),
        ("05_drop.png", "버리기", gold),
    ):
        sprite = write_word_png(font9, text, words_dir / filename, rgb)
        sprites.append((filename, text, rgb, sprite))
    write_word_atlas(
        sprites,
        output_dir,
        "EQUIP",
        {
            "01_level.png": (105, 22, 253),
            "02_equipment.png": (74, 39, 31),
            "03_exit.png": (14, 190, 253),
            "04_spellbook.png": (71, 190, 253),
            "05_drop.png": (133, 190, 253),
        },
    )


def clean_automap(source: ArenaIMG) -> ArenaIMG:
    if (source.width, source.height) != (320, 200) or source.palette is None:
        raise ValueError("AUTOMAP.IMG must be a paletted 320x200 image")
    pixels = bytearray(source.pixels)

    # Restore clean parchment over the four Latin compass letters and Exit.
    clone_rect(pixels, source.width, (230, 22, 242, 35), (266, 22))
    clone_rect(pixels, source.width, (230, 60, 242, 73), (266, 60))
    clone_rect(pixels, source.width, (225, 41, 238, 55), (244, 41))
    clone_rect(pixels, source.width, (304, 41, 317, 55), (288, 41))
    clone_rect(pixels, source.width, (188, 160, 242, 182), (242, 160))

    return localized_image(source, pixels)


def localize_automap(source: ArenaIMG, font9: bytes) -> ArenaIMG:
    cleaned = clean_automap(source)
    pixels = bytearray(cleaned.pixels)

    for text, x, y in (("북", 268, 24), ("남", 268, 62), ("서", 246, 43), ("동", 290, 43)):
        draw_text(pixels, 320, 200, font9, text, x, y, 9, 9, 10, 10)
    draw_text(pixels, 320, 200, font9, "종료", 259, 168, 9, 9, 10, 6)
    return localized_image(source, pixels)


def automap_palette_rgb(source: ArenaIMG, palette_index: int) -> tuple[int, int, int]:
    if source.palette is None:
        raise ValueError("AUTOMAP.IMG has no embedded palette")
    start = palette_index * 3
    return tuple(
        min(source.palette[start + component], 63) * 255 // 63
        for component in range(3)
    )


def write_automap_workpack(
    source: ArenaIMG,
    font9: bytes,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    words_dir = output_dir / "words"
    words_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "완성본-넣는곳").mkdir(parents=True, exist_ok=True)

    write_png(source, output_dir / "01_AUTOMAP-original.png")
    write_png(clean_automap(source), output_dir / "02_AUTOMAP-clean.png")
    write_png(
        localize_automap(source, font9),
        output_dir / "03_AUTOMAP-placement-reference.png",
    )

    direction_rgb = automap_palette_rgb(source, 10)
    exit_rgb = automap_palette_rgb(source, 6)
    sprites = []
    for filename, text, rgb in (
        ("01_north.png", "북", direction_rgb),
        ("02_south.png", "남", direction_rgb),
        ("03_west.png", "서", direction_rgb),
        ("04_east.png", "동", direction_rgb),
        ("05_exit.png", "종료", exit_rgb),
    ):
        sprite = write_word_png(font9, text, words_dir / filename, rgb)
        sprites.append((filename, text, rgb, sprite))
    write_word_atlas(
        sprites,
        output_dir,
        "AUTOMAP",
        {
            "01_north.png": (268, 24, 10),
            "02_south.png": (268, 62, 10),
            "03_west.png": (246, 43, 10),
            "04_east.png": (290, 43, 10),
            "05_exit.png": (259, 168, 6),
        },
    )


def localize_logbook(source: ArenaIMG, font9: bytes, font16: bytes) -> ArenaIMG:
    if (source.width, source.height) != (320, 200) or source.palette is None:
        raise ValueError("LOGBOOK.IMG must be a paletted 320x200 image")
    pixels = bytearray(source.pixels)

    clone_rect(pixels, source.width, (28, 0, 116, 21), (116, 0))
    clone_rect(pixels, source.width, (90, 178, 144, 198), (34, 178))
    clone_rect(pixels, source.width, (176, 178, 231, 198), (252, 178))

    draw_text(pixels, 320, 200, font16, "일지", 144, 1, 16, 16, 16, 0)
    draw_text(pixels, 320, 200, font9, "인쇄", 49, 184, 9, 9, 10, 206)
    draw_text(pixels, 320, 200, font9, "종료", 269, 184, 9, 9, 10, 206)
    return localized_image(source, pixels)


def write_external_palette_png(image: ArenaIMG, path: Path, palette_path: Path) -> None:
    palette = palette_path.read_bytes()
    if len(palette) != 776:
        raise ValueError(f"CHARSHT.COL must be 776 bytes: {palette_path}")
    preview = Image.frombytes("P", (image.width, image.height), image.pixels)
    preview.putpalette(palette[-768:])
    preview.save(path)


def write_result(
    image: ArenaIMG,
    path: Path,
    preview: Path | None,
    external_palette: Path | None = None,
) -> None:
    encode_uncompressed(image, image.pixels, path)
    decoded = decode(path)
    if decoded != image:
        raise ValueError(f"round-trip mismatch: {path}")
    if preview is not None:
        if image.palette is None:
            if external_palette is None:
                raise ValueError(f"external palette required for preview: {path.name}")
            write_external_palette_png(image, preview, external_palette)
        else:
            write_png(image, preview)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--font9", type=Path, required=True)
    parser.add_argument("--font16", type=Path, required=True)
    parser.add_argument("--charsht-col", type=Path)
    parser.add_argument("--preview-dir", type=Path)
    parser.add_argument("--equip-workpack-dir", type=Path)
    parser.add_argument("--automap-workpack-dir", type=Path)
    args = parser.parse_args()

    font9 = args.font9.read_bytes()
    font16 = args.font16.read_bytes()
    expected_size = 11172 * GLYPH_BYTES
    if len(font9) != expected_size or len(font16) != expected_size:
        raise ValueError("Hangul font bank size is invalid")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.preview_dir is not None:
        args.preview_dir.mkdir(parents=True, exist_ok=True)

    outputs = (
        ("AUTOMAP.IMG", localize_automap(decode(args.source_dir / "AUTOMAP.IMG"), font9), None),
        ("LOGBOOK.IMG", localize_logbook(decode(args.source_dir / "LOGBOOK.IMG"), font9, font16), None),
        ("EQUIP.IMG", localize_equip(decode(args.source_dir / "EQUIP.IMG"), font9), args.charsht_col),
    )
    for name, image, external_palette in outputs:
        preview = args.preview_dir / f"{Path(name).stem}.png" if args.preview_dir else None
        write_result(image, args.output_dir / name, preview, external_palette)
        print(f"localized: {name}")
    if args.equip_workpack_dir is not None:
        if args.charsht_col is None:
            raise ValueError("--equip-workpack-dir requires --charsht-col")
        write_equip_workpack(
            decode(args.source_dir / "EQUIP.IMG"),
            font9,
            args.charsht_col,
            args.equip_workpack_dir,
        )
        print(f"workpack: {args.equip_workpack_dir}")
    if args.automap_workpack_dir is not None:
        write_automap_workpack(
            decode(args.source_dir / "AUTOMAP.IMG"),
            font9,
            args.automap_workpack_dir,
        )
        print(f"workpack: {args.automap_workpack_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
