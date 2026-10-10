import struct

from ddw3_tools.header_structure import inspect_header_structure


def make_tim():
    return (b"\x10\x00\x00\x00" + struct.pack("<I", 2)
            + struct.pack("<IHHHH", 16, 320, 64, 2, 1)
            + b"\x1f\x00\xe0\x03")


def make_header(size=28, first_word=None):
    assert size >= 16 and (size - 16) % 12 == 0
    fields = [size if first_word is None else first_word, 1, 2, 3]
    result = struct.pack("<4I", *fields)
    result += struct.pack("<3I", 4, 5, 6) * ((size - 16) // 12)
    return result


def test_header_structure_verifies_shape_and_length(tmp_path):
    for name, header in (
        ("a", make_header(28)),
        ("b", make_header(40)),
        ("c", make_header(28, first_word=999)),
        ("d", b"\x00" * 17),
        ("e", b""),
    ):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "decoded.bin").write_bytes(header + make_tim())
    report = inspect_header_structure(tmp_path, tmp_path / "report.json")
    counts = report["counts"]
    assert counts["files"] == 5
    assert counts["with_prefix"] == 4
    assert counts["no_prefix"] == 1
    assert counts["shape_match"] == 3
    assert counts["shape_mismatch"] == 1
    assert counts["length_match"] == 2
    assert counts["length_mismatch"] == 1
    assert counts["records"] == 4
    assert report["second_word_distribution"][0] == {"value": 1, "count": 3}
    assert report["examples"][0]["records_u32le"] == [[4, 5, 6]]


def test_header_structure_rejects_missing_directory(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        inspect_header_structure(tmp_path / "missing", tmp_path / "out.json")
