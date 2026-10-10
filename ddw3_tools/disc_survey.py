"""Survey signatures in unlisted PS1 disc regions, without guessing asset identity."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .disc_files import Disc
from .disc_layout import analyze_layout


def survey_regions(source: Path, output: Path, *, max_hits: int = 200,
                   stride: int = 1) -> dict:
    """Sample each logical sector in unlisted ranges, looking for RLEN markers.

    Detection is byte-exact and scans sector payloads, not raw 2352 headers.
    A match is evidence of a signature, not proof of a valid compressed block.
    """
    if max_hits < 1 or stride < 1:
        raise ValueError("max_hits y stride deben ser positivos")
    layout = analyze_layout(source, output.with_name(output.stem + "_layout.json"))
    disc = Disc(source)
    ranges = []
    try:
        for region in layout["unlisted_ranges"]:
            start, end = region["start_lba"], region["end_lba_exclusive"]
            hits = []
            counts = Counter()
            scanned = 0
            failures = 0
            for lba in range(start, end, stride):
                try:
                    data = disc.sector(lba)
                except ValueError:
                    failures += 1
                    continue
                scanned += 1
                if not any(data):
                    counts["zero"] += 1
                else:
                    counts["nonzero"] += 1
                position = 0
                while True:
                    offset = data.find(b"RLEN", position)
                    if offset < 0:
                        break
                    counts["rlen"] += 1
                    if len(hits) < max_hits:
                        hits.append({"lba": lba, "sector_offset": offset,
                                     "prefix_hex": data[offset:offset + 32].hex()})
                    position = offset + 4
            ranges.append({
                "start_lba": start, "end_lba_exclusive": end,
                "sectors_scanned": scanned, "read_failures": failures,
                "zero_sectors": counts["zero"], "nonzero_sectors": counts["nonzero"],
                "rlen_occurrences": counts["rlen"], "rlen_hits": hits,
                "hits_truncated": counts["rlen"] > len(hits),
            })
    finally:
        disc.close()
    result = {
        "source": str(source), "stride": stride,
        "regions": ranges,
        "rlen_total": sum(x["rlen_occurrences"] for x in ranges),
        "note": "RLEN signature alone does not prove a decodable asset or compression format.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
