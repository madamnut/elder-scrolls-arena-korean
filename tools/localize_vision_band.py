#!/usr/bin/env python3
"""Expand an Arena FLC's black subtitle band without altering the picture."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from arena_flc import FLC, Frame, decode, encode


EXPECTED_WIDTH = 320
EXPECTED_HEIGHT = 200
DEFAULT_BAND_TOP = 163


class SubtitleBandError(RuntimeError):
    pass


def expand_band(source: FLC, band_top: int, expected_frames: int | None) -> FLC:
    if (source.width, source.height) != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
        raise SubtitleBandError(
            f"unsupported FLC size: {source.width}x{source.height}"
        )
    if not source.frames:
        raise SubtitleBandError("FLC has no frames")
    if expected_frames is not None and len(source.frames) != expected_frames:
        raise SubtitleBandError(
            f"unexpected FLC frame count: {len(source.frames)} "
            f"(expected {expected_frames})"
        )
    if not 0 <= band_top < source.height:
        raise SubtitleBandError(f"invalid band top: {band_top}")

    band_start = band_top * source.width
    frames = tuple(
        Frame(
            palette=frame.palette,
            pixels=frame.pixels[:band_start]
            + bytes(source.width * (source.height - band_top)),
        )
        for frame in source.frames
    )
    return FLC(
        width=source.width,
        height=source.height,
        speed_ms=source.speed_ms,
        frames=frames,
    )


def validate(source: FLC, result: FLC, band_top: int) -> None:
    if (result.width, result.height, result.speed_ms) != (
        source.width,
        source.height,
        source.speed_ms,
    ):
        raise SubtitleBandError("FLC geometry or playback speed changed")
    if len(result.frames) != len(source.frames):
        raise SubtitleBandError("FLC frame count changed")

    band_start = band_top * source.width
    expected_band = bytes(source.width * (source.height - band_top))
    for index, (before, after) in enumerate(zip(source.frames, result.frames)):
        if after.palette != before.palette:
            raise SubtitleBandError(f"frame {index}: palette changed")
        if after.pixels[:band_start] != before.pixels[:band_start]:
            raise SubtitleBandError(f"frame {index}: picture above band changed")
        if after.pixels[band_start:] != expected_band:
            raise SubtitleBandError(f"frame {index}: subtitle band is not black")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Expand an Arena FLC's black subtitle band for Korean text"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--band-top", type=int, default=DEFAULT_BAND_TOP)
    parser.add_argument(
        "--expected-frames",
        type=int,
        help="Reject the input unless it has exactly this many frames",
    )
    args = parser.parse_args(argv)

    try:
        source = decode(args.input)
        localized = expand_band(source, args.band_top, args.expected_frames)
        validate(source, localized, args.band_top)
        encode(localized, args.output)
        decoded = decode(args.output)
        validate(source, decoded, args.band_top)
    except (OSError, SubtitleBandError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"localized: {args.output}")
    print(f"band: y={args.band_top}..{source.height - 1}")
    print(f"frames: {len(source.frames)}")
    print(f"bytes: {args.output.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
