#!/usr/bin/env python3
"""Extract Arena's nine OUTPROV.CIF highlighted province-name frames."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct

from PIL import Image

from arena_img import decode as decode_img, decode_type04, decode_type08, palette_8bit


HEADER = struct.Struct("<6H")
FRAME_NAMES = (
    "high-rock",
    "hammerfell",
    "skyrim",
    "morrowind",
    "summurset-isle",
    "valenwood",
    "elsweyr",
    "black-marsh",
    "imperial-province",
)


def decode_frames(path: Path) -> list[tuple[int, int, int, int, bytes]]:
    data = path.read_bytes()
    frames: list[tuple[int, int, int, int, bytes]] = []
    offset = 0
    while offset < len(data):
        if offset + HEADER.size > len(data):
            raise ValueError(f"truncated CIF header at 0x{offset:X}")
        x, y, width, height, flags, packed_size = HEADER.unpack_from(data, offset)
        start = offset + HEADER.size
        end = start + packed_size
        if end > len(data):
            raise ValueError(f"truncated CIF frame at 0x{offset:X}")
        payload = data[start:end]
        compression = flags & 0xFF
        if compression == 0:
            pixels = payload[: width * height]
        elif compression == 4:
            pixels = decode_type04(payload, width * height)
        elif compression == 8:
            if len(payload) < 2:
                raise ValueError(f"missing type-8 size word at 0x{offset:X}")
            pixels = decode_type08(payload[2:], width * height)
        else:
            raise ValueError(f"unsupported CIF compression type {compression}")
        if len(pixels) != width * height:
            raise ValueError(f"wrong decoded size at 0x{offset:X}")
        frames.append((x, y, width, height, pixels))
        offset = end
    return frames


def rgba_frame(width: int, height: int, pixels: bytes, palette: list[int]) -> Image.Image:
    indexed = Image.frombytes("P", (width, height), pixels)
    indexed.putpalette(palette)
    rgba = indexed.convert("RGBA")
    alpha = Image.frombytes("L", (width, height), bytes(0 if value == 0 else 255 for value in pixels))
    rgba.putalpha(alpha)
    return rgba


def main() -> int:
    parser = argparse.ArgumentParser(description="OUTPROV.CIF 강조 지역명 9장 추출")
    parser.add_argument("cif", type=Path)
    parser.add_argument("tamriel", type=Path, help="팔레트와 합성 미리보기에 쓸 TAMRIEL.MNU")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    tamriel = decode_img(args.tamriel)
    if tamriel.palette is None:
        raise ValueError("TAMRIEL.MNU has no embedded palette")
    palette = palette_8bit(tamriel.palette)
    frames = decode_frames(args.cif)
    if len(frames) != len(FRAME_NAMES):
        raise ValueError(f"expected 9 OUTPROV frames, found {len(frames)}")

    base = Image.frombytes("P", (tamriel.width, tamriel.height), tamriel.pixels)
    base.putpalette(palette)
    base = base.convert("RGBA")
    args.output.mkdir(parents=True, exist_ok=True)

    manifest = ["# OUTPROV.CIF 강조 지역명", "", "| 번호 | 지역 | 좌표 | 원본 크기 |", "|---:|---|---:|---:|"]
    for index, (name, frame) in enumerate(zip(FRAME_NAMES, frames)):
        x, y, width, height, pixels = frame
        image = rgba_frame(width, height, pixels, palette)
        stem = f"{index:02d}-{name}"
        image.save(args.output / f"{stem}-original-{width}x{height}.png")
        preview = base.copy()
        preview.alpha_composite(image, (x, y))
        preview.save(args.output / f"{stem}-map-preview-320x200.png")
        manifest.append(f"| {index} | `{name}` | ({x}, {y}) | {width}×{height} |")

    (args.output / "프레임정보.md").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print(f"extracted {len(frames)} frames: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
