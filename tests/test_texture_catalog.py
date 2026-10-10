import struct

from ddw3_tools.texture_catalog import catalog_textures


def make_tim(words=4, height=2):
    pixels = bytes(words * height * 2)
    return (b"\x10\x00\x00\x00" + struct.pack("<I", 2)
            + struct.pack("<IHHHH", 12 + len(pixels), 0, 0, words, height)
            + pixels)


def test_texture_catalog_groups_without_asset_guessing(tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "decoded.bin").write_bytes(make_tim())
    b = tmp_path / "b"
    b.mkdir()
    prefix = struct.pack("<4I", 28, 1, 0, 0) + struct.pack("<6H", 2, 0, 2, 2, 0, 0)
    (b / "decoded.bin").write_bytes(prefix + make_tim(2, 2))
    report = catalog_textures(tmp_path, tmp_path / "catalog.json")
    assert len(report["textures"]) == 2
    assert report["counts"]["16bpp/tim_only/landscape"] == 1
    assert report["counts"]["16bpp/tim_with_header/square"] == 1
    assert all(item["identification"] == "unknown" for item in report["textures"])


def test_catalog_limits(tmp_path):
    for name in ("a", "b"):
        d = tmp_path / name
        d.mkdir()
        (d / "decoded.bin").write_bytes(make_tim())
    report = catalog_textures(tmp_path, tmp_path / "limited.json", max_files=1)
    assert report["files_examined"] == 1
    assert report["truncated"] is True
