"""Analyze bytes preceding validated TIMs without assigning undocumented semantics."""
from __future__ import annotations

import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

from .resource_inspector import inspect_payload


def inspect_prefixes(source: Path, output: Path, *,
                     max_files: int = 10000, max_examples: int = 5,
                     max_prefix: int = 256) -> dict:
    if min(max_files, max_examples, max_prefix) < 1:
        raise ValueError("Los limites deben ser positivos")
    if not source.is_dir():
        raise ValueError(f"No existe carpeta: {source}")
    lengths = Counter()
    patterns = Counter()
    samples = defaultdict(list)
    trailing = Counter()
    failed = 0
    scanned = 0
    no_prefix = 0
    for path in sorted(source.rglob("decoded.bin"))[:max_files]:
        scanned += 1
        try:
            data = path.read_bytes()
            if len(data) > 32 * 1024 * 1024:
                raise ValueError("Archivo demasiado grande")
            info = inspect_payload(data)
            if not info["tim_images"]:
                failed += 1
                continue
            first = info["tim_images"][0]
            prefix_size = first["offset"]
            end = info["tim_images"][-1]["end_offset"]
            trailing[len(data) - end] += 1
            if not prefix_size:
                no_prefix += 1
                continue
            lengths[prefix_size] += 1
            prefix = data[:prefix_size]
            # Prefix families: size + first 8 bytes, preserving evidence instead of guessing fields.
            key = (prefix_size, prefix[:8].hex())
            patterns[key] += 1
            if len(samples[key]) < max_examples:
                head = prefix[:max_prefix]
                samples[key].append({
                    "file": path.relative_to(source).as_posix(),
                    "prefix_hex": head.hex(),
                    "prefix_truncated": len(prefix) > len(head),
                    "u32le": list(struct.unpack("<" + "I" * (len(head) // 4),
                                                 head[:len(head) // 4 * 4])),
                    "tim_offset": prefix_size,
                    "tim_bpp": first["bpp"],
                    "tim_dimensions": [first["width"], first["height"]],
                    "tim_vram_xy": first["image_vram_xy"],
                })
        except (ValueError, OSError, struct.error):
            failed += 1
    families = [{
        "prefix_bytes": size, "first_8_hex": sig, "count": count,
        "examples": samples[(size, sig)],
    } for (size, sig), count in patterns.most_common()]
    result = {
        "source": str(source), "files_scanned": scanned,
        "files_without_valid_tim": failed, "files_without_prefix": no_prefix,
        "prefix_lengths": [{"bytes": size, "count": count}
                           for size, count in lengths.most_common()],
        "trailing_lengths": [{"bytes": size, "count": count}
                             for size, count in trailing.most_common()],
        "families": families,
        "note": "Prefix values are uninterpreted; no geometry or animation detection is claimed.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
