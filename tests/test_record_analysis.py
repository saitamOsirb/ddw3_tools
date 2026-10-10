import struct

from ddw3_tools.record_analysis import analyze_records


def make_tim(width_words=128, height=128):
    pixels = bytes(width_words * height * 2)
    return (b"\x10\x00\x00\x00" + struct.pack("<I", 2)
            + struct.pack("<IHHHH", 12 + len(pixels), 0, 0, width_words, height)
            + pixels)


def make_header(width_match=True):
    # 16-byte common prefix + two 12-byte records.
    first = struct.pack("<4I", 40, 1, 82, 0)
    row1 = struct.pack("<6H", 46, 23, 1, 0, 0, 0)
    row2 = struct.pack("<6H", 46, 0, 82 if width_match else 80, 128, 0, 0)
    return first + row1 + row2


def test_u16_records_match_tim_width_when_supported(tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "decoded.bin").write_bytes(make_header() + make_tim())
    b = tmp_path / "b"
    b.mkdir()
    (b / "decoded.bin").write_bytes(make_header(False) + make_tim())
    report = analyze_records(tmp_path, tmp_path / "records.json")
    assert report["counts"]["valid_headers"] == 2
    assert report["counts"]["last_record_width_match"] == 1
    assert report["counts"]["last_record_height_fits"] == 2
    assert report["record_count_distribution"] == [{"records": 2, "files": 2}]
    assert report["examples"][0]["records_u16le"][1] == [46, 0, 82, 128, 0, 0]


def test_no_header_not_assumed(tmp_path):
    (tmp_path / "decoded.bin").write_bytes(make_tim())
    report = analyze_records(tmp_path, tmp_path / "out.json")
    assert report["counts"]["no_header"] == 1
    assert report["counts"].get("valid_headers", 0) == 0
