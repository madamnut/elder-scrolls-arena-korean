#!/usr/bin/env python3
"""Export actual-size original and coordinate-guide PNGs for CHARSTAT.IMG."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

from arena_img import decode


PRIMARY_NAMES = ("Strength", "Intelligence", "Willpower", "Agility", "Speed", "Endurance", "Personality", "Luck")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("charstat", type=Path)
    parser.add_argument("palette_col", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    source = decode(args.charstat)
    palette_data = args.palette_col.read_bytes()
    if len(palette_data) != 776:
        raise ValueError(f"expected 776-byte CHARSHT.COL, got {len(palette_data)}")
    palette = palette_data[8:]

    original = Image.frombytes("P", (source.width, source.height), source.pixels)
    original.putpalette(palette)
    guide = original.convert("RGB")
    draw = ImageDraw.Draw(guide)

    rows = []
    for index, name in enumerate(PRIMARY_NAMES):
        y = 52 + (index * 8)
        click = (7, y, 30, 8)
        value = (26, y)
        updown = (38, 48 + (index * 8), 8, 16)
        rows.append({"index": index, "name": name, "click": click, "value": value, "updown": updown})
        draw.rectangle((click[0], click[1], click[0] + click[2], click[1] + click[3]), outline=(0, 255, 0))
        draw.point(value, fill=(0, 255, 255))
        draw.rectangle((updown[0], updown[1], updown[0] + updown[2], updown[1] + updown[3]), outline=(255, 255, 0))

    done = (0, 170, 31, 17)
    draw.rectangle((done[0], done[1], done[0] + done[2], done[1] + done[3]), outline=(255, 0, 0))

    dynamic_values = {
        "Damage": (86, 52),
        "Spell Points": (86, 60),
        "Magic Defense": (86, 68),
        "To Hit": (86, 76),
        "Health Modifier": (86, 92),
        "Charisma Modifier": (86, 100),
        "Max Weight": (145, 52),
        "Defense": (145, 76),
        "Healing Modifier": (145, 92),
        "Health": (45, 127),
        "Stamina": (45, 135),
        "Gold": (45, 144),
        "Experience": (45, 158),
        "Level": (45, 167),
    }
    for x, y in dynamic_values.values():
        draw.line((x - 1, y, x + 1, y), fill=(255, 0, 255))
        draw.line((x, y - 1, x, y + 1), fill=(255, 0, 255))

    layout = {
        "canvas": [source.width, source.height],
        "coordinates": "top-left origin; rectangles use engine x, y, width, height and inclusive right/bottom checks",
        "primary_rows": rows,
        "done_click": done,
        "bonus_record": [11, 7, 100, 10],
        "dynamic_values": dynamic_values,
        "legend": {
            "green": "primary click rectangles",
            "yellow": "moving up/down control rectangle",
            "cyan": "primary numeric value origins",
            "magenta": "other dynamic numeric value origins",
            "red": "Done click rectangle",
        },
    }

    args.output.mkdir(parents=True, exist_ok=True)
    original.save(args.output / "CHARSTAT-original-171x200.png")
    guide.save(args.output / "CHARSTAT-coordinate-guide-171x200.png")
    (args.output / "CHARSTAT-layout.json").write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
