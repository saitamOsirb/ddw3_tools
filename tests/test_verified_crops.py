import json
import struct

import pytest

from ddw3_tools.verified_crops import export_verified_crops


def _tim():
    pal = struct.pack("<16H", 0, 0x001f, *([0] * 14))
    clut = struct.pack("<IHHHH", 12 + len(pal), 0, 0, 16, 1) + pal
    pixels = bytes((0x11, 0, 0, 0))
    block = struct.pack("<IHHHH", 12 + len(pixels), 0, 0, 2, 1) + pixels
    return b"\x10\x00\x00\x00" + struct.pack("<I", 8) + clut + block


def test_exports_verified_original_crops(tmp_path):
    root = tmp_path / "rlen"
    folder = root / "lba_024233_offset_0540"
    folder.mkdir(parents=True)
    original = _tim()
    (folder / "decoded.bin").write_bytes(original)
    verified = tmp_path / "verified.json"
    verified.write_text(json.dumps({
        "large": {"lba": 24233, "offset": 540, "size": [8, 1]},
        "findings": [{"group_id": 1, "large_xy": [0, 0],
                      "small_box": {"w": 2, "h": 1},
                      "exact_indexed_pixels": True}],
    }))
    output = tmp_path / "out"
    result = export_verified_crops(root, verified, output)
    assert result["entries"][0]["visible_pixels"] == 2
    assert result["entries"][0]["source_box"] == {"x": 0, "y": 0, "w": 2, "h": 1}
    assert (output / "verified_group_001_pal_000.png").read_bytes().startswith(bytes((137, 80, 78, 71)))
    assert (output / "verified_crops.json").is_file()
    assert (folder / "decoded.bin").read_bytes() == original


def test_rejects_out_of_bounds_crop(tmp_path):
    root = tmp_path / "rlen"
    folder = root / "lba_024233_offset_0540"
    folder.mkdir(parents=True)
    (folder / "decoded.bin").write_bytes(_tim())
    verified = tmp_path / "verified.json"
    verified.write_text(json.dumps({
        "large": {"lba": 24233, "offset": 540, "size": [8, 1]},
        "findings": [{"group_id": 0, "large_xy": [7, 0],
                      "small_box": {"w": 2, "h": 1},
                      "exact_indexed_pixels": True}],
    }))
    with pytest.raises(ValueError, match="limites"):
        export_verified_crops(root, verified, tmp_path / "out")
