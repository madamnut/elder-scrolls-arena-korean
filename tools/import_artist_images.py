#!/usr/bin/env python3
"""Import the user's final 320x200 PNG story screens into Arena IMG files."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from arena_flc import decode as decode_flc
from arena_img import decode as decode_img, encode_uncompressed, palette_8bit


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "arena-korean-work" / "artist-handoff" / "해상도조정완료"
ORIGINAL = ROOT / "arena-korean-work" / "analysis" / "bsa-decoded"
OUTPUT = ROOT / "arena-korean-work" / "build" / "artist-final"
PREVIEW = ROOT / "arena-korean-work" / "analysis" / "artist-final-indexed"

MAPPING = {
    "01_QUOTE.png": "QUOTE.IMG",
    "02_SCROLL01.png": "SCROLL01.IMG",
    "03_SCROLL02.png": "SCROLL02.IMG",
    "04_SCROLL03.png": "SCROLL03.IMG",
    "05_MENU.png": "MENU.IMG",
    **{f"{index + 5:02d}_INTRO0{index}.png": f"INTRO0{index}.IMG" for index in range(1, 10)},
}


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    shared_palette = decode_flc(ROOT / "ARENA" / "SCROLL.FLC").frames[-1].palette
    shared_flat = [component for color in shared_palette for component in color]

    for png_name, img_name in MAPPING.items():
        input_path = INPUT / png_name
        if not input_path.is_file():
            raise FileNotFoundError(input_path)
        edited = Image.open(input_path).convert("RGB")
        if edited.size != (320, 200):
            raise ValueError(f"{png_name}: expected 320x200, got {edited.size}")

        # The CD release ships a loose SCROLL03.IMG that overrides the
        # different BSA entry. It contains the complete landscape artwork and
        # an embedded palette, so use the file the game actually loads.
        original_path = (
            ROOT / "ARENA" / "SCROLL03.IMG"
            if img_name == "SCROLL03.IMG"
            else ORIGINAL / img_name
        )
        original = decode_img(original_path)
        palette_image = Image.frombytes("P", (original.width, original.height), original.pixels)
        if original.palette is not None:
            palette_image.putpalette(palette_8bit(original.palette))
        else:
            palette_image.putpalette(shared_flat)

        indexed = edited.quantize(palette=palette_image, dither=Image.Dither.NONE)
        indexed.save(PREVIEW / f"{Path(img_name).stem}.png")
        encode_uncompressed(original, indexed.tobytes(), OUTPUT / img_name)
        print(f"{png_name} -> {img_name}")

    print(f"imported: {len(MAPPING)} images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
