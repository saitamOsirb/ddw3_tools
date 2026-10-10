"""Reproducible, user-authored sprite composition from original 4bpp TIM pixels.

No automatic claims about character identity or animation ordering. Recipes
use aligned candidate IDs and offsets from their original atlas coordinates.
"""
from __future__ import annotations

import json
from pathlib import Path

from .frame_grouping import _crop
from .sprites import parse_tim, rgba, write_png


def _read_aligned(aligned_dir: Path) -> dict:
    data = json.loads((aligned_dir / "aligned_candidates.json").read_text(encoding="utf-8"))
    if not isinstance(data.get("groups"), list) or not isinstance(data.get("source"), str):
        raise ValueError("Informe aligned_candidates.json invalido")
    return data


def make_composition_recipe(aligned_dir: Path, recipe_path: Path, *,
                            palette: int = 0) -> dict:
    """Create an explicit starting proposal. Original atlas positions are used."""
    data = _read_aligned(aligned_dir)
    usable = {p["palette"] for p in data["palettes"] if p["status"] == "partial"}
    if palette not in usable:
        raise ValueError(f"Paleta {palette} no es utilizable en el informe")
    recipe = {
        "source": data["source"],
        "palette": palette,
        "note": ("Starting layout uses ORIGINAL ATLAS COORDINATES, not reconstructed "
                 "character poses. Edit enabled, x, y and z before composing."),
        "parts": [
            {"id": g["id"], "enabled": True,
             "x": g["box"]["x"], "y": g["box"]["y"],
             "z": g["id"]}
            for g in data["groups"]
        ],
    }
    recipe_path.parent.mkdir(parents=True, exist_ok=True)
    recipe_path.write_text(json.dumps(recipe, indent=2), encoding="utf-8")
    return recipe


def _over(canvas: bytearray, dest_index: int, source: bytes, src_index: int) -> None:
    """Porter-Duff source-over RGBA, with rounding and no external dependencies."""
    sa = source[src_index + 3]
    if sa == 0:
        return
    da = canvas[dest_index + 3]
    if sa == 255 or da == 0:
        canvas[dest_index:dest_index + 4] = source[src_index:src_index + 4]
        return
    alpha = sa * 255 + da * (255 - sa)
    for channel in range(3):
        num = (source[src_index + channel] * sa * 255
               + canvas[dest_index + channel] * da * (255 - sa))
        canvas[dest_index + channel] = (num + alpha // 2) // alpha
    canvas[dest_index + 3] = (alpha + 127) // 255


def compose_sprite(aligned_dir: Path, resources_dir: Path, recipe_path: Path,
                   output: Path) -> dict:
    aligned = _read_aligned(aligned_dir)
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    if recipe.get("source") != aligned["source"]:
        raise ValueError("La receta no corresponde a este atlas")
    if not isinstance(recipe.get("palette"), int):
        raise ValueError("Paleta invalida")
    palette = recipe["palette"]
    usable = {p["palette"] for p in aligned["palettes"] if p["status"] == "partial"}
    if palette not in usable:
        raise ValueError("Paleta no utilizable")
    source_name = aligned["source"]
    source = (resources_dir / source_name).resolve()
    if not source.is_relative_to(resources_dir.resolve()) or not source.is_file():
        raise ValueError("Ruta de TIM fuera de los recursos o inexistente")
    if source.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("TIM demasiado grande")
    raw = source.read_bytes()
    tim = parse_tim(raw, 0)
    if (tim is None or tim["end"] != len(raw) or tim["bpp"] != 4
            or palette >= len(tim["palettes"])
            or [tim["width"], tim["height"]] != aligned["atlas_size"]):
        raise ValueError("TIM no coincide con el informe")
    by_id = {g["id"]: g for g in aligned["groups"]}
    if not isinstance(recipe.get("parts"), list) or len(recipe["parts"]) > 256:
        raise ValueError("Lista de piezas invalida")
    selected = []
    for part in recipe["parts"]:
        if not isinstance(part, dict) or type(part.get("enabled")) is not bool:
            raise ValueError("Cada pieza necesita enabled booleano")
        if not part["enabled"]:
            continue
        if any(type(part.get(k)) is not int for k in ("id", "x", "y", "z")):
            raise ValueError("id, x, y, z deben ser enteros")
        if part["id"] not in by_id:
            raise ValueError(f"Grupo desconocido: {part['id']}")
        if any(abs(part[k]) > 16384 for k in ("x", "y")):
            raise ValueError("Desplazamiento fuera de rango")
        selected.append((part, by_id[part["id"]]))
    if not selected:
        raise ValueError("No hay piezas habilitadas")
    xmin = min(p["x"] for p, _ in selected)
    ymin = min(p["y"] for p, _ in selected)
    xmax = max(p["x"] + g["box"]["w"] for p, g in selected)
    ymax = max(p["y"] + g["box"]["h"] for p, g in selected)
    width, height = xmax - xmin, ymax - ymin
    if width > 2048 or height > 2048:
        raise ValueError("Composicion superior a 2048x2048")
    original = rgba(tim, palette)
    canvas = bytearray(width * height * 4)
    ordered = sorted(enumerate(selected), key=lambda entry: (entry[1][0]["z"], entry[0]))
    for _, (part, group) in ordered:
        box = group["box"]
        x0, y0, w, h = (box[k] for k in ("x", "y", "w", "h"))
        if min(x0, y0, w, h) < 0 or x0 + w > tim["width"] or y0 + h > tim["height"]:
            raise ValueError("Coordenadas de grupo fuera del TIM")
        fragment = _crop(original, tim["width"], box)
        for row in range(h):
            for col in range(w):
                dest_x = part["x"] - xmin + col
                dest_y = part["y"] - ymin + row
                _over(canvas, (dest_y * width + dest_x) * 4,
                      fragment, (row * w + col) * 4)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_png(output, width, height, bytes(canvas))
    result = {"source": source_name, "palette": palette, "output": str(output),
              "size": [width, height], "origin": [xmin, ymin],
              "parts": [p for p, _ in selected],
              "warning": "Manual composite preview. Not a verified character or animation."}
    output.with_suffix(".json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
