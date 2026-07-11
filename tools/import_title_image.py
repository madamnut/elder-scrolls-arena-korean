#!/usr/bin/env python3
"""Import the final Korean 320x200 title PNG into Arena's loose TITLE.IMG."""

from pathlib import Path

from PIL import Image

from arena_img import decode as decode_img, encode_uncompressed, palette_8bit


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "korean-patch" / "artist-handoff" / "해상도조정완료" / "TITLE-gpt-raw.png"
ORIGINAL = ROOT / "korean-patch" / "backup" / "original-loose" / "TITLE.IMG"
OUTPUT = ROOT / "korean-patch" / "build" / "title-final" / "TITLE.IMG"
PREVIEW = ROOT / "korean-patch" / "analysis" / "title-final-indexed.png"


def main() -> int:
    edited = Image.open(INPUT).convert("RGB")
    if edited.size != (320, 200):
        raise ValueError(f"TITLE-gpt-raw.png: expected 320x200, got {edited.size}")

    original = decode_img(ORIGINAL)
    if original.palette is None:
        raise ValueError("Original TITLE.IMG has no embedded palette")

    palette_image = Image.frombytes("P", (original.width, original.height), original.pixels)
    palette_image.putpalette(palette_8bit(original.palette))
    indexed = edited.quantize(palette=palette_image, dither=Image.Dither.NONE)

    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    indexed.save(PREVIEW)
    encode_uncompressed(original, indexed.tobytes(), OUTPUT)
    print(f"TITLE-gpt-raw.png -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
