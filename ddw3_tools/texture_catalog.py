"""Technical TIM texture catalog; no unsupported map/character identification."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .resource_inspector import inspect_payload


def catalog_textures(source: Path, output: Path, *, max_files: int = 10000) -> dict:
    if max_files < 1:
        raise ValueError("max_files debe ser positivo")
    if not source.is_dir():
        raise ValueError(f"No existe carpeta: {source}")
    files = sorted(source.rglob("decoded.bin"))
    counts = Counter()
    entries = []
    for path in files[:max_files]:
        try:
            if path.stat().st_size > 32 * 1024 * 1024:
                counts["oversize"] += 1
                continue
            details = inspect_payload(path.read_bytes())
            if not details["tim_images"]:
                counts["unknown_binary"] += 1
                continue
            tim = details["tim_images"][0]
            width, height = tim["width"], tim["height"]
            if width == height:
                shape = "square"
            elif width > height:
                shape = "landscape"
            else:
                shape = "portrait"
            layout = ("tim_with_header" if tim["offset"] > 0 else "tim_only")
            bucket = f"{tim['bpp']}bpp/{layout}/{shape}"
            counts[bucket] += 1
            entries.append({
                "file": path.relative_to(source).as_posix(),
                "width": width, "height": height, "bpp": tim["bpp"],
                "palette_count": tim["palette_count"],
                "has_embedded_clut": tim["has_embedded_clut"],
                "tim_vram_xy": tim["image_vram_xy"],
                "header_bytes": tim["offset"],
                "shape": shape,
                "bucket": bucket,
                "identification": "unknown",
            })
        except (ValueError, OSError):
            counts["errors"] += 1
    result = {
        "source": str(source),
        "files_examined": min(len(files), max_files),
        "files_total": len(files),
        "truncated": len(files) > max_files,
        "counts": dict(sorted(counts.items())),
        "textures": entries,
        "warning": ("Buckets classify TIM characteristics only; they do not identify "
                    "Digimon, characters, maps, models or animations."),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
