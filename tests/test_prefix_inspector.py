import json
import struct

from ddw3_tools.prefix_inspector import inspect_prefixes


def _tim():
    return (b"\x10\x00\x00\x00" + struct.pack("<I", 2)
            + struct.pack("<IHHHH", 16, 320, 64, 2, 1)
            + b"\x1f\x00\xe0\x03")


def test_groups_prefix_sizes_and_reports_raw_fields(tmp_path):
    for name, prefix in (("a", bytes(range(40))), ("b", bytes(range(40))),
                         ("c", bytes(range(52))), ("d", b"")):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "decoded.bin").write_bytes(prefix + _tim())
    output = tmp_path / "headers.json"
    result = inspect_prefixes(tmp_path, output)
    assert result["files_scanned"] == 4
    assert result["files_without_prefix"] == 1
    assert result["prefix_lengths"][0] == {"bytes": 40, "count": 2}
    assert result["prefix_lengths"][1] == {"bytes": 52, "count": 1}
    assert result["trailing_lengths"] == [{"bytes": 0, "count": 4}]
    assert len(result["families"]) == 2
    assert result["families"][0]["examples"][0]["u32le"][0] == 0x03020100
    assert json.loads(output.read_text()) == result


def test_trailing_content_does_not_count_as_header(tmp_path):
    folder = tmp_path / "a"
    folder.mkdir()
    (folder / "decoded.bin").write_bytes(bytes(40) + _tim() + b"EXTRA")
    result = inspect_prefixes(tmp_path, tmp_path / "out.json")
    assert result["trailing_lengths"] == [{"bytes": 5, "count": 1}]
