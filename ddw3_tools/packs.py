"""Read DW3 offset-table PACK containers, based on markisha64/dmw3-util.

The first u32 is the offset-table byte length. Offsets refer to the
beginning of the packed file. Zero offsets denote empty entries.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from .sprites import parse_tim, rgba, write_png


def unpack(data: bytes, *, max_entries: int = 65536) -> list[dict]:
    if len(data) < 4:
        raise ValueError("PACK demasiado corto")
    first = struct.unpack_from("<I", data)[0]
    if first == 0:
        if len(data) != 4:
            raise ValueError("PACK vacio con datos sobrantes")
        return []
    if first % 4 or first > len(data) or first // 4 > max_entries:
        raise ValueError("Tabla de offsets PACK invalida")
    count = first // 4
    offsets = struct.unpack_from(f"<{count}I", data)
    entries = []
    for i, start in enumerate(offsets):
        if start == 0:
            entries.append({"index": i, "offset": None, "size": 0, "data": b""})
            continue
        if start < first or start > len(data):
            raise ValueError(f"Offset fuera del contenedor en entrada {i}")
        # Mirrors dmw3_pack: an entry extends to the next greater offset.
        end = next((x for x in offsets[i + 1:] if x > start), len(data))
        if end > len(data):
            raise ValueError(f"Fin fuera del contenedor en entrada {i}")
        entries.append({"index": i, "offset": start, "size": end - start,
                        "data": data[start:end]})
    return entries


def extract_pack(source: Path, output: Path, *, max_entries: int = 65536) -> dict:
    """Export PACK members losslessly; decode TIM only at member offset zero."""
    entries = unpack(source.read_bytes(), max_entries=max_entries)
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"source": str(source), "format": "dmw3_pack",
                "reference": "https://github.com/markisha64/dmw3-util/blob/main/pack/src/lib.rs",
                "entries": []}
    for entry in entries:
        index = entry["index"]
        record = {"index": index, "offset": entry["offset"], "size": entry["size"],
                  "file": None, "tim": None}
        if entry["data"]:
            name = f"part_{index:04d}.bin"
            (output / name).write_bytes(entry["data"])
            record["file"] = name
            tim = parse_tim(entry["data"], 0)
            if tim is not None and tim["end"] == len(entry["data"]):
                images = []
                for p in range(max(1, len(tim["palettes"]))):
                    png = f"part_{index:04d}_pal_{p:03d}.png"
                    write_png(output / png, tim["width"], tim["height"], rgba(tim, p))
                    images.append(png)
                record["tim"] = {
                    "width": tim["width"], "height": tim["height"], "bpp": tim["bpp"],
                    "image_position": tim["image_position"],
                    "clut_position": tim["clut_position"], "images": images}
        manifest["entries"].append(record)
    (output / "pack_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
