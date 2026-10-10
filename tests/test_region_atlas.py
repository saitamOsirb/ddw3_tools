import struct

import pytest

from ddw3_tools.region_atlas import crop_rgba, export_region_atlas, inspect_regions


def _payload():
    pixels = b"".join(struct.pack("<H", i) for i in range(1, 9))
    tim = (b"\x10\x00\x00\x00" + struct.pack("<I", 2)
           + struct.pack("<IHHHH", 12 + len(pixels), 0, 0, 4, 2) + pixels)
    header = (struct.pack("<4I", 28, 1, 0, 0)
              + struct.pack("<6H", 2, 0, 2, 2, 0, 0))
    return header + tim


def test_exact_split_and_preserved_source_pixels():
    info, reason = inspect_regions(_payload())
    assert reason is None
    assert info["candidate_rectangles"] == [
        {"x": 0, "y": 0, "w": 2, "h": 2, "source": "last_record_u16_0"},
        {"x": 2, "y": 0, "w": 2, "h": 2, "source": "last_record_u16_2"},
    ]
    rgba = bytes(range(32))
    left = crop_rgba(rgba, 4, 2, 0, 0, 2, 2)
    right = crop_rgba(rgba, 4, 2, 2, 0, 2, 2)
    assert left == rgba[:8] + rgba[16:24]
    assert right == rgba[8:16] + rgba[24:32]


def test_atlas_exports_original_and_regions_without_touching_input(tmp_path):
    source = tmp_path / "input" / "lba_025054_offset_0000"
    source.mkdir(parents=True)
    payload = _payload()
    (source / "decoded.bin").write_bytes(payload)
    out = tmp_path / "out"
    report = export_region_atlas(tmp_path / "input", out)
    assert report["counts"]["exported"] == 1
    assert report["entries"][0]["source_pixels_preserved"] is True
    assert (out / "lba_025054_offset_0000_original.png").read_bytes().startswith(b"\x89PNG")
    assert (out / "lba_025054_offset_0000_region_01.png").read_bytes().startswith(b"\x89PNG")
    assert (source / "decoded.bin").read_bytes() == payload


def test_reject_bad_crop():
    with pytest.raises(ValueError):
        crop_rgba(bytes(32), 4, 2, 3, 0, 2, 2)
