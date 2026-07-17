#!/usr/bin/env python3
"""Decode and conservatively encode headered TES Arena IMG files."""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
import struct

from PIL import Image


HEADER = struct.Struct("<6H")


@dataclass(frozen=True)
class ArenaIMG:
    x: int
    y: int
    width: int
    height: int
    palette: bytes | None
    pixels: bytes


def decode_type04(data: bytes, output_size: int) -> bytes:
    history = bytearray([0x20] * 4096)
    history_pos = 0
    source = 0
    output = bytearray()
    bits_left = 0
    mask = 0
    while source < len(data) and len(output) < output_size:
        if bits_left == 0:
            mask = data[source]
            source += 1
            bits_left = 8
        if mask & 1:
            value = data[source]
            source += 1
            history[history_pos & 0xFFF] = value
            history_pos += 1
            output.append(value)
        else:
            byte1, byte2 = data[source], data[source + 1]
            source += 2
            count = (byte2 & 0x0F) + 3
            copy_pos = (((byte2 & 0xF0) << 4) | byte1) + 18
            for _ in range(count):
                if len(output) >= output_size:
                    break
                value = history[copy_pos & 0xFFF]
                copy_pos += 1
                history[history_pos & 0xFFF] = value
                history_pos += 1
                output.append(value)
        mask >>= 1
        bits_left -= 1
    output.extend(b"\0" * (output_size - len(output)))
    return bytes(output)


def encode_type04(data: bytes, target_size: int | None = None) -> bytes:
    """Greedy type-4 encoder, optionally expanded to an exact byte length."""
    positions: dict[bytes, deque[int]] = defaultdict(deque)
    tokens: list[tuple[int, int, int]] = []  # source, match source (-1 for literal), length
    source = 0
    while source < len(data):
        best_pos = -1
        best_length = 0
        if source + 3 <= len(data):
            key = data[source : source + 3]
            candidates = positions[key]
            while candidates and source - candidates[0] > 4096:
                candidates.popleft()
            for candidate in reversed(candidates):
                distance = source - candidate
                length = 0
                limit = min(18, len(data) - source)
                while length < limit:
                    compare_at = candidate + (length % distance)
                    if data[source + length] != data[compare_at]:
                        break
                    length += 1
                if length > best_length:
                    best_pos = candidate
                    best_length = length
                    if length == 18:
                        break

        token_start = source
        if best_length >= 3:
            tokens.append((source, best_pos, best_length))
            source += best_length
        else:
            tokens.append((source, -1, 1))
            source += 1

        for index in range(token_start, source):
            if index + 3 <= len(data):
                queue = positions[data[index : index + 3]]
                queue.append(index)
                while queue and source - queue[0] > 4096:
                    queue.popleft()

    def encoded_size(items: list[tuple[int, int, int]]) -> int:
        payload = sum(1 if match < 0 else 2 for _, match, _ in items)
        return payload + ((len(items) + 7) // 8)

    if target_size is not None:
        base_size = encoded_size(tokens)
        if base_size > target_size:
            raise ValueError(f"type-4 stream exceeds target: {base_size} > {target_size}")
        if base_size < target_size:
            # Turning a match into literals preserves the decoded pixels while
            # increasing both payload bytes and token-mask usage. Find a subset
            # whose combined increase makes the stream exactly target_size.
            states: dict[tuple[int, int], tuple[tuple[int, int], int] | None] = {(0, 0): None}
            found: tuple[int, int] | None = None
            base_tokens = len(tokens)
            base_payload = base_size - ((base_tokens + 7) // 8)
            for token_index, (_, match, length) in enumerate(tokens):
                if match < 0:
                    continue
                token_delta = length - 1
                payload_delta = length - 2
                for state in list(states):
                    next_state = (state[0] + token_delta, state[1] + payload_delta)
                    if next_state in states:
                        continue
                    final_size = (
                        base_payload
                        + next_state[1]
                        + ((base_tokens + next_state[0] + 7) // 8)
                    )
                    if final_size > target_size:
                        continue
                    states[next_state] = (state, token_index)
                    if final_size == target_size:
                        found = next_state
                        break
                if found is not None:
                    break
            if found is None:
                raise ValueError(f"cannot expand type-4 stream exactly to {target_size} bytes")
            literalized: set[int] = set()
            state = found
            while states[state] is not None:
                previous, token_index = states[state]  # type: ignore[misc]
                literalized.add(token_index)
                state = previous
            expanded: list[tuple[int, int, int]] = []
            for token_index, (start, match, length) in enumerate(tokens):
                if token_index in literalized:
                    expanded.extend((start + offset, -1, 1) for offset in range(length))
                else:
                    expanded.append((start, match, length))
            tokens = expanded

    output = bytearray()
    for group_start in range(0, len(tokens), 8):
        group = tokens[group_start : group_start + 8]
        mask = 0
        payload = bytearray()
        for bit, (start, match, length) in enumerate(group):
            if match < 0:
                mask |= 1 << bit
                payload.append(data[start])
            else:
                encoded_pos = ((match & 0xFFF) - 18) & 0xFFF
                payload.append(encoded_pos & 0xFF)
                payload.append(((encoded_pos >> 4) & 0xF0) | (length - 3))
        output.append(mask)
        output.extend(payload)
    if target_size is not None and len(output) != target_size:
        raise AssertionError((len(output), target_size))
    return bytes(output)


def decode_type08(data: bytes, output_size: int) -> bytes:
    """Adaptive Huffman/LZ decoder used by Arena type-8 IMG files."""
    def low_bit_count(index: int) -> int:
        if index < 32:
            return 3
        if index < 80:
            return 4
        if index < 144:
            return 5
        if index < 192:
            return 6
        if index < 240:
            return 7
        return 8

    def high_offset(index: int) -> int:
        if index < 32:
            return 0
        if index < 80:
            return 1 + ((index - 32) // 16)
        if index < 144:
            return 4 + ((index - 80) // 8)
        if index < 192:
            return 12 + ((index - 144) // 4)
        if index < 240:
            return 24 + ((index - 192) // 2)
        return 48 + (index - 240)

    history = bytearray([0x20] * 4096)
    history_pos = 0
    node_index = [((value >> 1) + 314) for value in range(626)]
    node_index += [0]
    node_index += list(range(314))
    node_tree = list(range(627, 941)) + [(value * 2) for value in range(313)]
    node_freq = [1] * 314 + [0] * 313
    source_freq = 0
    for index in range(314, 627):
        node_freq[index] = node_freq[source_freq] + node_freq[source_freq + 1]
        source_freq += 2

    source = 0
    bitmask = 0
    valid_bits = 0
    output = bytearray()

    def ensure_bits() -> None:
        nonlocal source, bitmask, valid_bits
        while valid_bits < 9:
            value = data[source] if source < len(data) else 0
            source += source < len(data)
            bitmask |= value << (8 - valid_bits)
            valid_bits += 8

    while len(output) < output_size:
        node = node_tree[626]
        while node < 627:
            ensure_bits()
            node = node_tree[node + ((bitmask >> 15) & 1)]
            bitmask = (bitmask << 1) & 0xFFFF
            valid_bits -= 1

        freq_index = node_index[node]
        while True:
            node_freq[freq_index] += 1
            frequency = node_freq[freq_index]
            next_index = freq_index + 1
            if next_index < len(node_freq) and node_freq[next_index] < frequency:
                while next_index < len(node_freq) and node_freq[next_index] < frequency:
                    next_index += 1
                next_index -= 1
                node_freq[freq_index], node_freq[next_index] = node_freq[next_index], frequency
                node_tree[freq_index], node_tree[next_index] = node_tree[next_index], node_tree[freq_index]
                mapped = node_tree[next_index]
                node_index[mapped] = next_index
                if mapped < 627:
                    node_index[mapped + 1] = next_index
                mapped = node_tree[freq_index]
                node_index[mapped] = freq_index
                if mapped < 627:
                    node_index[mapped + 1] = freq_index
                freq_index = next_index
            freq_index = node_index[freq_index]
            if freq_index == 0:
                break

        codeword = node - 627
        if codeword < 256:
            history[history_pos & 0xFFF] = codeword
            history_pos += 1
            output.append(codeword)
        else:
            ensure_bits()
            table_index = (bitmask >> 8) & 0xFF
            bitmask = (bitmask << 8) & 0xFFFF
            valid_bits -= 8
            offset_high = high_offset(table_index) << 6
            count = low_bit_count(table_index) - 2
            offset_low = table_index
            for _ in range(count):
                ensure_bits()
                offset_low = (offset_low << 1) | ((bitmask >> 15) & 1)
                bitmask = (bitmask << 1) & 0xFFFF
                valid_bits -= 1
            copy_pos = history_pos - (offset_high | (offset_low & 0x3F)) - 1
            copy_count = codeword - 256 + 3
            for _ in range(copy_count):
                if len(output) >= output_size:
                    break
                value = history[copy_pos & 0xFFF]
                copy_pos += 1
                history[history_pos & 0xFFF] = value
                history_pos += 1
                output.append(value)
    return bytes(output)


def decode(path: Path) -> ArenaIMG:
    data = path.read_bytes()
    if len(data) < HEADER.size:
        raise ValueError("IMG header is truncated")
    x, y, width, height, flags, packed_size = HEADER.unpack_from(data)
    payload = data[HEADER.size : HEADER.size + packed_size]
    compression = flags & 0xFF
    if compression == 0:
        pixels = payload[: width * height]
    elif compression == 4:
        pixels = decode_type04(payload, width * height)
    elif compression == 8:
        pixels = decode_type08(payload[2:], width * height)
    else:
        raise ValueError(f"unsupported IMG compression type {compression}")
    if len(pixels) != width * height:
        raise ValueError("IMG pixel data has the wrong length")
    if flags & 0x0100:
        palette = data[HEADER.size + packed_size : HEADER.size + packed_size + 768]
        if len(palette) != 768:
            raise ValueError("IMG palette is truncated")
    else:
        palette = None
    return ArenaIMG(x, y, width, height, palette, pixels)


def palette_8bit(palette: bytes) -> list[int]:
    return [min(value, 63) * 255 // 63 for value in palette]


def write_png(img: ArenaIMG, output: Path, external_palette: bytes | None = None) -> None:
    image = Image.frombytes("P", (img.width, img.height), img.pixels)
    if external_palette is not None:
        image.putpalette([component for color in external_palette for component in color])
    elif img.palette is not None:
        image.putpalette(palette_8bit(img.palette))
    else:
        image.putpalette([value for index in range(256) for value in (index, index, index)])
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def encode_uncompressed(img: ArenaIMG, pixels: bytes, output: Path) -> None:
    if len(pixels) != img.width * img.height:
        raise ValueError("replacement pixels have the wrong length")
    # Arena supports type 0 (raw) images. Preserve an embedded palette, if any.
    flags = 0x0100 if img.palette is not None else 0
    header = HEADER.pack(img.x, img.y, img.width, img.height, flags, len(pixels))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(header + pixels + (img.palette or b""))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--palette-flc", type=Path)
    args = parser.parse_args()
    img = decode(args.input)
    external_palette = None
    if args.palette_flc is not None:
        from arena_flc import decode as decode_flc
        external_palette = decode_flc(args.palette_flc).frames[-1].palette
    write_png(img, args.output, external_palette)
    print(f"{args.input.name}: {img.width}x{img.height} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
