import json
import struct

import pytest

from ddw3_tools.frame_candidates import connected_regions, extract_candidate_frames


def test_diagonal_connected_components_and_bounds():
    rgba = bytearray(5 * 3 * 4)
    for x, y in ((0, 0), (1, 1), (4, 2)):
        rgba[(y * 5 + x) * 4 + 3] = 255
    regions = connected_regions(bytes(rgba), 5, 3, min_pixels=1)
    assert regions == [
        {"x": 0, "y": 0, "w": 2, "h": 2, "opaque_pixels": 2},
        {"x": 4, "y": 2, "w": 1, "h": 1, "opaque_pixels": 1},
    ]
    assert connected_regions(bytes(rgba), 5, 3, min_pixels=2) == regions[:1]
    with pytest.raises(ValueError):
        connected_regions(bytes(rgba), 6, 3)


def make_tim():
    # 8x2 pixels, opaque indexed pixels 1, with zero-valued transparency.
    clut_values = [0, 0x001f] + [0] * 14
    clut = struct.pack("<IHHHH", 44, 0, 0, 16, 1) + struct.pack("<16H", *clut_values)
    # Four bytes per row, left island in columns 0..1 and right in 6..7.
    image = bytes((0x11, 0, 0, 0x11)) * 2
    block = struct.pack("<IHHHH", 12 + len(image), 0, 0, 2, 2) + image
    return b"\x10\x00\x00\x00" + struct.pack("<I", 8) + clut + block


def test_candidate_export_by_lba_and_preserves_original(tmp_path):
    base = tmp_path / "rlen"
    target = base / "lba_023969_offset_0284"
    target.mkdir(parents=True)
    data = make_tim()
    (target / "decoded.bin").write_bytes(data)
    (target / "rlen_manifest.json").write_text(json.dumps({
        "lba": 23969, "sector_offset": 284
    }))
    other = base / "unrelated"
    other.mkdir()
    (other / "decoded.bin").write_bytes(data)
    output = tmp_path / "out"
    report = extract_candidate_frames(
        base, output, contains="lba_023969", min_pixels=2)
    assert report["counts"]["atlases_exported"] == 1
    assert report["counts"]["regions_exported"] == 2
    atlas = report["atlases"][0]
    assert atlas["origin"] == {"lba": 23969, "sector_offset": 284}
    assert [(r["x"], r["y"], r["w"], r["h"]) for r in atlas["palettes"][0]["regions"]] == [
        (0, 0, 2, 2), (6, 0, 2, 2)
    ]
    for region in atlas["palettes"][0]["regions"]:
        assert (output / region["png"]).read_bytes().startswith(b"\x89PNG")
    assert (target / "decoded.bin").read_bytes() == data
    assert (output / "frame_candidates.json").is_file()


def test_invalid_bounds(tmp_path):
    with pytest.raises(ValueError):
        extract_candidate_frames(tmp_path, tmp_path / "out", max_regions=0)
