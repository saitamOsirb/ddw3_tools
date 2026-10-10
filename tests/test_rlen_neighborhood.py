import json
import struct

import pytest

from ddw3_tools.rlen_neighborhood import inspect_rlen_neighborhood


def _disc(tmp_path):
    sectors = [bytearray(2048) for _ in range(6)]
    sectors[1][100:108] = b"RLEN" + struct.pack("<I", 65536)
    sectors[2][80:88] = b"RLEN" + struct.pack("<I", 77)
    sectors[2][100:104] = b"ABCD"
    path = tmp_path / "sample.iso"
    path.write_bytes(b"".join(sectors))
    return path


def test_neighborhood_reports_exact_markers_and_bytes(tmp_path):
    disc = _disc(tmp_path)
    out = tmp_path / "report.json"
    result = inspect_rlen_neighborhood(disc, out, lba=2, offset=80,
                                       radius=1, sample_bytes=16)
    assert result["range_lba_inclusive"] == [1, 3]
    assert result["target"]["declared_decoded_bytes"] == 77
    assert result["target"]["header_hex"] == (b"RLEN" + struct.pack("<I", 77)).hex()
    assert [(x["lba"], x["offset"]) for x in result["signatures"]] == [(1, 100), (2, 80)]
    assert len(result["sectors"]) == 3
    assert json.loads(out.read_text())["target"]["offset"] == 80


def test_rejects_false_marker_and_bad_limits(tmp_path):
    disc = _disc(tmp_path)
    with pytest.raises(ValueError, match="No hay firma"):
        inspect_rlen_neighborhood(disc, tmp_path / "bad.json", lba=2, offset=81)
    with pytest.raises(ValueError):
        inspect_rlen_neighborhood(disc, tmp_path / "bad.json", lba=2, offset=80, radius=129)
