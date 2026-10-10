"""Export spatially aligned 4bpp TIM candidate crops across usable CLUT palettes.

Coordinates are computed once from a union alpha mask. These are proposals,
not identified sprites, animation sequences, or Godot SpriteFrames resources.
"""
from __future__ import annotations

import json
from pathlib import Path

from .frame_candidates import connected_regions
from .frame_grouping import group_regions, _crop
from .sprites import parse_tim, rgba, write_png


def export_aligned_candidates(source: Path, output: Path, *, contains: str,
                              gap: int = 3, max_width: int = 64,
                              max_height: int = 64, min_pixels: int = 12,
                              max_regions: int = 96, max_palettes: int = 16,
                              max_coverage: float = .98) -> dict:
    if (not contains.strip() or gap < 0
            or min(max_width, max_height, min_pixels, max_regions, max_palettes) < 1
            or not 0 < max_coverage <= 1):
        raise ValueError("Parametros de alineacion invalidos")
    if not source.is_dir():
        raise ValueError(f"No existe carpeta: {source}")
    matches = sorted(p for p in source.rglob("decoded.bin") if contains in p.parent.name)
    if len(matches) != 1:
        raise ValueError("El filtro debe identificar exactamente un atlas TIM")
    path = matches[0]
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Archivo demasiado grande")
    data = path.read_bytes()
    tim = parse_tim(data, 0)
    if tim is None or tim["end"] != len(data) or tim["bpp"] != 4 or not tim["palettes"]:
        raise ValueError("Se necesita TIM 4bpp completo con paletas")
    w, h = tim["width"], tim["height"]
    area = w * h
    valid = {}
    palette_records = []
    for index in range(min(len(tim["palettes"]), max_palettes)):
        pix = rgba(tim, index)
        opaque = sum(pix[i] != 0 for i in range(3, len(pix), 4))
        coverage = opaque / area
        status = "empty" if opaque == 0 else (
            "nearly_opaque" if coverage >= max_coverage else "partial")
        palette_records.append({"palette": index, "coverage": coverage, "status": status})
        if status == "partial":
            valid[index] = pix
    # Shared geometry comes from alpha coverage of *all* useful palettes.
    # An atlas may have no eligible palettes; report this rather than guessing.
    mask = bytearray(area * 4)
    for pix in valid.values():
        for n in range(area):
            if pix[4 * n + 3]:
                mask[4 * n + 3] = 255
    components = (connected_regions(bytes(mask), w, h, min_pixels=min_pixels,
                                    max_regions=max_regions) if valid else [])
    groups = group_regions(components, gap=gap, max_width=max_width,
                           max_height=max_height)
    output.mkdir(parents=True, exist_ok=True)
    aligned = []
    for index, group in enumerate(groups):
        box = {key: group[key] for key in ("x", "y", "w", "h")}
        variations = []
        for palette, pix in valid.items():
            crop = _crop(pix, w, group)
            pixel_count = sum(crop[k] != 0 for k in range(3, len(crop), 4))
            if pixel_count == 0:
                variations.append({"palette": palette, "status": "empty_in_box"})
                continue
            filename = f"aligned_{index:03d}_pal_{palette:03d}.png"
            write_png(output / filename, group["w"], group["h"], crop)
            variations.append({"palette": palette, "status": "exported",
                               "visible_pixels": pixel_count, "png": filename})
        aligned.append({"id": index, "box": box, "component_ids": group["members"],
                        "variants": variations})
    origin = {}
    manifest = path.with_name("rlen_manifest.json")
    if manifest.is_file():
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        origin = {key: meta[key] for key in ("lba", "sector_offset") if key in meta}
    report = {
        "source": path.relative_to(source).as_posix(),
        "origin": origin, "atlas_size": [w, h],
        "parameters": {"gap": gap, "max_width": max_width, "max_height": max_height,
                       "min_pixels": min_pixels, "max_regions": max_regions,
                       "max_coverage": max_coverage},
        "palettes": palette_records, "component_count": len(components),
        "aligned_group_count": len(aligned), "groups": aligned,
        "godot_note": ("PNG files may be imported into Godot as textures. "
                       "Do not treat variant palettes as animation frames; "
                       "SpriteFrames sequencing and frame duration require manual verification."),
        "warning": "Shared spatial bounding boxes are unverified candidate figures.",
    }
    (output / "aligned_candidates.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    return report
