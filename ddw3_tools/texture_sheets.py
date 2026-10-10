"""Deterministic contact sheets of actual decoded TIM textures, grouped by type.

Use source TIM pixels exactly; thumbnails only use nearest-neighbor scaling.
No claim that a texture belongs to a particular map, model, or Digimon.
"""
from __future__ import annotations

import json
import struct
from collections import defaultdict
from pathlib import Path

from .sprites import parse_tim, rgba, write_png


def _decode(path: Path):
    data = path.read_bytes()
    if len(data) > 32 * 1024 * 1024:
        return None
    offset = 0
    if len(data) >= 4:
        header = struct.unpack_from("<I", data)[0]
        if 28 <= header < len(data) and (header - 16) % 12 == 0:
            offset = header
    tim = parse_tim(data, offset)
    if tim is None or tim["end"] != len(data):
        return None
    w, h = tim["width"], tim["height"]
    orientation = "square" if w == h else ("landscape" if w > h else "portrait")
    bucket = f"{tim['bpp']}bpp/{'tim_with_header' if offset else 'tim_only'}/{orientation}"
    return tim, bucket, offset


def _sample_evenly(items: list, count: int) -> list:
    if len(items) <= count:
        return items
    if count == 1:
        return [items[len(items) // 2]]
    return [items[i * (len(items) - 1) // (count - 1)] for i in range(count)]


def _paste_thumbnail(canvas: bytearray, cw: int, ch: int, source: bytes,
                     sw: int, sh: int, cell_x: int, cell_y: int,
                     tile: int, margin: int) -> None:
    # Fit strictly within tile, preserving aspect ratio and nearest-neighbor pixels.
    scale = min((tile - 2 * margin) / sw, (tile - 2 * margin) / sh)
    dw, dh = max(1, int(sw * scale)), max(1, int(sh * scale))
    x0 = cell_x + (tile - dw) // 2
    y0 = cell_y + (tile - dh) // 2
    for y in range(dh):
        sy = min(sh - 1, y * sh // dh)
        for x in range(dw):
            sx = min(sw - 1, x * sw // dw)
            so = (sy * sw + sx) * 4
            do = ((y0 + y) * cw + x0 + x) * 4
            canvas[do:do + 4] = source[so:so + 4]


def build_texture_sheets(source: Path, output: Path, *,
                         max_files: int = 10000, per_group: int = 24,
                         tile: int = 128, columns: int = 6) -> dict:
    if max_files < 1 or per_group < 1 or per_group > 200 or not 32 <= tile <= 512 or not 1 <= columns <= 12:
        raise ValueError("Limites de lamina fuera de rango")
    if not source.is_dir():
        raise ValueError(f"No existe carpeta: {source}")
    files = sorted(source.rglob("decoded.bin"))
    groups = defaultdict(list)
    errors = 0
    for path in files[:max_files]:
        try:
            found = _decode(path)
            if found is None:
                errors += 1
                continue
            tim, bucket, offset = found
            groups[bucket].append((path, offset, tim["width"], tim["height"], tim["bpp"]))
        except (OSError, ValueError, struct.error):
            errors += 1
    output.mkdir(parents=True, exist_ok=True)
    sheets = []
    for bucket in sorted(groups):
        candidates = groups[bucket]
        sampled = _sample_evenly(candidates, per_group)
        rows = (len(sampled) + columns - 1) // columns
        cw, ch = tile * columns, tile * rows
        # A neutral opaque background to distinguish alpha from black.
        canvas = bytearray(bytes((42, 42, 42, 255)) * (cw * ch))
        entries = []
        for index, (path, offset, width, height, bpp) in enumerate(sampled):
            try:
                data = path.read_bytes()
                tim = parse_tim(data, offset)
                if tim is None:
                    raise ValueError("TIM inconsistente")
                pixels = rgba(tim)
                _paste_thumbnail(canvas, cw, ch, pixels, width, height,
                                 (index % columns) * tile, (index // columns) * tile,
                                 tile, 6)
                entries.append({"index": index, "column": index % columns,
                                "row": index // columns,
                                "file": path.relative_to(source).as_posix(),
                                "width": width, "height": height, "bpp": bpp,
                                "header_bytes": offset})
            except (ValueError, OSError, IndexError, struct.error):
                errors += 1
        filename = bucket.replace("/", "_") + ".png"
        write_png(output / filename, cw, ch, bytes(canvas))
        sheets.append({"group": bucket, "available": len(candidates),
                       "sampled": len(entries), "sheet": filename,
                       "tile_size": tile, "columns": columns,
                       "entries": entries})
    result = {"source": str(source), "scanned": min(len(files), max_files),
              "errors": errors, "sheets": sheets,
              "note": "Contact sheets use technical texture categories, not game-asset identification. Grid positions map to entries in JSON."}
    (output / "texture_sheets.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
