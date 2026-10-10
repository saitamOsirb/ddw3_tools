"""Read-only neighborhood evidence around a known RLEN signature on a PS1 disc.

Reports adjacent sector bytes and nearby RLEN markers; it does not infer
animation layouts, compressed stream ends, or asset relationships.
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

from .disc_files import Disc, SECTOR


def inspect_rlen_neighborhood(source: Path, output: Path, *, lba: int,
                              offset: int, radius: int = 8,
                              sample_bytes: int = 64) -> dict:
    if lba < 0 or not 0 <= offset < SECTOR or not 0 <= radius <= 128 or not 8 <= sample_bytes <= 256:
        raise ValueError("LBA, offset, radio o muestra fuera de rango")
    disc = Disc(source)
    try:
        max_lba = disc.size // (2352 if disc.raw else SECTOR) - 1
        if lba > max_lba:
            raise ValueError("LBA fuera del disco")
        first, last = max(0, lba - radius), min(max_lba, lba + radius)
        sectors = []
        signatures = []
        for current in range(first, last + 1):
            try:
                data = disc.sector(current)
            except ValueError as exc:
                sectors.append({"lba": current, "readable": False, "error": str(exc)})
                continue
            offsets = []
            cursor = 0
            while True:
                pos = data.find(b"RLEN", cursor)
                if pos < 0:
                    break
                offsets.append(pos)
                # Declared decoded size is data, not verified validity.
                header = data[pos + 4:pos + 8]
                declared = struct.unpack("<I", header)[0] if len(header) == 4 else None
                signatures.append({"lba": current, "offset": pos,
                                   "declared_decoded_bytes": declared,
                                   "header_complete_in_sector": len(header) == 4})
                cursor = pos + 4
            counts = Counter(data)
            sectors.append({
                "lba": current, "readable": True,
                "nonzero_bytes": SECTOR - counts[0],
                "distinct_byte_values": len(counts),
                "prefix_hex": data[:sample_bytes].hex(),
                "rlen_offsets": offsets,
            })
        # Capture a bounded byte window preceding the target marker, without
        # guessing where the previous compressed stream ended.
        before = b""
        preceding_lba = max(0, lba - 1)
        for current in range(preceding_lba, lba + 1):
            before += disc.sector(current)
        target_position = (lba - preceding_lba) * SECTOR + offset
        target_header = before[target_position:target_position + 8]
        if len(target_header) < 8:
            target_header += disc.sector(lba + 1)[:8 - len(target_header)]
        if target_header[:4] != b"RLEN":
            raise ValueError("No hay firma RLEN en la posicion solicitada")
        result = {
            "disc": str(source), "target": {"lba": lba, "offset": offset,
                "declared_decoded_bytes": struct.unpack_from("<I", target_header, 4)[0],
                "preceding_bytes_hex": before[max(0, target_position - sample_bytes):target_position].hex(),
                "header_hex": target_header.hex()},
            "range_lba_inclusive": [first, last],
            "sectors": sectors, "signatures": signatures,
            "notes": [
                "Nearby RLEN markers and byte distributions do not prove shared asset identity.",
                "The preceding bytes may be compressed content of another resource, not an animation table.",
                "Decoded length in an RLEN header is not its compressed length.",
            ],
        }
    finally:
        disc.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
