"""Streaming sector-aligned candidate PACK search inside ISO9660 files.

This is a diagnostic, not a guarantee of game resource identity. Only inspect
sector boundaries by default; avoid reading a whole PS1 disc into memory.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from .disc_files import Disc, list_files
from .disc_packs import plausible_pack


def scan_embedded_packs(source: Path, output: Path, *,
                        max_sectors: int = 400000,
                        max_hits: int = 1000,
                        max_header_bytes: int = 262144) -> dict:
    disc = Disc(source)
    hits = []
    sectors_checked = 0
    try:
        files = list_files(disc)
        for file in files:
            size = file["size"]
            for relative in range(0, size, 2048):
                if sectors_checked >= max_sectors or len(hits) >= max_hits:
                    break
                sectors_checked += 1
                remaining = size - relative
                if remaining < 8:
                    continue
                lba = file["lba"] + relative // 2048
                try:
                    head = disc.sector(lba)
                    first = struct.unpack_from("<I", head)[0]
                    if not (4 <= first <= min(max_header_bytes, remaining)
                            and first % 4 == 0):
                        continue
                    header = disc.extent(lba, first)
                    if not plausible_pack(header, remaining):
                        continue
                except ValueError:
                    continue
                hits.append({
                    "path": file["path"], "file_offset": relative,
                    "lba": lba, "candidate_entries": first // 4,
                    "remaining_bytes": remaining,
                    "warning": "Candidate header only; PACK end is not verified",
                })
            if sectors_checked >= max_sectors or len(hits) >= max_hits:
                break
        result = {
            "source": str(source), "files_checked": len(files),
            "sectors_checked": sectors_checked,
            "candidates": len(hits), "hits": hits,
            "truncated": sectors_checked >= max_sectors or len(hits) >= max_hits,
            "scan_alignment": 2048,
            "note": "Only ISO9660 file contents and sector boundaries scanned.",
        }
    finally:
        disc.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
