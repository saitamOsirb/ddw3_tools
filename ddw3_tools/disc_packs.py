"""Identify likely DW3 PACK files in an ISO9660 filesystem."""
from __future__ import annotations

import json
import struct
from pathlib import Path

from .disc_files import Disc, list_files
from .packs import extract_pack


def plausible_pack(data: bytes, size: int, *, max_entries: int = 65536) -> bool:
    if len(data) < 8 or size < 8:
        return False
    first = struct.unpack_from("<I", data)[0]
    if first < 4 or first % 4 or first > size or first // 4 > max_entries:
        return False
    if len(data) < first:
        return False
    offsets = struct.unpack_from(f"<{first // 4}I", data)
    nonzero = [x for x in offsets if x]
    return bool(nonzero) and all(first <= x < size for x in nonzero)


def scan_disc_packs(source: Path, output: Path, *, max_files: int = 100000,
                    extract: bool = False, max_extract: int = 50) -> dict:
    disc = Disc(source)
    matches = []
    try:
        files = list_files(disc, max_files=max_files)
        for file in files:
            if file["size"] < 8:
                continue
            try:
                first_sector = disc.extent(file["lba"], min(file["size"], 2048))
                if len(first_sector) < 4:
                    continue
                first = struct.unpack_from("<I", first_sector)[0]
                if first < 4 or first % 4 or first > min(file["size"], 65536 * 4):
                    continue
                header = disc.extent(file["lba"], first)
                if not plausible_pack(header, file["size"]):
                    continue
            except ValueError:
                continue
            match = dict(file)
            match["entries"] = first // 4
            matches.append(match)
            if extract and len(matches) <= max_extract:
                # A detected candidate is not proof that this is a DW3 PACK.
                # Preserve its original bytes for later verification.
                target = output / "packs" / f"{len(matches):04d}"
                target.mkdir(parents=True, exist_ok=True)
                packed = target / "original.bin"
                packed.write_bytes(disc.extent(file["lba"], file["size"]))
                try:
                    extract_pack(packed, target / "members")
                    match["extracted"] = True
                except ValueError as exc:
                    match["extracted"] = False
                    match["error"] = str(exc)
    finally:
        disc.close()
    result = {"source": str(source), "files_checked": len(files),
              "pack_candidates": len(matches), "matches": matches,
              "warning": "Heuristic matches require validation; not all offset tables are DW3 PACK."}
    output.mkdir(parents=True, exist_ok=True)
    (output / "disc_packs.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
