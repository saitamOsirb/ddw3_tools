import struct

from ddw3_tools.disc_survey import survey_regions
from test_disc_files import make_iso


def test_survey_unlisted_sector_signature(tmp_path):
    iso, _ = make_iso(tmp_path)
    data = bytearray(iso.read_bytes())
    data[18 * 2048:18 * 2048 + 8] = b"RLENtest"
    iso.write_bytes(data)
    report = survey_regions(iso, tmp_path / "survey.json")
    assert report["rlen_total"] == 1
    hits = [hit for region in report["regions"] for hit in region["rlen_hits"]]
    assert hits[0]["lba"] == 18
    assert hits[0]["sector_offset"] == 0
