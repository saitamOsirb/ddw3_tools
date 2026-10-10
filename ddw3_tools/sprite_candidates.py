"""Export validated 4-bpp TIM sprite-atlas candidates with provenance.

A 4-bpp TIM containing repeated figures is a *candidate* spritesheet,
not proof that each apparent cell is one animation frame.
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

from .sprites import parse_tim, rgba, write_png


def export_sprite_candidates(source: Path, output: Path, *,
                             max_files: int = 10000,
                             max_candidates: int = 250) -> dict:
    if max_files < 1 or max_candidates < 1:
        raise ValueError("Los limites deben ser positivos")
    if not source.is_dir():
        raise ValueError(f"No existe carpeta: {source}")
    files = sorted(source.rglob("decoded.bin"))
    output.mkdir(parents=True, exist_ok=True)
    stats = Counter()
    entries = []
    for path in files[:max_files]:
        if len(entries) >= max_candidates:
            break
        stats["scanned"] += 1
        try:
            if path.stat().st_size > 32 * 1024 * 1024:
                stats["oversize"] += 1
                continue
            data = path.read_bytes()
            if len(data) < 8 or data[:4] != b"\x10\x00\x00\x00":
                stats["not_tim_at_start"] += 1
                continue
            tim = parse_tim(data, 0)
            if tim is None or tim["end"] != len(data) or tim["bpp"] != 4:
                stats["not_complete_4bpp"] += 1
                continue
            if not tim["palettes"]:
                stats["missing_palette"] += 1
                continue
            base = path.parent.name
            images = []
            for palette in range(len(tim["palettes"])):
                filename = f"{base}_pal_{palette:03d}.png"
                write_png(output / filename, tim["width"], tim["height"],
                          rgba(tim, palette))
                images.append(filename)
            origin_file = path.parent / "rlen_manifest.json"
            origin = {}
            if origin_file.is_file():
                metadata = json.loads(origin_file.read_text(encoding="utf-8"))
                origin = {key: metadata[key] for key in ("lba", "sector_offset")
                          if key in metadata}
            entries.append({
                "source": path.relative_to(source).as_posix(),
                "width": tim["width"], "height": tim["height"],
                "bpp": 4, "palette_count": len(tim["palettes"]),
                "image_vram_xy": tim["image_position"],
                "clut_vram_xy": tim["clut_position"],
                "origin": origin, "pngs": images,
            })
            stats["exported"] += 1
        except (OSError, ValueError, IndexError, struct.error,
                json.JSONDecodeError):
            stats["errors"] += 1
    report = {
        "source": str(source), "counts": dict(stats),
        "candidate_count": len(entries),
        "max_files_reached": len(files) > max_files,
        "max_candidates_reached": len(entries) >= max_candidates,
        "candidates": entries,
        "note": "Exports complete 4-bpp TIM textures only; frames, character IDs and animations are not inferred.",
    }
    (output / "sprite_candidates.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    return report
