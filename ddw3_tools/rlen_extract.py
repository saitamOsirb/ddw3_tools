"""Decode RLEN blocks at exact PS1 disc sector and byte offsets."""
from __future__ import annotations

import json
import struct
from pathlib import Path

from .disc_files import Disc
from .rlen import decode_rlen
from .sprites import parse_tim, rgba, write_png


def extract_rlen_at(source: Path, output: Path, *, lba: int, offset: int,
                    max_output: int = 32 * 1024 * 1024,
                    max_input: int = 32 * 1024 * 1024) -> dict:
    if lba < 0 or not 0 <= offset < 2048:
        raise ValueError("LBA u offset fuera de rango")
    disc = Disc(source)
    try:
        header = disc.sector(lba)[offset:offset + 8]
        if len(header) < 8:
            header += disc.sector(lba + 1)[:8 - len(header)]
        if header[:4] != b"RLEN":
            raise ValueError("No existe cabecera RLEN en la posicion indicada")
        expected = struct.unpack_from("<I", header, 4)[0]
        if expected > max_output:
            raise ValueError("Tamano descomprimido excede max_output")
        # Read in bounded increments until a complete RLEN stream decodes.
        compressed = bytearray()
        last_error = None
        max_sectors = (offset + max_input + 2047) // 2048
        for sector_index in range(max_sectors):
            try:
                compressed.extend(disc.sector(lba + sector_index))
            except ValueError as exc:
                raise ValueError(f"Sector RLEN no legible: {exc}") from exc
            if len(compressed) - offset > max_input:
                break
            try:
                decoded, consumed = decode_rlen(compressed[offset:], max_output=max_output)
                break
            except ValueError as exc:
                last_error = exc
                if "truncado" in str(exc) or "fuera de limites" in str(exc):
                    continue
                raise
        else:
            raise ValueError(f"No se pudo decodificar RLEN: {last_error}")
        output.mkdir(parents=True, exist_ok=True)
        (output / "decoded.bin").write_bytes(decoded)
        tim = parse_tim(decoded, 0)
        previews = []
        if tim is not None and tim["end"] == len(decoded):
            for palette in range(max(1, len(tim["palettes"]))):
                name = f"decoded_pal_{palette:03d}.png"
                write_png(output / name, tim["width"], tim["height"], rgba(tim, palette))
                previews.append(name)
        result = {"source": str(source), "lba": lba, "sector_offset": offset,
                  "decompressed_bytes": len(decoded), "compressed_bytes": consumed,
                  "tim_at_start": bool(previews), "previews": previews}
        (output / "rlen_manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result
    finally:
        disc.close()
