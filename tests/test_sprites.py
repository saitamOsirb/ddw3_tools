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
    palette = [0, 31] + [0] * 14 + [0, 31744] + [0] * 14
    image = MAGIC + struct.pack("<I", 8) + block(16, 2, struct.pack("<32H", *palette)) + block(1, 1, bytes((0x10, 0)))
    tim = parse_tim(image, 0)
    assert tim["width"] == 4 and len(tim["palettes"]) == 2
    assert rgba(tim, 0)[4:8] == bytes((255, 0, 0, 255))
    assert rgba(tim, 1)[4:8] == bytes((0, 0, 255, 255))


def test_reject_truncated():
    assert parse_tim(MAGIC + bytes(4), 0) is None


def test_raw_mode2_form1_tim_crosses_sector(tmp_path):
    """Sector headers must never appear inside decoded TIM pixels."""
    # A 16-bit TIM with 1100 pixels spans two logical sectors.
    pixels = struct.pack("<1100H", *([31] * 1100))
    image = MAGIC + struct.pack("<I", 2) + block(1100, 1, pixels)
    payload = bytes(2000) + image
    payload += bytes((-len(payload)) % 2048)

    def sector(chunk):
        header = b"\x00" + b"\xff" * 10 + b"\x00"
        return (header + bytes((0, 0, 0, 2)) +
                bytes((0, 0, 0, 0)) * 2 + chunk + bytes(280))

    disc = tmp_path / "disc.bin"
    disc.write_bytes(b"".join(sector(payload[i:i + 2048])
                              for i in range(0, len(payload), 2048)))
    out = tmp_path / "out"
    manifest = extract_sprites(disc, out)
    assert manifest["disc_layout"] == "raw2352"
    assert manifest["tim_count"] == 1
    item = manifest["images"][0]
    assert item["logical_offset"] == 2000
    assert item["offset"] == 24 + 2000
    assert item["width"] == 1100
    assert item["height"] == 1


def test_plain_tim_still_supported(tmp_path):
    image = MAGIC + struct.pack("<I", 2) + block(1, 1, struct.pack("<H", 31))
    disc = tmp_path / "plain.iso"
    disc.write_bytes(image)
    manifest = extract_sprites(disc, tmp_path / "out")
    assert manifest["disc_layout"] == "plain"
    assert manifest["tim_count"] == 1


def test_tim_positions_and_external_palette():
    # Indexed TIM without embedded CLUT can be decoded only with a supplied palette.
    pixels = bytes((0x10, 0x00))
    image = MAGIC + struct.pack("<I", 0) + struct.pack("<IHHHH", 14, 12, 34, 1, 1) + pixels
    assert parse_tim(image, 0) is None
    palette = tuple([0, 31] + [0] * 14)
    tim = parse_tim(image, 0, external_palette=palette)
    assert tim is not None
    assert tim["image_position"] == [12, 34]
    assert tim["clut_position"] is None
    assert tim["external_palette"] is True
    assert rgba(tim)[4:8] == bytes((255, 0, 0, 255))
    assert parse_tim(image, 0, external_palette=(0, 31)) is None


def test_embedded_clut_positions_and_truncated_blocks():
    palette = struct.pack("<16H", *([0, 31] + [0] * 14))
    clut = struct.pack("<IHHHH", 12 + len(palette), 100, 200, 16, 1) + palette
    img = struct.pack("<IHHHH", 14, 50, 60, 1, 1) + bytes((0x10, 0))
    image = MAGIC + struct.pack("<I", 8) + clut + img
    tim = parse_tim(image, 0)
    assert tim["clut_position"] == [100, 200]
    assert tim["image_position"] == [50, 60]
    assert tim["external_palette"] is False
    assert parse_tim(image[:-1], 0) is None
