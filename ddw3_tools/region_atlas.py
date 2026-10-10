"""Non-destructive TIM region atlas for studying 12-byte header records.

Record semantics remain unknown. Output contains exact pixel crops and the
original texture; rectangles are hypotheses, not decoded map assembly.
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

from .sprites import parse_tim, rgba, write_png


def inspect_regions(data: bytes) -> tuple[dict | None, str | None]:
    if len(data) < 28:
        return None, "short"
    length = struct.unpack_from("<I", data)[0]
    if not 28 <= length < len(data) or (length - 16) % 12:
        return None, "header_shape"
    tim = parse_tim(data, length)
    if tim is None or tim["end"] != len(data):
        return None, "not_complete_tim"
    width, height = tim["width"], tim["height"]
    rows = [list(struct.unpack_from("<6H", data, 16 + 12 * i))
            for i in range((length - 16) // 12)]
    candidate_rectangles = []
    # Only consider the documented positional arithmetic hypothesis for
    # the LAST record. This is explicitly a crop, not a texture transform.
    last = rows[-1]
    if 0 < last[0] < width and 0 < last[2] <= width - last[0]:
        candidate_rectangles = [
            {"x": 0, "y": 0, "w": last[0], "h": height,
             "source": "last_record_u16_0"},
            {"x": last[0], "y": 0, "w": last[2], "h": height,
             "source": "last_record_u16_2"},
        ]
    return {
        "tim": tim, "record_words": rows, "header_length": length,
        "candidate_rectangles": candidate_rectangles,
    }, None


def crop_rgba(pixels: bytes, source_width: int, source_height: int,
              x: int, y: int, width: int, height: int) -> bytes:
    if (x < 0 or y < 0 or width <= 0 or height <= 0
            or x + width > source_width or y + height > source_height
            or len(pixels) != source_width * source_height * 4):
        raise ValueError("Recorte fuera de limites")
    return b"".join(
        pixels[((y + row) * source_width + x) * 4:
               ((y + row) * source_width + x + width) * 4]
        for row in range(height)
    )


def export_region_atlas(source: Path, output: Path, *,
                        max_files: int = 250, max_atlases: int = 30) -> dict:
    if max_files < 1 or max_atlases < 1:
        raise ValueError("Los limites deben ser positivos")
    if not source.is_dir():
        raise ValueError(f"No existe carpeta: {source}")
    output.mkdir(parents=True, exist_ok=True)
    files = sorted(source.rglob("decoded.bin"))
    counts = Counter()
    entries = []
    for path in files[:max_files]:
        if counts["exported"] >= max_atlases:
            break
        counts["examined"] += 1
        try:
            if path.stat().st_size > 32 * 1024 * 1024:
                counts["oversize"] += 1
                continue
            info, reason = inspect_regions(path.read_bytes())
            if reason is not None:
                counts[reason] += 1
                continue
            rects = info["candidate_rectangles"]
            if not rects:
                counts["no_split"] += 1
                continue
            tim = info["tim"]
            if tim["bpp"] in (4, 8) and not tim["palettes"]:
                counts["no_palette"] += 1
                continue
            base = path.parent.name
            pixels = rgba(tim)
            original = f"{base}_original.png"
            write_png(output / original, tim["width"], tim["height"], pixels)
            crops = []
            for i, rectangle in enumerate(rects):
                filename = f"{base}_region_{i:02d}.png"
                png_pixels = crop_rgba(pixels, tim["width"], tim["height"],
                                       rectangle["x"], rectangle["y"],
                                       rectangle["w"], rectangle["h"])
                write_png(output / filename, rectangle["w"], rectangle["h"], png_pixels)
                crops.append({**rectangle, "png": filename})
            entries.append({
                "file": path.relative_to(source).as_posix(),
                "original": original, "dimensions": [tim["width"], tim["height"]],
                "bpp": tim["bpp"], "tim_vram_xy": tim["image_position"],
                "header_length": info["header_length"],
                "records_u16le": info["record_words"],
                "candidate_crops": crops,
                "source_pixels_preserved": (
                    sum(rect["w"] * rect["h"] for rect in rects)
                    == tim["width"] * tim["height"]
                ),
            })
            counts["exported"] += 1
        except (OSError, ValueError, IndexError, struct.error) as exc:
            counts["errors"] += 1
            if len(entries) < max_atlases:
                entries.append({"file": path.relative_to(source).as_posix(),
                                "error": str(exc)})
    result = {
        "source": str(source), "counts": dict(counts),
        "entries": entries,
        "experiment": "Preserve original TIM and cut two side-by-side rectangles from final 12-byte record; no stacking or rescaling.",
        "limitations": "Does not reconstruct world maps, 3D models, sprites or animations.",
    }
    (output / "regions_atlas.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    return result
