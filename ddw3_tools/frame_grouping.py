"""Conservative grouping of nearby 4bpp TIM connected components.

Spatial proximity is only a hypothesis. We keep original pixels and full
provenance, and never label grouped regions as verified animation frames.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .frame_candidates import connected_regions
from .sprites import parse_tim, rgba, write_png


def _gap(a: dict, b: dict) -> tuple[int, int]:
    dx = max(0, a["x"] - (b["x"] + b["w"]),
             b["x"] - (a["x"] + a["w"]))
    dy = max(0, a["y"] - (b["y"] + b["h"]),
             b["y"] - (a["y"] + a["h"]))
    return dx, dy


def group_regions(regions: list[dict], *, gap: int = 3,
                  max_width: int = 64, max_height: int = 64) -> list[dict]:
    if gap < 0 or max_width < 1 or max_height < 1:
        raise ValueError("Parametros de agrupacion invalidos")
    groups = [{
        "members": [i], "x": r["x"], "y": r["y"],
        "w": r["w"], "h": r["h"],
    } for i, r in enumerate(regions)]
    # Deterministic nearest-first merges. A maximum resulting bounding box
    # prevents distant neighbors becoming connected via chains.
    while True:
        best = None
        for i, a in enumerate(groups):
            for j in range(i + 1, len(groups)):
                b = groups[j]
                dx, dy = _gap(a, b)
                if dx > gap or dy > gap:
                    continue
                x = min(a["x"], b["x"])
                y = min(a["y"], b["y"])
                x2 = max(a["x"] + a["w"], b["x"] + b["w"])
                y2 = max(a["y"] + a["h"], b["y"] + b["h"])
                if x2 - x > max_width or y2 - y > max_height:
                    continue
                key = (dx + dy, max(dx, dy), i, j)
                if best is None or key < best[0]:
                    best = (key, i, j, x, y, x2 - x, y2 - y)
        if best is None:
            break
        _, i, j, x, y, w, h = best
        members = sorted(groups[i]["members"] + groups[j]["members"])
        groups[i] = {"members": members, "x": x, "y": y, "w": w, "h": h}
        groups.pop(j)
    return sorted(groups, key=lambda g: (g["y"], g["x"], g["members"][0]))


def _crop(pixels: bytes, width: int, group: dict) -> bytes:
    x, y, w, h = (group[k] for k in ("x", "y", "w", "h"))
    return b"".join(
        pixels[((y + row) * width + x) * 4:
               ((y + row) * width + x + w) * 4]
        for row in range(h)
    )


def export_grouped_candidates(source: Path, output: Path, *, contains: str,
                              gap: int = 3, max_width: int = 64,
                              max_height: int = 64, min_pixels: int = 12,
                              max_regions: int = 96, max_palettes: int = 16) -> dict:
    if not contains.strip() or min(max_width, max_height, min_pixels, max_regions, max_palettes) < 1 or gap < 0:
        raise ValueError("Parametros invalidos")
    if not source.is_dir():
        raise ValueError(f"No existe carpeta: {source}")
    matching = sorted(p for p in source.rglob("decoded.bin") if contains in p.parent.name)
    if not matching:
        raise ValueError(f"No se encontro atlas para: {contains}")
    if len(matching) != 1:
        raise ValueError("El filtro debe identificar exactamente un atlas")
    path = matching[0]
    data = path.read_bytes()
    if len(data) > 32 * 1024 * 1024:
        raise ValueError("Atlas demasiado grande")
    tim = parse_tim(data, 0)
    if tim is None or tim["end"] != len(data) or tim["bpp"] != 4 or not tim["palettes"]:
        raise ValueError("Se necesita un TIM 4bpp completo con CLUT")
    output.mkdir(parents=True, exist_ok=True)
    results = []
    counts = Counter()
    area = tim["width"] * tim["height"]
    for palette_index in range(min(len(tim["palettes"]), max_palettes)):
        pixels = rgba(tim, palette_index)
        coverage = sum(pixels[i] != 0 for i in range(3, len(pixels), 4)) / area
        record = {"palette": palette_index, "coverage": coverage, "groups": []}
        if coverage == 0:
            record["status"] = "empty"
        elif coverage >= .98:
            record["status"] = "nearly_opaque"
        else:
            record["status"] = "partial"
            parts = connected_regions(pixels, tim["width"], tim["height"],
                                      min_pixels=min_pixels, max_regions=max_regions)
            groups = group_regions(parts, gap=gap, max_width=max_width,
                                   max_height=max_height)
            record["component_count"] = len(parts)
            record["group_count"] = len(groups)
            for index, group in enumerate(groups):
                name = f"{path.parent.name}_pal_{palette_index:03d}_group_{index:03d}.png"
                write_png(output / name, group["w"], group["h"],
                          _crop(pixels, tim["width"], group))
                record["groups"].append({
                    **group, "png": name,
                    "components": [parts[i] for i in group["members"]],
                })
            counts["components"] += len(parts)
            counts["groups"] += len(groups)
        counts[record["status"]] += 1
        results.append(record)
    origin = {}
    manifest = path.with_name("rlen_manifest.json")
    if manifest.is_file():
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        origin = {k: meta[k] for k in ("lba", "sector_offset") if k in meta}
    report = {
        "source": path.relative_to(source).as_posix(),
        "origin": origin,
        "dimensions": [tim["width"], tim["height"]],
        "parameters": {"gap": gap, "max_width": max_width, "max_height": max_height,
                       "min_pixels": min_pixels, "max_regions": max_regions},
        "counts": dict(counts), "palettes": results,
        "warning": "Proximity groups are visual proposals, NOT verified game frames or animations.",
    }
    (output / "grouped_candidates.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    return report
