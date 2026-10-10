"""Evidence-based analysis of a possible 16-byte header plus 12-byte records.

No record fields are assigned game-specific meanings until validated.
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

from .resource_inspector import inspect_payload


def inspect_header_structure(source: Path, output: Path, *,
                             max_files: int = 10000,
                             max_examples: int = 12) -> dict:
    if max_files < 1 or max_examples < 1:
        raise ValueError("Los limites deben ser positivos")
    if not source.is_dir():
        raise ValueError(f"No existe carpeta: {source}")
    counters = Counter()
    second_words = Counter()
    first_mismatch = Counter()
    fixed_words = [Counter() for _ in range(4)]
    entry_words = [Counter() for _ in range(3)]
    examples = []
    mismatches = []
    for file in sorted(source.rglob("decoded.bin"))[:max_files]:
        counters["files"] += 1
        try:
            data = file.read_bytes()
            if len(data) > 32 * 1024 * 1024:
                raise ValueError("Archivo demasiado grande")
            report = inspect_payload(data)
            if not report["tim_images"]:
                counters["no_valid_tim"] += 1
                continue
            size = report["tim_images"][0]["offset"]
            if not size:
                counters["no_prefix"] += 1
                continue
            counters["with_prefix"] += 1
            prefix = data[:size]
            if size < 16 or (size - 16) % 12:
                counters["shape_mismatch"] += 1
                if len(mismatches) < max_examples:
                    mismatches.append({"file": file.relative_to(source).as_posix(),
                                       "bytes": size, "reason": "shape"})
                continue
            counters["shape_match"] += 1
            first = struct.unpack_from("<I", prefix, 0)[0]
            if first != size:
                counters["length_mismatch"] += 1
                first_mismatch[first] += 1
                if len(mismatches) < max_examples:
                    mismatches.append({"file": file.relative_to(source).as_posix(),
                                       "bytes": size, "first_u32": first,
                                       "reason": "length"})
            else:
                counters["length_match"] += 1
            words = list(struct.unpack_from("<4I", prefix, 0))
            for pos, value in enumerate(words):
                fixed_words[pos][value] += 1
            second_words[words[1]] += 1
            entries = []
            for i in range((size - 16) // 12):
                row = list(struct.unpack_from("<3I", prefix, 16 + i * 12))
                entries.append(row)
                for j, value in enumerate(row):
                    entry_words[j][value] += 1
            counters["records"] += len(entries)
            if len(examples) < max_examples:
                examples.append({
                    "file": file.relative_to(source).as_posix(),
                    "header_bytes": size, "fixed_words_u32le": words,
                    "record_count_if_12_bytes": len(entries),
                    "records_u32le": entries,
                    "tim_bpp": report["tim_images"][0]["bpp"],
                    "tim_dimensions": [
                        report["tim_images"][0]["width"],
                        report["tim_images"][0]["height"],
                    ],
                })
        except (OSError, ValueError, struct.error) as exc:
            counters["errors"] += 1
            if len(mismatches) < max_examples:
                mismatches.append({"file": file.relative_to(source).as_posix(),
                                   "reason": "error", "detail": str(exc)})
    def most_common(counter: Counter, count: int = 12) -> list[dict]:
        return [{"value": value, "count": n} for value, n in counter.most_common(count)]
    result = {
        "source": str(source),
        "counts": dict(counters),
        "hypothesis": "16 bytes fixed + 12 bytes per record",
        "first_word_equals_header_length": counters["length_match"],
        "first_word_mismatch_values": most_common(first_mismatch),
        "second_word_distribution": most_common(second_words, 30),
        "fixed_u32_distributions": [most_common(c) for c in fixed_words],
        "record_u32_distributions": [most_common(c) for c in entry_words],
        "examples": examples,
        "mismatch_examples": mismatches,
        "note": ("12-byte records are a shape hypothesis, not decoded game structures. "
                 "No geometry, UV coordinates, animation or sprite assembly is inferred."),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
