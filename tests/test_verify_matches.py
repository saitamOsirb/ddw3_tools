import json
import struct

import pytest

from ddw3_tools.verify_matches import verify_atlas_matches


def _tim():
    # 8x1 pixels, first two red, remaining transparent. Two different CLUTs.
    colors = [0, 0x001f] + [0] * 14
    palettes = (struct.pack("<16H", *colors) * 2
                + struct.pack("<16H", *([0] * 16)))
    clut = struct.pack("<IHHHH", 12 + len(palettes), 0, 0, 16, 3) + palettes
    pixels = bytes((0x11, 0, 0, 0))
    block = struct.pack("<IHHHH", 12 + len(pixels), 0, 0, 2, 1) + pixels
    return b"\x10\x00\x00\x00" + struct.pack("<I", 8) + clut + block


def test_verifies_indices_and_all_palette_pairings(tmp_path):
    root = tmp_path / "rlen"
    for lba, offset in ((24233, 540), (24241, 668)):
        folder = root / f"lba_{lba:06d}_offset_{offset:04d}"
        folder.mkdir(parents=True)
        (folder / "decoded.bin").write_bytes(_tim())
    aligned = tmp_path / "aligned"
    aligned.mkdir()
    (aligned / "aligned_candidates.json").write_text(json.dumps({
        "source": "lba_024241_offset_0668/decoded.bin",
        "groups": [{"id": 0, "box": {"x": 0, "y": 0, "w": 2, "h": 1}}],
    }))
    matching = tmp_path / "matches.json"
    matching.write_text(json.dumps({
        "large": {"lba": 24233, "offset": 540, "size": [8, 1]},
        "small": {"lba": 24241, "offset": 668, "size": [8, 1]},
        "groups": [{"id": 0, "box": {"x": 0, "y": 0, "w": 2, "h": 1},
                    "palettes": [{"small_palette": 0, "large_palette": 0,
                                  "matches": [{"x": 0, "y": 0}]}]}],
    }))
    out = tmp_path / "report"
    result = verify_atlas_matches(root, aligned, matching, out)
    finding = result["findings"][0]
    assert finding["exact_indexed_pixels"]
    assert len(finding["palette_pairings_with_matching_alpha"]) == 4
    assert all(x["exact_visible_rgba"] and x["visible_pixels"] > 0
               for x in finding["palette_pairings_with_matching_alpha"])
    assert finding["best_visible_rgba_pairing"]["visible_pixels"] == 2
    assert finding["best_visible_rgba_pairing"]["small_palette"] == 0
    assert result["summary"] == {
        "verified_locations": 1, "exact_indexed": 1, "exact_visible_rgba": 1
    }
    assert json.loads((out / "verified_matches.json").read_text())["findings"][0]["indexed_pixels_equal"] == 2


def test_rejects_incorrect_match(tmp_path):
    with pytest.raises(ValueError):
        verify_atlas_matches(tmp_path, tmp_path, tmp_path / "missing.json",
                             tmp_path / "out", max_palettes=0)
