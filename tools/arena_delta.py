#!/usr/bin/env python3
"""Build and apply source-verified Arena Korean patch delta archives."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


FORMAT = "arena-korean-delta-v1"
DEFAULT_BLOCK_SIZE = 1024
HASH_BASE = 257
HASH_MASK = (1 << 64) - 1


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def window_hash(data: bytes, start: int, length: int) -> int:
    value = 0
    for byte in data[start : start + length]:
        value = ((value * HASH_BASE) + byte + 1) & HASH_MASK
    return value


def common_prefix(source: bytes, source_at: int, target: bytes, target_at: int) -> int:
    limit = min(len(source) - source_at, len(target) - target_at)
    matched = 0
    chunk_size = 65536
    while matched < limit:
        take = min(chunk_size, limit - matched)
        source_chunk = source[source_at + matched : source_at + matched + take]
        target_chunk = target[target_at + matched : target_at + matched + take]
        if source_chunk == target_chunk:
            matched += take
            continue
        for left, right in zip(source_chunk, target_chunk):
            if left != right:
                return matched
            matched += 1
        return matched
    return matched


def build_operations(source: bytes, target: bytes, block_size: int) -> list[dict[str, object]]:
    if block_size < 64:
        raise ValueError("block size must be at least 64 bytes")

    source_blocks: dict[int, list[int]] = {}
    for offset in range(0, len(source) - block_size + 1, block_size):
        fingerprint = window_hash(source, offset, block_size)
        offsets = source_blocks.setdefault(fingerprint, [])
        if len(offsets) < 32:
            offsets.append(offset)

    operations: list[dict[str, object]] = []
    literal_start = 0
    position = 0
    if len(target) < block_size:
        return [{"type": "data", "start": 0, "length": len(target)}]

    power = pow(HASH_BASE, block_size - 1, 1 << 64)
    fingerprint = window_hash(target, 0, block_size)
    while position + block_size <= len(target):
        best_offset = -1
        best_length = 0
        for candidate in source_blocks.get(fingerprint, ()):
            if source[candidate : candidate + block_size] != target[position : position + block_size]:
                continue
            length = common_prefix(source, candidate, target, position)
            if length > best_length:
                best_offset = candidate
                best_length = length

        if best_length >= block_size:
            if literal_start < position:
                operations.append(
                    {"type": "data", "start": literal_start, "length": position - literal_start}
                )
            operations.append(
                {"type": "copy", "sourceOffset": best_offset, "length": best_length}
            )
            position += best_length
            literal_start = position
            if position + block_size <= len(target):
                fingerprint = window_hash(target, position, block_size)
            continue

        outgoing = target[position] + 1
        position += 1
        if position + block_size <= len(target):
            incoming = target[position + block_size - 1] + 1
            fingerprint = (
                ((fingerprint - (outgoing * power)) & HASH_MASK) * HASH_BASE + incoming
            ) & HASH_MASK

    if literal_start < len(target):
        operations.append(
            {"type": "data", "start": literal_start, "length": len(target) - literal_start}
        )
    return operations


def build_delta(source_path: Path, target_path: Path, output_path: Path, block_size: int) -> None:
    source = source_path.read_bytes()
    target = target_path.read_bytes()
    operations = build_operations(source, target, block_size)

    manifest_operations: list[dict[str, object]] = []
    data_blobs: list[tuple[str, bytes]] = []
    for operation in operations:
        if operation["type"] == "copy":
            manifest_operations.append(operation)
            continue
        start = int(operation["start"])
        length = int(operation["length"])
        name = f"data/{len(data_blobs):05d}.bin"
        data_blobs.append((name, target[start : start + length]))
        manifest_operations.append({"type": "data", "file": name, "length": length})

    manifest = {
        "format": FORMAT,
        "blockSize": block_size,
        "sourceSize": len(source),
        "sourceSha256": sha256(source),
        "targetSize": len(target),
        "targetSha256": sha256(target),
        "operations": manifest_operations,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        with zipfile.ZipFile(
            temporary_output,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            archive.writestr(
                "delta.json",
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            )
            for name, data in data_blobs:
                archive.writestr(name, data)
        temporary_output.replace(output_path)
    finally:
        temporary_output.unlink(missing_ok=True)

    copy_bytes = sum(int(op["length"]) for op in manifest_operations if op["type"] == "copy")
    data_bytes = len(target) - copy_bytes
    print(f"wrote: {output_path}")
    print(f"operations: {len(manifest_operations)}")
    print(f"copy bytes: {copy_bytes}")
    print(f"data bytes: {data_bytes}")
    print(f"archive bytes: {output_path.stat().st_size}")


def apply_delta(source_path: Path, delta_path: Path, output_path: Path) -> None:
    source = source_path.read_bytes()
    with zipfile.ZipFile(delta_path) as archive:
        manifest = json.loads(archive.read("delta.json").decode("utf-8"))
        if manifest.get("format") != FORMAT:
            raise ValueError("unsupported delta format")
        if len(source) != manifest["sourceSize"] or sha256(source) != manifest["sourceSha256"]:
            raise ValueError("source file does not match the delta manifest")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as output:
            for operation in manifest["operations"]:
                if operation["type"] == "copy":
                    offset = int(operation["sourceOffset"])
                    length = int(operation["length"])
                    output.write(source[offset : offset + length])
                elif operation["type"] == "data":
                    data = archive.read(operation["file"])
                    if len(data) != int(operation["length"]):
                        raise ValueError("delta data length mismatch")
                    output.write(data)
                else:
                    raise ValueError(f"unknown operation: {operation['type']}")

    result = output_path.read_bytes()
    if len(result) != manifest["targetSize"] or sha256(result) != manifest["targetSha256"]:
        output_path.unlink(missing_ok=True)
        raise ValueError("delta output verification failed")
    print(f"wrote: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("source", type=Path)
    build.add_argument("target", type=Path)
    build.add_argument("output", type=Path)
    build.add_argument("--block-size", type=int, default=DEFAULT_BLOCK_SIZE)
    apply = subparsers.add_parser("apply")
    apply.add_argument("source", type=Path)
    apply.add_argument("delta", type=Path)
    apply.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.command == "build":
        build_delta(args.source, args.target, args.output, args.block_size)
    else:
        apply_delta(args.source, args.delta, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
