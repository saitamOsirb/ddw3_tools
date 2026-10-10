from ddw3_tools.disc_layout import analyze_layout
from test_disc_files import make_iso


def test_layout_reports_unlisted_ranges(tmp_path):
    iso, _ = make_iso(tmp_path)
    report = analyze_layout(iso, tmp_path / "layout.json")
    assert report["total_sectors"] == 24
    assert report["listed_files"][0]["path"] == "DATA.BIN"
    assert any(r["start_lba"] <= 18 < r["end_lba_exclusive"]
               for r in report["unlisted_ranges"])
    assert all(r["sector_count"] > 0 for r in report["unlisted_ranges"])
