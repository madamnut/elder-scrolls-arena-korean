#!/usr/bin/env python3
"""Render tightly cropped transparent menu-label samples at exact pixel heights."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


LABELS = (
    ("load-game", "저장한 게임 불러오기"),
    ("new-game", "새 게임 시작"),
    ("exit", "종료"),
)
TEXT_COLOR = (109, 12, 12, 255)


def render(font_path: Path, text: str, target_height: int) -> tuple[Image.Image, int]:
    best: tuple[int, int, ImageFont.FreeTypeFont, tuple[int, int, int, int]] | None = None
    for size in range(4, 65):
        font = ImageFont.truetype(str(font_path), size)
        bbox = font.getbbox(text, stroke_width=0)
        visible_height = bbox[3] - bbox[1]
        score = (abs(visible_height - target_height), size)
        if best is None or score < best[:2]:
            best = (score[0], score[1], font, bbox)
    assert best is not None
    _, size, font, bbox = best
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    image = Image.new("RGBA", (width + 2, height + 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.text((1 - bbox[0], 1 - bbox[1]), text, font=font, fill=TEXT_COLOR)
    return image, size


def render_native(
    font_path: Path,
    text: str,
    font_size: int,
    color: tuple[int, int, int, int] = TEXT_COLOR,
    binary_alpha: bool = False,
) -> Image.Image:
    """Rasterize at the requested font size without scaling the glyph bitmap."""
    font = ImageFont.truetype(str(font_path), font_size)
    bbox = font.getbbox(text, stroke_width=0)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    image = Image.new("RGBA", (width + 2, height + 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.text((1 - bbox[0], 1 - bbox[1]), text, font=font, fill=color)
    if binary_alpha:
        red, green, blue, alpha = image.split()
        alpha = alpha.point(lambda value: 255 if value >= 128 else 0)
        solid = Image.new("L", image.size, 0)
        image = Image.merge("RGBA", (solid, solid, solid, alpha))
    return image


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("font", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--native-sizes",
        action="store_true",
        help="Render at nominal font sizes 10, 12, and 14 without height fitting.",
    )
    parser.add_argument(
        "--single-size",
        type=int,
        help="Render one nominal font size instead of the preset comparisons.",
    )
    parser.add_argument(
        "--black-binary",
        action="store_true",
        help="Use solid black pixels with no antialiased edge alpha.",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    if args.single_size is not None:
        for slug, text in LABELS:
            image = render_native(
                args.font,
                text,
                args.single_size,
                color=(0, 0, 0, 255) if args.black_binary else TEXT_COLOR,
                binary_alpha=args.black_binary,
            )
            output = args.output / f"{slug}.png"
            image.save(output)
            alpha_values = sorted(set(image.getchannel("A").getdata()))
            print(
                f"{output}: canvas={image.width}x{image.height}, "
                f"font-size={args.single_size}, alpha={alpha_values}"
            )
        return 0

    if args.native_sizes:
        for font_size in (10, 12, 14):
            size_dir = args.output / f"font-size-{font_size}"
            size_dir.mkdir(parents=True, exist_ok=True)
            for slug, text in LABELS:
                image = render_native(args.font, text, font_size)
                output = size_dir / f"{slug}.png"
                image.save(output)
                print(
                    f"{output}: canvas={image.width}x{image.height}, "
                    f"visible={image.height - 2}px, font-size={font_size}"
                )
        return 0

    for target_height in (10, 12, 14):
        height_dir = args.output / f"height-{target_height}px"
        height_dir.mkdir(parents=True, exist_ok=True)
        for slug, text in LABELS:
            image, font_size = render(args.font, text, target_height)
            output = height_dir / f"{slug}.png"
            image.save(output)
            print(
                f"{output}: canvas={image.width}x{image.height}, "
                f"visible={image.height - 2}px, font-size={font_size}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
