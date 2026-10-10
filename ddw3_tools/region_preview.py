"""Experimental TIM layout previews based on measured 12-byte header fields.

An arbitrary left/right-to-top/bottom rearrangement is a VISUAL HYPOTHESIS,
not a reconstructed Digimon sprite. Original RLEN payloads are never modified.
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

from .sprites import parse_tim, rgba, write_png


def split_preview(data: bytes):
    """Return RGBA preview for testable split hypothesis, or a rejection reason."""
    if len(data) < 28:
        return None, "payload_too_short"
    header = struct.unpack_from("<I", data)[0]
    if header < 28 or header > len(data) or (header - 16) % 12:
        return None, "invalid_header"
    tim = parse_tim(data, header)
    if tim is None or tim["end"] != len(data):
        return None, "no_complete_tim"
    rows = (header - 16) // 12
    last = struct.unpack_from("<6H", data, 16 + (rows - 1) * 12)
    left_width, right_width = last[0], last[2]
    w, h = tim["width"], tim["height"]
    if not (0 < left_width < w and right_width > 0
            and left_width + right_width == w):
        return None, "split_does_not_cover_tim"
    if not tim["palettes"] and tim["bpp"] in (4, 8):
        return None, "missing_palette"
    try:
        pixels = rgba(tim, 0)
    except (IndexError, ValueError, struct.error):
        return None, "pixel_conversion_error"
    if len(pixels) != w * h * 4:
        return None, "unexpected_rgba_size"
    # Stacking adjacent horizontal strips vertically is purely experimental.
    # Transparent padding preserves every source pixel, with no resampling.
    out_w = max(left_width, right_width)
    out_h = h * 2
    result = bytearray(out_w * out_h * 4)
    for y in range(h):
        src = y * w * 4
        left_dst = y * out_w * 4
        right_dst = (y + h) * out_w * 4
        result[left_dst:left_dst + left_width * 4] = pixels[src:src + left_width * 4]
        result[right_dst:right_dst + right_width * 4] = pixels[
            src + left_width * 4:src + w * 4]
    return {
        "width": out_w, "height": out_h, "rgba": bytes(result),
        "source_width": w, "source_height": h,
        "left_width": left_width, "right_width": right_width,
        "tim_offset": header, "tim_bpp": tim["bpp"],
    }, None


def preview_regions(source: Path, output: Path, *, max_files: int = 100,
                    max_pngs: int = 25) -> dict:
    if max_files < 1 or max_pngs < 1:
        raise ValueError("Los limites deben ser positivos")
    if not source.is_dir():
        raise ValueError(f"No existe carpeta: {source}")
    output.mkdir(parents=True, exist_ok=True)
    files = sorted(source.rglob("decoded.bin"))
    counters = Counter()
    entries = []
    for path in files[:max_files]:
        counters["examined"] += 1
        if counters["exported"] >= max_pngs:
            break
        try:
            if path.stat().st_size > 32 * 1024 * 1024:
                counters["oversize"] += 1
                continue
            preview, reason = split_preview(path.read_bytes())
            if reason is not None:
                counters[reason] += 1
                continue
            basename = path.parent.name
            target = output / f"{basename}_split_vertical.png"
            write_png(target, preview["width"], preview["height"], preview["rgba"])
            entries.append({
                "source": path.relative_to(source).as_posix(),
                "png": target.name,
                "source_dimensions": [preview["source_width"], preview["source_height"]],
                "preview_dimensions": [preview["width"], preview["height"]],
                "left_width": preview["left_width"],
                "right_width": preview["right_width"],
                "tim_bpp": preview["tim_bpp"],
                "tim_offset": preview["tim_offset"],
            })
            counters["exported"] += 1
        except (OSError, ValueError, struct.error) as exc:
            counters["errors"] += 1
            if len(entries) < max_pngs:
                entries.append({"source": path.relative_to(source).as_posix(),
                                "error": str(exc)})
    result = {
        "source": str(source), "counts": dict(counters),
        "entries": entries,
        "hypothesis": "Horizontal split at final header record u16[0], stacking right section below left",
        "warning": "Experimental visualization only; not a validated sprite layout or animation.",
    }
    (output / "regions_preview.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
