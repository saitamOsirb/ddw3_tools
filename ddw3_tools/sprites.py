"""Conservative PlayStation TIM scanner and PNG exporter (standard library only)."""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

MAGIC = b"\x10\x00\x00\x00"
MODES = {0: 4, 1: 8, 2: 16, 3: 24}


def u32(data: bytes, pos: int) -> int:
    return struct.unpack_from("<I", data, pos)[0]


def parse_tim(data: bytes, offset: int) -> dict | None:
    """Validate one complete TIM structure at offset, without guessing dimensions."""
    if offset + 8 > len(data) or data[offset:offset + 4] != MAGIC:
        return None
    flags = u32(data, offset + 4)
    mode = flags & 7
    if mode not in MODES or flags & ~15:
        return None
    pos = offset + 8
    palettes = []
    if flags & 8:
        block = _block(data, pos)
        if block is None:
            return None
        _, _, cw, ch, raw, pos = block
        if mode not in (0, 1) or cw == 0 or ch == 0 or len(raw) != cw * ch * 2:
            return None
        count = 16 if mode == 0 else 256
        if cw * ch % count:
            return None
        values = struct.unpack("<" + "H" * (cw * ch), raw)
        palettes = [values[i:i + count] for i in range(0, len(values), count)]
    elif mode in (0, 1):
        return None
    block = _block(data, pos)
    if block is None:
        return None
    _, _, words, height, pixels, end = block
    if not words or not height or words > 4096 or height > 4096:
        return None
    stride = words * 2
    if mode == 24 and stride % 3:
        return None
    width = stride * 8 // MODES[mode]
    if width < 1 or width > 8192:
        return None
    return {"offset": offset, "end": end, "width": width, "height": height,
            "bpp": MODES[mode], "stride": stride, "pixels": pixels, "palettes": palettes}


def _block(data: bytes, pos: int):
    if pos + 12 > len(data):
        return None
    size = u32(data, pos)
    if size < 12 or pos + size > len(data):
        return None
    x, y, w, h = struct.unpack_from("<HHHH", data, pos + 4)
    if not w or not h or size != 12 + w * h * 2:
        return None
    return x, y, w, h, data[pos + 12:pos + size], pos + size


def color(value: int, *, transparent_zero: bool = False) -> bytes:
    if transparent_zero and value == 0:
        return bytes((0, 0, 0, 0))
    r = (value & 31) * 255 // 31
    g = ((value >> 5) & 31) * 255 // 31
    b = ((value >> 10) & 31) * 255 // 31
    return bytes((r, g, b, 255))


def rgba(tim: dict, palette_index: int = 0) -> bytes:
    width, height, stride = tim["width"], tim["height"], tim["stride"]
    mode, pixels = tim["bpp"], tim["pixels"]
    pal = tim["palettes"][palette_index] if tim["palettes"] else None
    result = bytearray()
    for y in range(height):
        row = pixels[y * stride:(y + 1) * stride]
        if mode == 4:
            indices = [v for byte in row for v in (byte & 15, byte >> 4)]
        elif mode == 8:
            indices = row
        elif mode == 16:
            indices = struct.unpack("<" + "H" * (len(row) // 2), row)
        else:
            indices = None
        if mode == 24:
            for x in range(width):
                result.extend(row[x * 3:x * 3 + 3])
                result.append(255)
        else:
            for index in indices[:width]:
                result.extend(color(pal[index] if pal else index, transparent_zero=pal is not None))
    return bytes(result)


def write_png(path: Path, width: int, height: int, pixels: bytes) -> None:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff)
    scanlines = b"".join(b"\x00" + pixels[y * width * 4:(y + 1) * width * 4] for y in range(height))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" +
                     chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) +
                     chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b""))


def extract_sprites(source: Path, output: Path, *, max_images: int = 10000) -> dict:
    """Scan raw bytes for valid TIM structures; extracted images may be textures, not sprites."""
    if max_images < 1:
        raise ValueError("--max-images debe ser mayor que cero")
    output.mkdir(parents=True, exist_ok=True)
    data = source.read_bytes()
    records = []
    offset = 0
    while len(records) < max_images:
        offset = data.find(MAGIC, offset)
        if offset < 0:
            break
        tim = parse_tim(data, offset)
        if tim is None:
            offset += 4
            continue
        files = []
        for i in range(max(1, len(tim["palettes"]))):
            name = f"tim_{offset:08x}_pal_{i:03d}.png"
            write_png(output / name, tim["width"], tim["height"], rgba(tim, i))
            files.append(name)
        records.append({"offset": offset, "length": tim["end"] - offset,
                        "width": tim["width"], "height": tim["height"],
                        "bpp": tim["bpp"], "palette_count": len(tim["palettes"]),
                        "files": files})
        offset = tim["end"]
    manifest = {"source": str(source), "tim_count": len(records),
                "png_count": sum(len(r["files"]) for r in records),
                "truncated": len(records) == max_images, "images": records}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
