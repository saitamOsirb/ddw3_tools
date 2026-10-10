import json
import struct

from ddw3_tools.sprite_candidates import export_sprite_candidates


def tim_4bpp():
    palette = struct.pack("<16H", *range(16))
    clut = struct.pack("<IHHHH", 12 + len(palette), 0, 0, 16, 1) + palette
    # Four 4-bit indices, two bytes of packed pixels.
    pixels = b"\x10\x32"
    image = struct.pack("<IHHHH", 12 + len(pixels), 0, 0, 1, 1) + pixels
    return b"\x10\x00\x00\x00" + struct.pack("<I", 8) + clut + image


def test_candidates_export_4bpp_png_and_metadata(tmp_path):
    folder = tmp_path / "input" / "lba_023969_offset_0284"
    folder.mkdir(parents=True)
    data = tim_4bpp()
    (folder / "decoded.bin").write_bytes(data)
    (folder / "rlen_manifest.json").write_text(json.dumps({
        "lba": 23969, "sector_offset": 284
    }))
    output = tmp_path / "output"
    report = export_sprite_candidates(tmp_path / "input", output)
    assert report["candidate_count"] == 1
    entry = report["candidates"][0]
    assert (entry["width"], entry["height"], entry["bpp"]) == (4, 1, 4)
    assert entry["origin"] == {"lba": 23969, "sector_offset": 284}
    assert (output / entry["pngs"][0]).read_bytes().startswith(b"\x89PNG")
    assert (folder / "decoded.bin").read_bytes() == data


def test_candidates_ignore_unrelated_data(tmp_path):
    folder = tmp_path / "input"
    folder.mkdir()
    (folder / "decoded.bin").write_bytes(b"not a tim")
    report = export_sprite_candidates(folder, tmp_path / "out")
    assert report["candidate_count"] == 0
    assert report["counts"]["not_tim_at_start"] == 1
