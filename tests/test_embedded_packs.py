import json
import struct

from ddw3_tools.embedded_packs import scan_embedded_packs
from test_disc_files import make_iso


def test_embedded_scan_finds_pack_at_file_start(tmp_path):
    iso, packed = make_iso(tmp_path)
    output = tmp_path / "embedded.json"
    result = scan_embedded_packs(iso, output)
    assert result["candidates"] == 1
    assert result["hits"][0]["path"] == "DATA.BIN"
    assert result["hits"][0]["file_offset"] == 0
    assert result["hits"][0]["candidate_entries"] == 2
    assert json.loads(output.read_text()) == result


def test_embedded_scan_limits(tmp_path):
    iso, _ = make_iso(tmp_path)
    result = scan_embedded_packs(iso, tmp_path / "limited.json", max_sectors=1)
    assert result["sectors_checked"] == 1
    assert result["truncated"] is True
