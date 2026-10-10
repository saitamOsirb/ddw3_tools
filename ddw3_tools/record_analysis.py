"""Evidence-only analysis of 12-byte resource records as six little-endian u16s.

Some values appear to describe regions of TIM textures. The tool measures
relationships to TIM dimensions but does not label undocumented fields as UV,
model geometry, animation, or authoritative texture coordinates.
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

from .resource_inspector import inspect_payload


def analyze_records(source: Path, output: Path, *, max_files: int = 10000,
                    max_examples: int = 12) -> dict:
    if max_files < 1 or max_examples < 1:
        raise ValueError("Los limites deben ser positivos")
    if not source.is_dir():
        raise ValueError(f"No existe carpeta: {source}")
    stats = Counter()
    slot_values = [Counter() for _ in range(6)]
    examples = []
    by_count = Counter()
    for path in sorted(source.rglob("decoded.bin"))[:max_files]:
        stats["files_scanned"] += 1
        try:
            data = path.read_bytes()
            if len(data) > 32 * 1024 * 1024:
                stats["oversize"] += 1
                continue
            info = inspect_payload(data)
            if not info["tim_images"]:
                stats["missing_tim"] += 1
                continue
            tim = info["tim_images"][0]
            n = tim["offset"]
            if n == 0:
                stats["no_header"] += 1
                continue
            if n < 16 or (n - 16) % 12 or struct.unpack_from("<I", data)[0] != n:
                stats["unsupported_header"] += 1
                continue
            stats["valid_headers"] += 1
            count = (n - 16) // 12
            by_count[count] += 1
            records = [list(struct.unpack_from("<6H", data, 16 + i * 12))
                       for i in range(count)]
            for row in records:
                for slot, value in enumerate(row):
                    slot_values[slot][value] += 1
            # A falsifiable, explicitly positional relationship, not a semantic claim:
            # last record slot0 + slot2 equals pixel width, and slot3 <= height.
            last = records[-1]
            width_match = last[0] + last[2] == tim["width"]
            height_fits = last[3] <= tim["height"]
            if width_match:
                stats["last_record_width_match"] += 1
            if height_fits:
                stats["last_record_height_fits"] += 1
            if width_match and height_fits:
                stats["both_conditions"] += 1
            if len(examples) < max_examples:
                examples.append({
                    "file": path.relative_to(source).as_posix(),
                    "lba_folder": path.parent.name,
                    "header_bytes": n,
                    "tim_dimensions": [tim["width"], tim["height"]],
                    "tim_bpp": tim["bpp"],
                    "fixed_u16le": list(struct.unpack_from("<8H", data, 0)),
                    "records_u16le": records,
                    "last_record_width_sum": last[0] + last[2],
                    "width_match": width_match,
                    "height_fits": height_fits,
                })
        except (ValueError, OSError, struct.error):
            stats["errors"] += 1
    result = {
        "source": str(source),
        "counts": dict(stats),
        "record_count_distribution": [
            {"records": k, "files": v} for k, v in sorted(by_count.items())
        ],
        "u16_slot_top_values": [
            [{"value": k, "count": v} for k, v in c.most_common(15)]
            for c in slot_values
        ],
        "examples": examples,
        "hypothesis": "12-byte records may encode six u16 values; last record (u16[0] + u16[2]) may equal TIM pixel width",
        "warning": "An arithmetic match is not proof of rectangle, UV, model or animation semantics.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
