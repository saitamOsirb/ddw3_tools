import json
import struct

import pytest

from ddw3_tools.related_atlases import locate_exact_regions, compare_related_atlases


def _image(w, h, points, color=(255, 0, 0, 255)):
    data = bytearray(w * h * 4)
    for x, y in points:
        data[(y * w + x) * 4:(y * w + x) * 4 + 4] = bytes(color)
    return bytes(data)


def test_translated_alpha_and_rgba_matches():
    small = _image(5, 5, {(1, 1), (2, 1), (1, 2)})
    large = _image(9, 9, {(4, 3), (5, 3), (4, 4)})
    box = {"x": 1, "y": 1, "w": 2, "h": 2}
    result = locate_exact_regions(small, 5, 5, box, large, 9, 9, min_opaque=3)
    assert result["opaque_pixels"] == 3
    assert result["matches"] == [
        {"x": 4, "y": 3, "exact_alpha": True, "exact_visible_rgba": True}]
    recolored = _image(9, 9, {(4, 3), (5, 3), (4, 4)}, (0, 255, 0, 255))
    other = locate_exact_regions(small, 5, 5, box, recolored, 9, 9, min_opaque=3)
    assert len(other["matches"]) == 1
    assert not other["matches"][0]["exact_visible_rgba"]


def test_no_false_match_for_different_shape_and_tiny_groups():
    small = _image(5, 5, {(1, 1), (2, 1), (1, 2)})
    large = _image(9, 9, {(4, 3), (5, 3), (5, 4)})
    box = {"x": 1, "y": 1, "w": 2, "h": 2}
    assert locate_exact_regions(small, 5, 5, box, large, 9, 9, min_opaque=3)["matches"] == []
    assert not locate_exact_regions(small, 5, 5, box, large, 9, 9, min_opaque=4)["eligible"]
    with pytest.raises(ValueError):
        locate_exact_regions(small, 5, 5, {"x": 4, "y": 4, "w": 2, "h": 2},
                             large, 9, 9)


def _tim():
    pal = struct.pack("<16H", 0, 0x001f, *([0] * 14))
    clut = struct.pack("<IHHHH", 12 + len(pal), 0, 0, 16, 1) + pal
    # 8x1 indexed pixels: red, red, empty, empty, ...
    pixels = b"\x11\x00\x00\x00"
    image = struct.pack("<IHHHH", 12 + len(pixels), 0, 0, 2, 1) + pixels
    return b"\x10\x00\x00\x00" + struct.pack("<I", 8) + clut + image


def test_related_atlas_report_and_pngs(tmp_path):
    root = tmp_path / "rlen"
    for lba, offset in ((24233, 540), (24241, 668)):
        folder = root / f"lba_{lba:06d}_offset_{offset:04d}"
        folder.mkdir(parents=True)
        (folder / "decoded.bin").write_bytes(_tim())
    aligned = tmp_path / "aligned"
    aligned.mkdir()
    (aligned / "aligned_candidates.json").write_text(json.dumps({
        "source": "lba_024241_offset_0668/decoded.bin",
        "atlas_size": [8, 1],
        "palettes": [{"palette": 0, "status": "partial"}],
        "groups": [{"id": 0, "box": {"x": 0, "y": 0, "w": 2, "h": 1}}],
    }))
    output = tmp_path / "out"
    report = compare_related_atlases(root, aligned, output, min_opaque=2)
    assert report["groups"][0]["palettes"][0]["matches"][0]["exact_visible_rgba"]
    assert (output / "related_atlases.json").is_file()
    assert (output / "large_palette0.png").read_bytes().startswith(bytes((137, 80, 78, 71)))
    assert (output / "small_palette0.png").is_file()
