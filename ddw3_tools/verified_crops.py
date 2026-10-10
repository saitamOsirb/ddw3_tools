"""Export verified crops directly from the larger original TIM.

The output is a set of independent candidate images, not a fabricated animation.
"""
from __future__ import annotations

import json
from pathlib import Path

from .related_atlases import _load
from .frame_grouping import _crop
from .sprites import rgba, write_png


def export_verified_crops(source: Path, verified_path: Path, output: Path,
                          *, palette: int = 0) -> dict:
    if not source.is_dir() or palette < 0:
        raise ValueError("Entrada o paleta invalida")
    report = json.loads(verified_path.read_text(encoding="utf-8-sig"))
    large = report["large"]
    path = source / f"lba_{large['lba']:06d}_offset_{large['offset']:04d}" / "decoded.bin"
    tim = _load(path)
    if palette >= len(tim["palettes"]):
        raise ValueError("La paleta no existe en TIM")
    if large["size"] != [tim["width"], tim["height"]]:
        raise ValueError("Dimensiones incompatibles con el informe")
    pixels = rgba(tim, palette)
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    seen = set()
    for item in report["findings"]:
        gid = item["group_id"]
        x, y = item["large_xy"]
        w, h = item["small_box"]["w"], item["small_box"]["h"]
        if (min(x, y) < 0 or min(w, h) < 1 or
                x + w > tim["width"] or y + h > tim["height"]):
            raise ValueError("Recorte fuera de los limites TIM")
        if gid in seen:
            raise ValueError("ID de grupo ambiguo")
        seen.add(gid)
        box = {"x": x, "y": y, "w": w, "h": h}
        crop = _crop(pixels, tim["width"], box)
        visible = sum(crop[i] != 0 for i in range(3, len(crop), 4))
        name = f"verified_group_{gid:03d}_pal_{palette:03d}.png"
        write_png(output / name, w, h, crop)
        entries.append({
            "group_id": gid, "source_box": box,
            "palette": palette, "visible_pixels": visible,
            "png": name,
            "exact_indexed_pixels": item["exact_indexed_pixels"],
        })
    result = {
        "source": path.relative_to(source).as_posix(), "entries": entries,
        "warning": "Verified spatial crops are not a proven frame order or animation.",
    }
    (output / "verified_crops.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
