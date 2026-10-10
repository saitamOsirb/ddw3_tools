"""Evidence-only spatial comparison of aligned small-atlas groups with a larger TIM.

Searches translations using alpha masks; exact RGBA matches are additionally
reported. No palette equivalence, animation order or character identity inferred.
"""
from __future__ import annotations

import json
from pathlib import Path

from .sprites import parse_tim, rgba, write_png

def _load(path: Path):
    if not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError(f"TIM ausente o demasiado grande: {path}")
    data = path.read_bytes()
    tim = parse_tim(data, 0)
    if tim is None or tim["end"] != len(data) or tim["bpp"] != 4 or not tim["palettes"]:
        raise ValueError(f"No es TIM 4bpp completo con CLUT: {path}")
    return tim

def _alpha(pixels: bytes) -> bytes:
    return pixels[3::4]

def locate_exact_regions(small: bytes, sw: int, sh: int, box: dict,
                         large: bytes, lw: int, lh: int, *,
                         min_opaque: int = 24, max_matches: int = 20) -> dict:
    x, y, w, h = (box[k] for k in ("x", "y", "w", "h"))
    if (min_opaque < 1 or max_matches < 1 or
            min(x, y) < 0 or w < 1 or h < 1 or x + w > sw or y + h > sh or
            len(small) != sw * sh * 4 or len(large) != lw * lh * 4):
        raise ValueError("Dimensiones o limites invalidos")
    if w > lw or h > lh:
        return {"opaque_pixels": 0, "eligible": False, "matches": []}
    mask_a, mask_b = _alpha(small), _alpha(large)
    foreground = [(cx, cy) for cy in range(h) for cx in range(w)
                  if mask_a[(y + cy) * sw + x + cx]]
    count = len(foreground)
    if count < min_opaque:
        return {"opaque_pixels": count, "eligible": False, "matches": []}
    # Require *the whole crop* to have identical transparency geometry.
    # Two distinct opaque points accelerate rejection; matching RGB is
    # stricter and does not assume different CLUTs are interchangeable.
    first, last = foreground[0], foreground[-1]
    matches = []
    for ty in range(lh - h + 1):
        for tx in range(lw - w + 1):
            if not (mask_b[(ty + first[1]) * lw + tx + first[0]]
                    and mask_b[(ty + last[1]) * lw + tx + last[0]]):
                continue
            if any(bool(mask_a[(y + ry) * sw + x + rx]) !=
                   bool(mask_b[(ty + ry) * lw + tx + rx])
                   for ry in range(h) for rx in range(w)):
                continue
            same_rgba = all(
                small[((y + ry) * sw + x + rx) * 4:
                      ((y + ry) * sw + x + rx) * 4 + 4] ==
                large[((ty + ry) * lw + tx + rx) * 4:
                      ((ty + ry) * lw + tx + rx) * 4 + 4]
                for rx, ry in foreground
            )
            matches.append({"x": tx, "y": ty, "exact_alpha": True,
                            "exact_visible_rgba": same_rgba})
            if len(matches) >= max_matches:
                return {"opaque_pixels": count, "eligible": True,
                        "matches": matches, "truncated": True}
    return {"opaque_pixels": count, "eligible": True,
            "matches": matches, "truncated": False}

def compare_related_atlases(source: Path, aligned_dir: Path, output: Path, *,
                            large_lba: int = 24233, large_offset: int = 540,
                            small_lba: int = 24241, small_offset: int = 668,
                            min_opaque: int = 24, max_matches: int = 20) -> dict:
    if not source.is_dir() or min_opaque < 1 or max_matches < 1:
        raise ValueError("Parametros invalidos")
    big_path = source / f"lba_{large_lba:06d}_offset_{large_offset:04d}" / "decoded.bin"
    little_path = source / f"lba_{small_lba:06d}_offset_{small_offset:04d}" / "decoded.bin"
    big, little = _load(big_path), _load(little_path)
    report_path = aligned_dir / "aligned_candidates.json"
    aligned = json.loads(report_path.read_text(encoding="utf-8-sig"))
    expected = little_path.relative_to(source).as_posix()
    if aligned.get("source") != expected or aligned.get("atlas_size") != [little["width"], little["height"]]:
        raise ValueError("El informe alineado no corresponde al atlas pequeno")
    usable = [p["palette"] for p in aligned["palettes"] if p["status"] == "partial"]
    small_rgba = {p: rgba(little, p) for p in usable if 0 <= p < len(little["palettes"])}
    # Palette zero only for large atlas at this stage; other CLUT pairings remain unknown.
    large_rgba = rgba(big, 0)
    results = []
    for group in aligned["groups"]:
        box = group["box"]
        record = {"id": group["id"], "box": box, "palettes": []}
        for index, pix in small_rgba.items():
            matched = locate_exact_regions(
                pix, little["width"], little["height"], box, large_rgba,
                big["width"], big["height"], min_opaque=min_opaque,
                max_matches=max_matches)
            record["palettes"].append({"small_palette": index, "large_palette": 0, **matched})
        results.append(record)
    output.mkdir(parents=True, exist_ok=True)
    write_png(output / "large_palette0.png", big["width"], big["height"], large_rgba)
    for index, pix in small_rgba.items():
        write_png(output / f"small_palette{index}.png", little["width"], little["height"], pix)
    result = {
        "large": {"lba": large_lba, "offset": large_offset, "size": [big["width"], big["height"]]},
        "small": {"lba": small_lba, "offset": small_offset, "size": [little["width"], little["height"]]},
        "groups": results, "min_opaque": min_opaque, "max_matches_per_group": max_matches,
        "warning": ("Exact translated transparency shapes and RGBA matches only. "
                    "No approximate visual similarity or animation relationships inferred. "
                    "Absence of exact matches does not disprove related art or palettes."),
    }
    (output / "related_atlases.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
