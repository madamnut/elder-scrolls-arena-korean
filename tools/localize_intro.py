#!/usr/bin/env python3
"""Create a Korean INTRO.FLC title-card prototype."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

from arena_flc import FLC, FLCError, Frame, decode, encode


CANONICAL_SIZE = (160, 150)

# Inner illustrated cover quadrilateral, clockwise from top-left. Coordinates
# were measured from the decoded 320x200 Arena CD 1.07 INTRO.FLC.
QUAD_KEYFRAMES: dict[int, tuple[tuple[float, float], ...]] = {
    63: ((134, 65), (163, 62), (171, 88), (136, 91)),
    65: ((128, 59), (171, 55), (181, 93), (130, 97)),
    69: ((120, 31), (181, 27), (196, 86), (123, 92)),
    73: ((105, 27), (201, 19), (226, 121), (108, 130)),
    74: ((101, 35), (211, 25), (242, 158), (104, 166)),
    75: ((94, 54), (221, 42), (260, 202), (97, 207)),
}


class IntroError(ValueError):
    pass


def interpolate_quad(frame_index: int) -> tuple[tuple[float, float], ...]:
    keys = sorted(QUAD_KEYFRAMES)
    if frame_index <= keys[0]:
        return QUAD_KEYFRAMES[keys[0]]
    if frame_index >= keys[-1]:
        return QUAD_KEYFRAMES[keys[-1]]
    for left, right in zip(keys, keys[1:]):
        if left <= frame_index <= right:
            amount = (frame_index - left) / (right - left)
            return tuple(
                (
                    QUAD_KEYFRAMES[left][i][0] * (1.0 - amount) + QUAD_KEYFRAMES[right][i][0] * amount,
                    QUAD_KEYFRAMES[left][i][1] * (1.0 - amount) + QUAD_KEYFRAMES[right][i][1] * amount,
                )
                for i in range(4)
            )
    raise AssertionError(frame_index)


def solve_linear(matrix: list[list[float]], values: list[float]) -> list[float]:
    size = len(values)
    augmented = [row[:] + [value] for row, value in zip(matrix, values)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1.0e-9:
            raise IntroError("원근 변환 행렬을 풀 수 없습니다.")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [
                    current - (factor * pivot_value)
                    for current, pivot_value in zip(augmented[row], augmented[column])
                ]
    return [augmented[row][-1] for row in range(size)]


def perspective_coefficients(
    output_points: tuple[tuple[float, float], ...],
    input_points: tuple[tuple[float, float], ...],
) -> tuple[float, ...]:
    # Pillow expects output -> input mapping coefficients.
    matrix: list[list[float]] = []
    values: list[float] = []
    for (x, y), (u, v) in zip(output_points, input_points):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        values.append(u)
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        values.append(v)
    return tuple(solve_linear(matrix, values))


def centered_text(draw, box: tuple[int, int, int, int], text: str, font, fill) -> None:
    left, top, right, bottom = box
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = left + ((right - left - width) // 2) - bbox[0]
    y = top + ((bottom - top - height) // 2) - bbox[1]
    draw.text((x, y), text, font=font, fill=fill)


def edit_frame(frame: Frame, width: int, height: int, frame_index: int, ttf: Path) -> Frame:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise IntroError("INTRO 편집에는 Pillow가 필요합니다.") from exc

    quad = interpolate_quad(frame_index)
    canonical_corners = ((0.0, 0.0), (159.0, 0.0), (159.0, 149.0), (0.0, 149.0))
    flat_palette = [component for color in frame.palette for component in color]
    source_p = Image.frombytes("P", (width, height), frame.pixels)
    source_p.putpalette(flat_palette)
    source_rgb = source_p.convert("RGB")

    to_canonical = perspective_coefficients(canonical_corners, quad)
    canonical = source_rgb.transform(
        CANONICAL_SIZE,
        Image.Transform.PERSPECTIVE,
        to_canonical,
        resample=Image.Resampling.NEAREST,
    )
    draw = ImageDraw.Draw(canonical, "RGBA")

    # Opaque/semitransparent bands cover the baked English while retaining the
    # landscape illustration between them.
    draw.rectangle((8, 5, 151, 57), fill=(35, 31, 48, 224), outline=(150, 105, 25, 255), width=2)
    draw.rectangle((10, 61, 149, 88), fill=(35, 27, 28, 224), outline=(120, 82, 22, 255), width=1)
    draw.rectangle((8, 128, 151, 146), fill=(25, 17, 15, 235), outline=(110, 70, 18, 255), width=1)

    title_font = ImageFont.truetype(str(ttf), 20)
    chapter_font = ImageFont.truetype(str(ttf), 13)
    credit_font = ImageFont.truetype(str(ttf), 8)
    gold = (205, 148, 42, 255)
    pale_gold = (190, 142, 58, 255)
    centered_text(draw, (8, 5, 152, 57), "엘더 스크롤", title_font, gold)
    centered_text(draw, (10, 61, 150, 88), "제1장: 아레나", chapter_font, gold)
    centered_text(draw, (8, 128, 152, 146), "베데스다 소프트웍스", credit_font, pale_gold)

    from_canonical = perspective_coefficients(quad, canonical_corners)
    warped = canonical.transform(
        (width, height),
        Image.Transform.PERSPECTIVE,
        from_canonical,
        resample=Image.Resampling.NEAREST,
    )
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).polygon(quad, fill=255)

    palette_holder = Image.new("P", (1, 1))
    palette_holder.putpalette(flat_palette)
    quantized = warped.quantize(palette=palette_holder, dither=Image.Dither.NONE)
    output = source_p.copy()
    output.paste(quantized, (0, 0), mask)
    return Frame(output.tobytes(), frame.palette)


def build(input_path: Path, output_path: Path, ttf: Path, preview: Path | None) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise IntroError("INTRO 편집에는 Pillow가 필요합니다.") from exc
    flc = decode(input_path)
    frames = list(flc.frames)
    for index in range(min(QUAD_KEYFRAMES), len(frames)):
        frames[index] = edit_frame(frames[index], flc.width, flc.height, index, ttf)
    localized = replace(flc, frames=tuple(frames))
    encode(localized, output_path)

    decoded = decode(output_path)
    if decoded != localized:
        raise IntroError("한글 INTRO.FLC 왕복 검증 실패")

    if preview is not None:
        indices = [63, 65, 69, 73, 74, 75]
        canvas = Image.new("RGB", (flc.width * 2, (flc.height + 20) * 3), (0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        for position, index in enumerate(indices):
            frame = decoded.frames[index]
            image = Image.frombytes("P", (flc.width, flc.height), frame.pixels)
            image.putpalette([component for color in frame.palette for component in color])
            x = (position % 2) * flc.width
            y = (position // 2) * (flc.height + 20)
            canvas.paste(image.convert("RGB"), (x, y))
            draw.text((x + 4, y + flc.height + 2), f"frame {index}", fill="white")
        preview.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(preview)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Arena INTRO.FLC 한글 표지 생성기")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ttf", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args(argv)
    try:
        build(args.input, args.output, args.ttf, args.preview)
    except (IntroError, FLCError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"localized FLC: {args.output}")
    if args.preview:
        print(f"preview: {args.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

