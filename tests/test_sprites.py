import json
import struct
import zlib

from ddw3_tools.sprites import MAGIC, parse_tim, rgba, extract_sprites


def block(width, height, pixels):
    return struct.pack("<IHHHH", 12 + len(pixels), 0, 0, width, height) + pixels


def test_tim_16bit(tmp_path):
    image = MAGIC + struct.pack("<I", 2) + block(1, 1, struct.pack("<H", 31))
    tim = parse_tim(image, 0)
    assert (tim["width"], tim["height"], tim["bpp"]) == (1, 1, 16)
    assert rgba(tim) == bytes((255, 0, 0, 255))
    source = tmp_path / "test.bin"
    source.write_bytes(b"prefix" + image)
    result = extract_sprites(source, tmp_path / "out")
    assert result["tim_count"] == result["png_count"] == 1
    assert result["images"][0]["offset"] == 6
    png = (tmp_path / "out" / result["images"][0]["files"][0]).read_bytes()
    assert png.startswith(bytes((137, 80, 78, 71, 13, 10, 26, 10)))
    assert json.loads((tmp_path / "out" / "manifest.json").read_text())["tim_count"] == 1


def test_tim_4bit_two_palettes():
    palette = [0, 31] + [0] * 14 + [0, 992] + [0] * 14
    image = MAGIC + struct.pack("<I", 8) + block(16, 2, struct.pack("<32H", *palette)) + block(1, 1, bytes((0x10, 0, 0, 0)))
    tim = parse_tim(image, 0)
    assert tim["width"] == 4 and len(tim["palettes"]) == 2
    assert rgba(tim, 0)[4:8] == bytes((255, 0, 0, 255))
    assert rgba(tim, 1)[4:8] == bytes((0, 0, 255, 255))


def test_reject_truncated():
    assert parse_tim(MAGIC + bytes(4), 0) is None
