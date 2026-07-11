#!/usr/bin/env python3
"""Decode and conservatively encode the Autodesk FLC subset used by Arena."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import struct
import sys


FLC_MAGIC = 0xAF12
FRAME_MAGIC = 0xF1FA
PREFIX_MAGIC = 0xF100
COLOR_256 = 0x04
FLI_SS2 = 0x07
BLACK = 0x0D
FLI_BRUN = 0x0F
FLI_COPY = 0x10


class FLCError(ValueError):
    pass


@dataclass(frozen=True)
class Frame:
    pixels: bytes
    palette: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True)
class FLC:
    width: int
    height: int
    speed_ms: int
    frames: tuple[Frame, ...]


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def i16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<h", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def signed_byte(value: int) -> int:
    return value - 256 if value >= 128 else value


def decode_palette(payload: bytes, palette: list[tuple[int, int, int]]) -> None:
    if len(payload) < 2:
        raise FLCError("잘린 팔레트 청크")
    packet_count = u16(payload, 0)
    offset = 2
    color_index = 0
    for _ in range(packet_count):
        if offset + 2 > len(payload):
            raise FLCError("잘린 팔레트 패킷")
        color_index += payload[offset]
        count = payload[offset + 1] or 256
        offset += 2
        if color_index + count > 256 or offset + (count * 3) > len(payload):
            raise FLCError("팔레트 패킷 범위 초과")
        for _ in range(count):
            palette[color_index] = tuple(payload[offset : offset + 3])
            color_index += 1
            offset += 3


def decode_brun(payload: bytes, width: int, height: int) -> bytearray:
    output = bytearray(width * height)
    offset = 0
    for y in range(height):
        if offset >= len(payload):
            raise FLCError("잘린 BRUN 행")
        offset += 1  # ignored packet count
        x = 0
        while x < width:
            if offset >= len(payload):
                raise FLCError("잘린 BRUN 패킷")
            count = signed_byte(payload[offset])
            offset += 1
            if count > 0:
                if offset >= len(payload):
                    raise FLCError("잘린 BRUN 반복 패킷")
                amount = min(count, width - x)
                output[(y * width) + x : (y * width) + x + amount] = bytes((payload[offset],)) * amount
                x += amount
                offset += 1
            elif count < 0:
                amount = -count
                if offset + amount > len(payload):
                    raise FLCError("잘린 BRUN 리터럴 패킷")
                copy_count = min(amount, width - x)
                output[(y * width) + x : (y * width) + x + copy_count] = payload[offset : offset + copy_count]
                x += copy_count
                offset += amount
            else:
                raise FLCError("BRUN 패킷 길이가 0입니다.")
    return output


def decode_ss2(payload: bytes, width: int, height: int, pixels: bytearray) -> None:
    if len(payload) < 2:
        raise FLCError("잘린 SS2 청크")
    line_count = u16(payload, 0)
    offset = 2
    y = 0
    for _ in range(line_count):
        packet_count = None
        while offset + 2 <= len(payload):
            packet = i16(payload, offset)
            raw_packet = u16(payload, offset)
            offset += 2
            bit15 = bool(raw_packet & 0x8000)
            bit14 = bool(raw_packet & 0x4000)
            if bit15 and bit14:
                y += -packet
            elif bit15:
                if 0 <= y < height:
                    pixels[(y * width) + width - 1] = raw_packet & 0xFF
                y += 1
            else:
                packet_count = packet
                break
        if packet_count is None:
            raise FLCError("SS2 패킷 수를 찾지 못했습니다.")

        x = 0
        for _ in range(packet_count):
            if offset + 2 > len(payload):
                raise FLCError("잘린 SS2 데이터 패킷")
            x += payload[offset]
            count = signed_byte(payload[offset + 1])
            offset += 2
            if count > 0:
                byte_count = count * 2
                if offset + byte_count > len(payload):
                    raise FLCError("잘린 SS2 리터럴 데이터")
                if 0 <= y < height and x < width:
                    amount = min(byte_count, width - x)
                    pixels[(y * width) + x : (y * width) + x + amount] = payload[offset : offset + amount]
                x += byte_count
                offset += byte_count
            elif count < 0:
                if offset + 2 > len(payload):
                    raise FLCError("잘린 SS2 반복 데이터")
                pair = payload[offset : offset + 2]
                offset += 2
                byte_count = (-count) * 2
                repeated = (pair * (-count))[:byte_count]
                if 0 <= y < height and x < width:
                    amount = min(byte_count, width - x)
                    pixels[(y * width) + x : (y * width) + x + amount] = repeated[:amount]
                x += byte_count
            else:
                raise FLCError("SS2 패킷 길이가 0입니다.")
        y += 1


def decode(path: Path) -> FLC:
    data = path.read_bytes()
    if len(data) < 128 or u16(data, 4) != FLC_MAGIC:
        raise FLCError("Arena FLC(0xAF12)가 아닙니다.")
    declared_size = u32(data, 0)
    declared_frames = u16(data, 6)
    width, height = u16(data, 8), u16(data, 10)
    depth = u16(data, 12)
    speed_ms = u32(data, 16)
    if declared_size > len(data) or depth != 8 or width <= 0 or height <= 0:
        raise FLCError("지원하지 않는 FLC 헤더")

    pixels = bytearray(width * height)
    palette: list[tuple[int, int, int]] = [(0, 0, 0)] * 256
    frames: list[Frame] = []
    offset = 128
    while offset + 16 <= min(declared_size, len(data)):
        frame_size, frame_type, chunk_count = struct.unpack_from("<IHH", data, offset)
        if frame_size < 16 or offset + frame_size > len(data):
            raise FLCError(f"잘못된 프레임 크기 (오프셋 {offset})")
        if frame_type == FRAME_MAGIC:
            chunk_offset = offset + 16
            for _ in range(chunk_count):
                if chunk_offset + 6 > offset + frame_size:
                    raise FLCError("프레임을 벗어난 청크 헤더")
                chunk_size, chunk_type = struct.unpack_from("<IH", data, chunk_offset)
                if chunk_size < 6 or chunk_offset + chunk_size > offset + frame_size:
                    raise FLCError("프레임을 벗어난 청크")
                payload = data[chunk_offset + 6 : chunk_offset + chunk_size]
                if chunk_type == COLOR_256:
                    decode_palette(payload, palette)
                elif chunk_type == FLI_BRUN:
                    pixels = decode_brun(payload, width, height)
                elif chunk_type == FLI_SS2:
                    decode_ss2(payload, width, height, pixels)
                elif chunk_type == FLI_COPY:
                    expected = width * height
                    if len(payload) < expected:
                        raise FLCError("잘린 COPY 프레임")
                    pixels[:] = payload[:expected]
                elif chunk_type == BLACK:
                    pixels[:] = b"\0" * len(pixels)
                chunk_offset += chunk_size
            frames.append(Frame(bytes(pixels), tuple(palette)))
        elif frame_type != PREFIX_MAGIC:
            raise FLCError(f"알 수 없는 프레임 형식 0x{frame_type:04X}")
        offset += frame_size

    # Arena FLCs contain one ring frame after the declared animation frames.
    if len(frames) == declared_frames + 1:
        frames.pop()
    if len(frames) != declared_frames:
        raise FLCError(f"프레임 수 불일치: 헤더={declared_frames}, 실제={len(frames)}")
    return FLC(width, height, speed_ms, tuple(frames))


def make_palette_chunk(palette: tuple[tuple[int, int, int], ...]) -> bytes:
    if len(palette) != 256:
        raise FLCError("팔레트 색상 수가 256이 아닙니다.")
    payload = bytearray(struct.pack("<HBB", 1, 0, 0))
    for color in palette:
        if len(color) != 3 or any(not 0 <= component <= 255 for component in color):
            raise FLCError("잘못된 팔레트 색상")
        payload.extend(color)
    return struct.pack("<IH", 6 + len(payload), COLOR_256) + payload


def make_copy_chunk(pixels: bytes, expected: int) -> bytes:
    if len(pixels) != expected:
        raise FLCError("프레임 픽셀 크기가 맞지 않습니다.")
    return struct.pack("<IH", 6 + len(pixels), FLI_COPY) + pixels


def make_frame(chunks: list[bytes]) -> bytes:
    size = 16 + sum(len(chunk) for chunk in chunks)
    return struct.pack("<IHH8x", size, FRAME_MAGIC, len(chunks)) + b"".join(chunks)


def encode(flc: FLC, path: Path) -> None:
    if not flc.frames or len(flc.frames) > 0xFFFF:
        raise FLCError("지원하지 않는 프레임 수")
    expected_pixels = flc.width * flc.height
    encoded_frames: list[bytes] = []
    previous_palette = None
    for frame in list(flc.frames) + [flc.frames[0]]:
        chunks: list[bytes] = []
        if frame.palette != previous_palette:
            chunks.append(make_palette_chunk(frame.palette))
            previous_palette = frame.palette
        chunks.append(make_copy_chunk(frame.pixels, expected_pixels))
        encoded_frames.append(make_frame(chunks))

    header = bytearray(128)
    total_size = 128 + sum(len(frame) for frame in encoded_frames)
    struct.pack_into("<IHHHHHHI", header, 0, total_size, FLC_MAGIC, len(flc.frames),
        flc.width, flc.height, 8, 3, flc.speed_ms)
    struct.pack_into("<HH", header, 40, 6, 5)  # classic 320x200 pixel aspect ratio
    struct.pack_into("<II", header, 80, 128, 128 + len(encoded_frames[0]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(header) + b"".join(encoded_frames))


def write_png(frame: Frame, width: int, height: int, path: Path) -> None:
    try:
        from PIL import Image
    except ImportError as exc:
        raise FLCError("PNG 추출에는 Pillow가 필요합니다.") from exc
    image = Image.frombytes("P", (width, height), frame.pixels)
    flat_palette = [component for color in frame.palette for component in color]
    image.putpalette(flat_palette)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TES Arena FLC 디코더/보존형 인코더")
    subparsers = parser.add_subparsers(dest="command", required=True)
    info_parser = subparsers.add_parser("info")
    info_parser.add_argument("input", type=Path)
    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("input", type=Path)
    extract_parser.add_argument("output", type=Path)
    roundtrip_parser = subparsers.add_parser("roundtrip")
    roundtrip_parser.add_argument("input", type=Path)
    roundtrip_parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)

    try:
        flc = decode(args.input)
        if args.command == "info":
            print(f"size: {flc.width}x{flc.height}")
            print(f"frames: {len(flc.frames)}")
            print(f"speed_ms: {flc.speed_ms}")
            print(f"palettes: {len(set(frame.palette for frame in flc.frames))}")
        elif args.command == "extract":
            for index, frame in enumerate(flc.frames):
                write_png(frame, flc.width, flc.height, args.output / f"frame-{index:04d}.png")
            print(f"extracted: {len(flc.frames)} frames -> {args.output}")
        else:
            encode(flc, args.output)
            decoded = decode(args.output)
            if decoded != flc:
                raise FLCError("왕복 인코딩 후 프레임 또는 팔레트가 달라졌습니다.")
            print(f"roundtrip OK: {args.output}")
            print(f"frames: {len(flc.frames)}")
            print(f"bytes: {args.output.stat().st_size}")
    except (FLCError, OSError, struct.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

