"""Inspect decoded RLEN payloads without assuming that TIM textures are sprites.

The inspector reports validated TIM blocks, palette/VRAM metadata and unknown
bytes. It does NOT claim to parse game geometry or animations.
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

from .sprites import MAGIC, parse_tim


def inspect_payload(data: bytes, *, max_tims: int = 256) -> dict:
    if max_tims < 1:
        raise ValueError("max_tims debe ser positivo")
    images = []
    cursor = 0
    while len(images) < max_tims:
        offset = data.find(MAGIC, cursor)
        if offset < 0:
            break
        tim = parse_tim(data, offset)
        if tim is None:
            cursor = offset + 1
            continue
        flags = struct.unpack_from("<I", data, offset + 4)[0]
        images.append({
            "offset": offset,
            "end_offset": tim["end"],
            "length": tim["end"] - offset,
            "width": tim["width"],
            "height": tim["height"],
            "bpp": tim["bpp"],
            "flags": flags,
            "has_embedded_clut": bool(flags & 8),
            "palette_count": len(tim["palettes"]),
            "image_vram_xy": tim["image_position"],
            "clut_vram_xy": tim["clut_position"],
            "pixel_bytes": len(tim["pixels"]),
            "classification": "tim_texture_not_assembled_sprite",
        })
        cursor = tim["end"]
    spans = []
    end = 0
    for tim in images:
        if tim["offset"] > end:
            spans.append({"start": end, "end": tim["offset"],
                          "bytes": tim["offset"] - end})
        end = tim["end_offset"]
    if end < len(data):
        spans.append({"start": end, "end": len(data), "bytes": len(data) - end})
    kinds = Counter(str(im["bpp"]) + "bpp" for im in images)
    if not images:
        classification = "unclassified_binary"
    elif sum(x["bytes"] for x in spans) == 0:
        classification = "tim_only"
    else:
        classification = "tim_and_unclassified_bytes"
    return {
        "size_bytes": len(data),
        "classification": classification,
        "tim_count": len(images),
        "tim_limit_reached": len(images) == max_tims,
        "tim_bpp_counts": dict(sorted(kinds.items())),
        "tim_images": images,
        "unclassified_spans": spans,
        "unclassified_bytes": sum(x["bytes"] for x in spans),
        "geometry_detected": False,
        "animation_detected": False,
        "detection_note": (
            "Geometry and animation formats are not implemented; false means "
            "not detected by this tool, not proof of absence."
        ),
    }


def inspect_extractions(source: Path, output: Path, *, max_files: int = 10000,
                        max_file_bytes: int = 32 * 1024 * 1024) -> dict:
    if max_files < 1 or max_file_bytes < 1:
        raise ValueError("Los limites deben ser positivos")
    if source.is_file():
        files = [source]
        root = source.parent
    elif source.is_dir():
        files = sorted(source.rglob("decoded.bin"))
        root = source
    else:
        raise ValueError(f"No existe la entrada: {source}")
    records = []
    summary = Counter()
    for path in files[:max_files]:
        record = {"file": path.relative_to(root).as_posix()}
        try:
            size = path.stat().st_size
            if size > max_file_bytes:
                raise ValueError(f"Archivo excede max_file_bytes: {size}")
            record.update(inspect_payload(path.read_bytes()))
            manifest = path.with_name("rlen_manifest.json")
            if manifest.is_file():
                meta = json.loads(manifest.read_text(encoding="utf-8"))
                record["origin"] = {
                    field: meta[field] for field in ("lba", "sector_offset", "compressed_bytes")
                    if field in meta
                }
            summary[record["classification"]] += 1
            summary["tim_count"] += record["tim_count"]
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            record["error"] = str(exc)
            summary["errors"] += 1
        records.append(record)
    result = {
        "input": str(source), "file_count": len(records),
        "available_file_count": len(files), "files_truncated": len(files) > max_files,
        "summary": dict(summary), "resources": records,
        "note": "TIM textures are not assembled sprites; model and animation parsing remains future work.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
