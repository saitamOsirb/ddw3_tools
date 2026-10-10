import json

import pytest

from ddw3_tools.frame_grouping import group_regions, export_grouped_candidates
from test_frame_candidates import make_tim


def test_nearby_components_merge_but_distant_do_not():
    regions = [
        {"x": 0, "y": 0, "w": 3, "h": 3, "opaque_pixels": 7},
        {"x": 5, "y": 0, "w": 2, "h": 2, "opaque_pixels": 4},
        {"x": 30, "y": 0, "w": 2, "h": 2, "opaque_pixels": 4},
    ]
    groups = group_regions(regions, gap=2, max_width=12, max_height=12)
    assert len(groups) == 2
    assert groups[0]["members"] == [0, 1]
    assert groups[0]["x"] == 0 and groups[0]["w"] == 7
    assert groups[1]["members"] == [2]


def test_maximum_bounds_prevent_merging():
    regions = [
        {"x": 0, "y": 0, "w": 3, "h": 2},
        {"x": 5, "y": 0, "w": 3, "h": 2},
    ]
    assert len(group_regions(regions, gap=3, max_width=7)) == 2
    with pytest.raises(ValueError):
        group_regions(regions, gap=-1)


def test_export_grouped_pngs_with_original_coordinates(tmp_path):
    root = tmp_path / "rlen"
    folder = root / "lba_023969_offset_0284"
    folder.mkdir(parents=True)
    raw = make_tim()
    (folder / "decoded.bin").write_bytes(raw)
    (folder / "rlen_manifest.json").write_text(json.dumps({
        "lba": 23969, "sector_offset": 284
    }))
    out = tmp_path / "grouped"
    report = export_grouped_candidates(
        root, out, contains="lba_023969", gap=3, min_pixels=2)
    assert report["origin"] == {"lba": 23969, "sector_offset": 284}
    assert report["counts"]["components"] == 2
    assert report["counts"]["groups"] == 2
    assert report["palettes"][0]["status"] == "partial"
    assert len(report["palettes"][0]["groups"]) == 2
    for item in report["palettes"][0]["groups"]:
        assert (out / item["png"]).read_bytes().startswith(b"\x89PNG")
    assert (folder / "decoded.bin").read_bytes() == raw
    assert (out / "grouped_candidates.json").is_file()


def test_filter_must_resolve_single_atlas(tmp_path):
    root = tmp_path / "rlen"
    for name in ("lba_023969_a", "lba_023969_b"):
        folder = root / name
        folder.mkdir(parents=True)
        (folder / "decoded.bin").write_bytes(make_tim())
    with pytest.raises(ValueError):
        export_grouped_candidates(root, tmp_path / "out", contains="lba_023969")
