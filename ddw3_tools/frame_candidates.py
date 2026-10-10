"""Conservative connected-component candidates from 4bpp TIM atlas transparency.

Components are not claimed to be animation frames: disconnected limbs, shadows,
pixels from adjacent poses, and opaque backgrounds can all distort components.
No source assets are changed.
"""
from __future__ import annotations

import json
from collections import Counter, deque
from pathlib import Path

from .sprites import parse_tim, rgba, write_png


def connected_regions(pixels: bytes, width: int, height: int, *,
                      min_pixels: int = 12, max_regions: int = 96) -> list[dict]:
    if min_pixels < 1 or max_regions < 1 or width <= 0 or height <= 0:
        raise ValueError("Limites de deteccion invalidos")
    if len(pixels) != width * height * 4:
        raise ValueError("RGBA no coincide con dimensiones")
    visited = bytearray(width * height)
    result = []
    for start in range(width * height):
        if visited[start] or pixels[start * 4 + 3] == 0:
            continue
        visited[start] = 1
        queue = deque([start])
        count = 0
        x0, y0 = width, height
        x1 = y1 = 0
        while queue:
            cur = queue.popleft()
            x, y = cur % width, cur // width
            count += 1
            x0, x1 = min(x0, x), max(x1, x)
            y0, y1 = min(y0, y), max(y1, y)
            # 8-way connectivity is intentionally generous across diagonals.
            for ny in range(max(0, y - 1), min(height, y + 2)):
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    pos = ny * width + nx
                    if not visited[pos] and pixels[pos * 4 + 3] != 0:
                        visited[pos] = 1
                        queue.append(pos)
        if count >= min_pixels:
            result.append({"x": x0, "y": y0, "w": x1 - x0 + 1,
                           "h": y1 - y0 + 1, "opaque_pixels": count})
            if len(result) >= max_regions:
                break
    return sorted(result, key=lambda r: (r["y"], r["x"]))


def extract_candidate_frames(source: Path, output: Path, *,
                             contains: str | None = None,
                             max_files: int = 10000,
                             max_atlases: int = 2,
                             max_regions: int = 96,
                             min_pixels: int = 12,
                             max_palettes: int = 16) -> dict:
    if min(max_files, max_atlases, max_regions, min_pixels, max_palettes) < 1:
        raise ValueError("Los limites deben ser positivos")
    if not source.is_dir():
        raise ValueError(f"No existe carpeta: {source}")
    all_files = sorted(source.rglob("decoded.bin"))
    files = [p for p in all_files if not contains or contains in p.parent.name]
    output.mkdir(parents=True, exist_ok=True)
    stats = Counter()
    atlases = []
    for path in files[:max_files]:
        if len(atlases) >= max_atlases:
            break
        stats["scanned"] += 1
        try:
            if path.stat().st_size > 32 * 1024 * 1024:
                stats["oversize"] += 1
                continue
            data = path.read_bytes()
            tim = parse_tim(data, 0)
            if tim is None or tim["end"] != len(data) or tim["bpp"] != 4 or not tim["palettes"]:
                stats["not_complete_4bpp"] += 1
                continue
            base = path.parent.name
            palette_entries = []
            for palette_index in range(min(len(tim["palettes"]), max_palettes)):
                pixels = rgba(tim, palette_index)
                total_pixels = tim["width"] * tim["height"]
                visible_pixels = sum(pixels[i] != 0 for i in range(3, len(pixels), 4))
                coverage = visible_pixels / total_pixels
                if visible_pixels == 0:
                    stats["empty_palettes"] += 1
                    palette_entries.append({"palette": palette_index,
                                            "visible_pixels": 0,
                                            "coverage": 0.0,
                                            "status": "empty",
                                            "regions": []})
                    continue
                if coverage >= 0.98:
                    stats["full_coverage_palettes"] += 1
                    palette_entries.append({"palette": palette_index,
                                            "visible_pixels": visible_pixels,
                                            "coverage": coverage,
                                            "status": "nearly_opaque",
                                            "regions": []})
                    continue
                regions = connected_regions(
                    pixels, tim["width"], tim["height"],
                    min_pixels=min_pixels, max_regions=max_regions)
                folder = output / base / f"palette_{palette_index:03d}"
                folder.mkdir(parents=True, exist_ok=True)
                out_regions = []
                for i, region in enumerate(regions):
                    x, y, w, h = (region[k] for k in ("x", "y", "w", "h"))
                    crop = b"".join(
                        pixels[((y + yy) * tim["width"] + x) * 4:
                               ((y + yy) * tim["width"] + x + w) * 4]
                        for yy in range(h))
                    filename = f"candidate_{i:03d}.png"
                    write_png(folder / filename, w, h, crop)
                    out_regions.append({**region, "png": (folder / filename).relative_to(output).as_posix()})
                palette_entries.append({"palette": palette_index,
                                        "visible_pixels": visible_pixels,
                                        "coverage": coverage,
                                        "status": "partial",
                                        "regions": out_regions})
                stats["regions_exported"] += len(out_regions)
            origin = {}
            manifest = path.parent / "rlen_manifest.json"
            if manifest.is_file():
                raw = json.loads(manifest.read_text(encoding="utf-8"))
                origin = {k: raw[k] for k in ("lba", "sector_offset") if k in raw}
            atlases.append({"source": path.relative_to(source).as_posix(),
                            "dimensions": [tim["width"], tim["height"]],
                            "available_palettes": len(tim["palettes"]),
                            "origin": origin, "palettes": palette_entries})
            stats["atlases_exported"] += 1
        except (OSError, ValueError, IndexError, json.JSONDecodeError) as exc:
            stats["errors"] += 1
    result = {
        "source": str(source), "filter": contains,
        "counts": dict(stats), "atlases": atlases,
        "note": ("Eight-connected opaque components are only segmentation candidates; "
                 "they are not confirmed characters, frames, directions, or animations. "
                 "Zero-valued CLUT colors follow the existing PNG decoder transparency policy. "
                 "Nearly opaque palettes (>=98%) are reported but not segmented."),
    }
    (output / "frame_candidates.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    return result
