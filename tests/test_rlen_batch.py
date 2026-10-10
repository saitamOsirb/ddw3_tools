import json
import struct

from ddw3_tools.rlen_batch import extract_rlen_batch
from test_disc_files import make_iso


def test_batch_extracts_survey_hits(tmp_path):
    iso, _ = make_iso(tmp_path)
    data = bytearray(iso.read_bytes())
    payload = b"RLEN" + struct.pack("<I", 3) + bytes((3,)) + b"ABC"
    data[18 * 2048:18 * 2048 + len(payload)] = payload
    iso.write_bytes(data)
    survey = tmp_path / "survey.json"
    survey.write_text(json.dumps({"regions": [
        {"rlen_hits": [{"lba": 18, "sector_offset": 0}]}
    ]}))
    result = extract_rlen_batch(iso, survey, tmp_path / "batch")
    assert result["attempted"] == 1
    assert result["successful"] == 1
    assert (tmp_path / "batch/lba_000018_offset_0000/decoded.bin").read_bytes() == b"ABC"
    assert result["png_count"] == 0


def test_batch_deduplicates_hits(tmp_path):
    iso, _ = make_iso(tmp_path)
    survey = tmp_path / "survey.json"
    survey.write_text(json.dumps({"regions": [{"rlen_hits": [
        {"lba": 18, "sector_offset": 0}, {"lba": 18, "sector_offset": 0}
    ]}]}))
    result = extract_rlen_batch(iso, survey, tmp_path / "batch")
    assert result["available_hits"] == 1
    assert result["attempted"] == 1
    assert result["successful"] == 0
