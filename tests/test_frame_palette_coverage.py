import struct

from ddw3_tools.frame_candidates import extract_candidate_frames


def _tim(palette_values):
    clut = struct.pack("<IHHHH", 44, 0, 0, 16, 1) + struct.pack("<16H", *palette_values)
    # 8 x 2 indexed pixels, all index 1
    raw = bytes((0x11, 0x11, 0x11, 0x11)) * 2
    block = struct.pack("<IHHHH", 12 + len(raw), 0, 0, 2, 2) + raw
    return b"\x10\x00\x00\x00" + struct.pack("<I", 8) + clut + block


def test_nearly_opaque_palette_reported_not_segmented(tmp_path):
    folder = tmp_path / "resources" / "lba_000001_offset_0000"
    folder.mkdir(parents=True)
    (folder / "decoded.bin").write_bytes(_tim([0, 0x7fff] + [0] * 14))
    result = extract_candidate_frames(tmp_path / "resources", tmp_path / "out")
    assert result["counts"]["full_coverage_palettes"] == 1
    assert result["counts"].get("regions_exported", 0) == 0
    palette = result["atlases"][0]["palettes"][0]
    assert palette["status"] == "nearly_opaque"
    assert palette["coverage"] == 1.0
    assert palette["regions"] == []


def test_empty_palette_reported_not_segmented(tmp_path):
    folder = tmp_path / "resources" / "lba_000002_offset_0000"
    folder.mkdir(parents=True)
    (folder / "decoded.bin").write_bytes(_tim([0] * 16))
    result = extract_candidate_frames(tmp_path / "resources", tmp_path / "out")
    assert result["counts"]["empty_palettes"] == 1
    assert result["atlases"][0]["palettes"][0]["status"] == "empty"
