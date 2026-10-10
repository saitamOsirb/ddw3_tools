"""Build a reproducible inventory of extracted TIM textures.

This is a texture/region inventory, NOT an animation reconstruction: Digimon
World 3 animation order cannot be inferred reliably from TIM offsets alone.
"""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path


def _png_rgba(path: Path) -> tuple[int, int, bytes]:
    """Decode PNGs emitted by sprites.write_png (RGBA8, filter 0)."""
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"PNG invalido: {path}")
    pos, compressed, width, height = 8, bytearray(), None, None
    while pos + 12 <= len(data):
        size = struct.unpack_from(">I", data, pos)[0]
        kind = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + size]
        if len(payload) != size:
            raise ValueError(f"PNG truncado: {path}")
        if kind == b"IHDR":
            width, height, depth, color, *_ = struct.unpack(">IIBBBBB", payload)
            if (depth, color) != (8, 6):
                raise ValueError("Solo PNG RGBA8 es compatible")
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
        pos += size + 12
    if not width or not height:
        raise ValueError("PNG sin dimensiones")
    scan = zlib.decompress(compressed)
    stride = width * 4
    if len(scan) != (stride + 1) * height:
        raise ValueError("PNG con datos incompletos")
    rgba = bytearray()
    for y in range(height):
        start = y * (stride + 1)
        if scan[start] != 0:
            raise ValueError("Filtro PNG no soportado")
        rgba.extend(scan[start + 1:start + stride + 1])
    return width, height, bytes(rgba)


def inspect_png(path: Path) -> dict:
    width, height, rgba = _png_rgba(path)
    occupied = []
    row_counts = []
    for y in range(height):
        count = 0
        for x in range(width):
            if rgba[(y * width + x) * 4 + 3]:
                occupied.append((x, y))
                count += 1
        row_counts.append(count)
    if occupied:
        bounds = [min(x for x, _ in occupied), min(y for _, y in occupied),
                  max(x for x, _ in occupied) + 1, max(y for _, y in occupied) + 1]
    else:
        bounds = None
    return {"width": width, "height": height, "opaque_pixels": len(occupied),
            "opaque_fraction": round(len(occupied) / (width * height), 4),
            "content_bbox_xyxy": bounds, "opaque_pixels_per_row": row_counts}


def build_report(folder: Path, destination: Path | None = None) -> dict:
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    images = []
    for item in manifest["images"]:
        palettes = []
        for filename in item["files"]:
            palettes.append({"file": filename, **inspect_png(folder / filename)})
        images.append({"offset": item["offset"],
                       "logical_offset": item.get("logical_offset"),
                       "bpp": item["bpp"],
                       "image_position": item.get("image_position"),
                       "clut_position": item.get("clut_position"),
                       "external_palette": item.get("external_palette", False),
                       "palettes": palettes})
    report = {"source": manifest.get("source"),
              "disc_layout": manifest.get("disc_layout", "unknown"),
              "texture_count": len(images),
              "note": "TIM textures are not necessarily complete character frames.",
              "textures": images}
    if destination is not None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
