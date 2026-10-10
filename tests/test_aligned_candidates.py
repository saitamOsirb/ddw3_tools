import json
import struct

import pytest

from ddw3_tools.aligned_candidates import export_aligned_candidates


def make_two_palette_tim():
    pal0 = [0, 0x001f] + [0] * 14
    pal1 = [0, 0, 0x03e0] + [0] * 13
    clut = struct.pack("<IHHHH", 12 + 64, 0, 0, 16, 2)
    clut += struct.pack("<16H", *pal0) + struct.pack("<16H", *pal1)
    # One row (8 pixels): palette0 sees 1s, palette1 sees 2s.
    raw = bytes((0x11, 0, 0x22, 0))
    image = struct.pack("<IHHHH", 12 + len(raw), 0, 0, 2, 1) + raw
    return b"\x10\x00\x00\x00" + struct.pack("<I", 8) + clut + image


def test_shared_bounds_across_palette_variants(tmp_path):
    folder = tmp_path / "rlen" / "lba_024241_offset_0668"
    folder.mkdir(parents=True)
    original = make_two_palette_tim()
    (folder / "decoded.bin").write_bytes(original)
    (folder / "rlen_manifest.json").write_text(json.dumps({"lba": 24241}))
    output = tmp_path / "aligned"
    report = export_aligned_candidates(
        tmp_path / "rlen", output, contains="lba_024241",
        gap=0, min_pixels=1)
    assert report["origin"]["lba"] == 24241
    assert report["aligned_group_count"] == 2
    assert [p["status"] for p in report["palettes"]] == ["partial", "partial"]
    for g in report["groups"]:
        assert len(g["variants"]) == 2
        assert sum(v["status"] == "exported" for v in g["variants"]) == 1
        for v in g["variants"]:
            if "png" in v:
                assert (output / v["png"]).read_bytes().startswith(b"\x89PNG")
    assert (output / "aligned_candidates.json").is_file()
    assert (folder / "decoded.bin").read_bytes() == original


def test_align_rejects_ambiguous_filter_and_invalid_limits(tmp_path):
    with pytest.raises(ValueError):
        export_aligned_candidates(tmp_path, tmp_path / "out", contains="", gap=0)
    root = tmp_path / "rlen"
    root.mkdir()
    with pytest.raises(ValueError):
        export_aligned_candidates(root, tmp_path / "out", contains="lba_")
