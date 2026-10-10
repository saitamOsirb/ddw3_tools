"""Compare exact neighboring RLEN resources without inferring animation semantics."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .sprites import parse_tim, rgba, write_png
from .texture_sheets import _paste_thumbnail

DEFAULT_TARGETS = ((24226, 1732), (24233, 540), (24241, 668),
                   (24246, 748), (24253, 32), (24256, 588))


def compare_neighbor_atlases(source: Path, output: Path, *,
                             targets: tuple[tuple[int, int], ...] = DEFAULT_TARGETS,
                             tile: int = 280) -> dict:
    if not source.is_dir() or not 64 <= tile <= 512 or not 1 <= len(targets) <= 24:
        raise ValueError("Carpeta, cantidad de recursos o tamano de celda invalido")
    if len(set(targets)) != len(targets):
        raise ValueError("Posiciones LBA duplicadas")
    output.mkdir(parents=True, exist_ok=True)
    # Resolve by the actual batch naming convention, not filename substring:
    # lba_024241_offset_0668/decoded.bin
    paths = {}
    for path in source.rglob("decoded.bin"):
        match = re.fullmatch(r"lba_(\d+)_offset_(\d+)", path.parent.name)
        if match:
            key = tuple(map(int, match.groups()))
            if key in targets:
                if key in paths:
                    raise ValueError(f"Recurso duplicado: {key}")
                paths[key] = path
    records = []
    decoded = {}
    for lba, offset in targets:
        item = {"lba": lba, "offset": offset}
        path = paths.get((lba, offset))
        if path is None:
            item["status"] = "missing"
        else:
            item["file"] = path.relative_to(source).as_posix()
            try:
                if path.stat().st_size > 32 * 1024 * 1024:
                    raise ValueError("Recurso demasiado grande")
                data = path.read_bytes()
                tim = parse_tim(data, 0)
                if tim is None or tim["end"] != len(data):
                    raise ValueError("No es TIM completo al inicio")
                pix = rgba(tim)
                item.update({
                    "status": "tim", "decoded_bytes": len(data),
                    "decoded_sha256": hashlib.sha256(data).hexdigest(),
                    "width": tim["width"], "height": tim["height"],
                    "bpp": tim["bpp"], "palette_count": len(tim["palettes"]),
                    "indices_sha256": hashlib.sha256(tim["pixels"]).hexdigest(),
                    "clut_sha256": hashlib.sha256(
                        b"".join(int(v).to_bytes(2, "little")
                                 for pal in tim["palettes"] for v in pal)).hexdigest(),
                    "palette0_rgba_sha256": hashlib.sha256(pix).hexdigest(),
                    "palette0_visible_pixels": sum(pix[i] != 0 for i in range(3, len(pix), 4)),
                })
                decoded[(lba, offset)] = (tim, pix)
                filename = f"lba_{lba:06d}_offset_{offset:04d}_palette0.png"
                write_png(output / filename, tim["width"], tim["height"], pix)
                item["png"] = filename
            except (OSError, ValueError, IndexError) as exc:
                item["status"] = "invalid"
                item["reason"] = str(exc)
        records.append(item)
    comparisons = []
    for index, a in enumerate(records):
        for b in records[index + 1:]:
            result = {"a": [a["lba"], a["offset"]], "b": [b["lba"], b["offset"]]}
            if a["status"] == b["status"] == "tim":
                ta, pa = decoded[tuple(result["a"])]
                tb, pb = decoded[tuple(result["b"])]
                result["same_dimensions_bpp"] = (
                    ta["width"], ta["height"], ta["bpp"]) == (
                    tb["width"], tb["height"], tb["bpp"])
                result["same_indexed_pixels"] = ta["pixels"] == tb["pixels"]
                result["same_clut"] = ta["palettes"] == tb["palettes"]
                if len(pa) == len(pb) and ta["width"] == tb["width"] and ta["height"] == tb["height"]:
                    result["palette0_changed_rgba_pixels"] = sum(
                        pa[p:p + 4] != pb[p:p + 4] for p in range(0, len(pa), 4))
                else:
                    result["palette0_changed_rgba_pixels"] = None
            else:
                result["not_comparable"] = True
            comparisons.append(result)
    count = len(targets)
    canvas = bytearray(bytes((42, 42, 42, 255)) * (tile * count * tile))
    for index, item in enumerate(records):
        key = (item["lba"], item["offset"])
        if key in decoded:
            tim, pix = decoded[key]
            _paste_thumbnail(canvas, tile * count, tile, pix, tim["width"],
                             tim["height"], index * tile, 0, tile, 6)
            item["sheet_column"] = index
    sheet = "neighbor_comparison.png"
    write_png(output / sheet, tile * count, tile, bytes(canvas))
    report = {
        "source": str(source), "sheet": sheet, "tile_size": tile,
        "resources": records, "pairwise": comparisons,
        "warning": ("Matching size, pixel data or adjacent LBA locations cannot establish "
                    "character identity, frame sequence or animation timing. "
                    "All comparisons use palette 0 for rendered RGBA."),
    }
    (output / "neighbor_comparison.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    return report
