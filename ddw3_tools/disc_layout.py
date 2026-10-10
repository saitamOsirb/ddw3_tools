"""Report ISO9660 extents and unlisted sector ranges on PS1 CD images.

Physical gaps are *not* automatically game assets. This command provides
measurements needed to investigate non-ISO game-specific storage.
"""
from __future__ import annotations

import json
from pathlib import Path

from .disc_files import Disc, list_files


def analyze_layout(source: Path, output: Path, *, sample_bytes: int = 32) -> dict:
    if not 1 <= sample_bytes <= 2048:
        raise ValueError("sample_bytes fuera de rango")
    disc = Disc(source)
    try:
        files = list_files(disc)
        total = disc.size // (2352 if disc.raw else 2048)
        intervals = [(0, 17, "system_area_and_primary_descriptor")]
        for item in files:
            count = (item["size"] + 2047) // 2048
            if count:
                intervals.append((item["lba"], item["lba"] + count, item["path"]))
        intervals.sort()
        covered = []
        for start, end, label in intervals:
            if start >= total:
                continue
            covered.append((max(0, start), min(total, end), label))
        gaps = []
        cursor = 0
        for start, end, _ in covered:
            if start > cursor:
                gaps.append((cursor, start))
            cursor = max(cursor, end)
        if cursor < total:
            gaps.append((cursor, total))
        ranges = []
        for start, end in gaps:
            samples = []
            for lba in sorted({start, start + (end - start) // 2, end - 1}):
                try:
                    block = disc.sector(lba)
                    samples.append({
                        "lba": lba, "prefix_hex": block[:sample_bytes].hex(),
                        "zero_sector": not any(block),
                    })
                except ValueError as exc:
                    samples.append({"lba": lba, "error": str(exc)})
            ranges.append({
                "start_lba": start, "end_lba_exclusive": end,
                "sector_count": end - start,
                "logical_bytes": (end - start) * 2048,
                "samples": samples,
            })
        result = {
            "source": str(source),
            "layout": "raw2352" if disc.raw else "iso2048",
            "total_sectors": total,
            "listed_files": files,
            "known_file_extents": [
                {"path": label, "start_lba": start, "end_lba_exclusive": end}
                for start, end, label in covered
            ],
            "unlisted_ranges": ranges,
            "note": "Unlisted ranges may include filesystem structures, padding, XA streams, or game assets; no identity is inferred.",
        }
    finally:
        disc.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
