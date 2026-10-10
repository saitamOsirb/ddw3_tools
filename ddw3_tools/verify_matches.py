"""Verify known atlas correspondences against all CLUTs and original 4-bit indices.

A candidate is accepted only if the previously detected alpha mask exactly
matches at its recorded translation. Does not invent frame sequences.
"""
from __future__ import annotations

import json
from pathlib import Path

from .related_atlases import _load
from .sprites import rgba, write_png


def _indices(tim: dict) -> bytes:
    out = bytearray()
    for value in tim["pixels"]:
        out.extend((value & 15, value >> 4))
    return bytes(out)


def verify_atlas_matches(source: Path, aligned_dir: Path, matches_path: Path,
                         output: Path, *, max_palettes: int = 16) -> dict:
    if not 1 <= max_palettes <= 16 or not source.is_dir():
        raise ValueError("Parametros invalidos")
    matches = json.loads(matches_path.read_text(encoding="utf-8-sig"))
    aligned = json.loads((aligned_dir / "aligned_candidates.json").read_text(encoding="utf-8-sig"))
    large = matches["large"]
    small = matches["small"]
    big_path = source / f"lba_{large['lba']:06d}_offset_{large['offset']:04d}" / "decoded.bin"
    little_path = source / f"lba_{small['lba']:06d}_offset_{small['offset']:04d}" / "decoded.bin"
    if aligned["source"] != little_path.relative_to(source).as_posix():
        raise ValueError("Informe alineado no corresponde al atlas pequeno")
    big, little = _load(big_path), _load(little_path)
    lw, lh, sw, sh = big["width"], big["height"], little["width"], little["height"]
    if large["size"] != [lw, lh] or small["size"] != [sw, sh]:
        raise ValueError("Dimensiones del informe no coinciden")
    bidx, sidx = _indices(big), _indices(little)
    big_palettes = [(p, rgba(big, p)) for p in range(min(max_palettes, len(big["palettes"])))]
    small_palettes = [(p, rgba(little, p)) for p in range(min(max_palettes, len(little["palettes"])))]
    by_id = {g["id"]: g["box"] for g in aligned["groups"]}
    output.mkdir(parents=True, exist_ok=True)
    findings = []
    seen = set()
    for group in matches["groups"]:
        gid = group["id"]
        if gid not in by_id or group["box"] != by_id[gid]:
            raise ValueError("Caja de grupo inconsistente")
        x, y, w, h = (group["box"][k] for k in ("x", "y", "w", "h"))
        if min(x, y) < 0 or x + w > sw or y + h > sh:
            raise ValueError("Caja fuera del atlas")
        for palette in group["palettes"]:
            sp = palette["small_palette"]
            if sp >= len(little["palettes"]):
                raise ValueError("Paleta pequena invalida")
            for match in palette["matches"]:
                bx, by = match["x"], match["y"]
                key = (gid, sp, bx, by)
                if key in seen:
                    continue
                seen.add(key)
                if min(bx, by) < 0 or bx + w > lw or by + h > lh:
                    raise ValueError("Correspondencia fuera del atlas")
                a = rgba(little, sp)
                b = rgba(big, palette["large_palette"])
                if any(bool(a[((y + ry) * sw + x + rx) * 4 + 3]) !=
                       bool(b[((by + ry) * lw + bx + rx) * 4 + 3])
                       for ry in range(h) for rx in range(w)):
                    raise ValueError("La coincidencia almacenada no reproduce la mascara")
                index_total = w * h
                same_index = sum(
                    sidx[(y + ry) * sw + x + rx] == bidx[(by + ry) * lw + bx + rx]
                    for ry in range(h) for rx in range(w))
                variants = []
                for si, sa in small_palettes:
                    for bi, ba in big_palettes:
                        same_mask = all(
                            bool(sa[((y + ry) * sw + x + rx) * 4 + 3]) ==
                            bool(ba[((by + ry) * lw + bx + rx) * 4 + 3])
                            for ry in range(h) for rx in range(w))
                        if not same_mask:
                            continue
                        visible = 0
                        matched = 0
                        for ry in range(h):
                            for rx in range(w):
                                ai = ((y + ry) * sw + x + rx) * 4
                                bj = ((by + ry) * lw + bx + rx) * 4
                                if sa[ai + 3]:
                                    visible += 1
                                    matched += sa[ai:ai + 4] == ba[bj:bj + 4]
                        # An empty shared mask is not evidence of a matching sprite.
                        if visible == 0:
                            continue
                        variants.append({
                            "small_palette": si, "large_palette": bi,
                            "visible_pixels": visible, "same_visible_rgba_pixels": matched,
                            "exact_visible_rgba": matched == visible,
                        })
                findings.append({
                    "group_id": gid, "small_palette_of_original_match": sp,
                    "small_box": group["box"], "large_xy": [bx, by],
                    "indexed_pixels_equal": same_index,
                    "indexed_pixels_total": index_total,
                    "exact_indexed_pixels": same_index == index_total,
                    "palette_pairings_with_matching_alpha": variants,
                    "best_visible_rgba_pairing": (
                        max(variants, key=lambda v: (
                            v["same_visible_rgba_pixels"] / v["visible_pixels"],
                            v["same_visible_rgba_pixels"]))
                        if variants else None),
                })
    report = {
        "large": large, "small": small, "findings": findings,
        "summary": {
            "verified_locations": len(findings),
            "exact_indexed": sum(f["exact_indexed_pixels"] for f in findings),
            "exact_visible_rgba": sum(
                any(v["exact_visible_rgba"] for v in f["palette_pairings_with_matching_alpha"])
                for f in findings),
        },
        "warning": ("Checks only previously established exact-mask translations. "
                    "Palette differences and matching indices do not prove animation timing."),
    }
    (output / "verified_matches.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
