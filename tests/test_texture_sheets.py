import struct

from ddw3_tools.texture_sheets import _sample_evenly, build_texture_sheets


def _tim(words=4, height=2):
    raw = b"".join(struct.pack("<H", x) for x in range(words * height))
    return (b"\x10\x00\x00\x00" + struct.pack("<I", 2)
            + struct.pack("<IHHHH", 12 + len(raw), 0, 0, words, height) + raw)


def test_sample_evenly_spans_full_group():
    assert _sample_evenly(list(range(100)), 3) == [0, 49, 99]
    assert _sample_evenly(list(range(3)), 5) == [0, 1, 2]


def test_texture_sheets_create_png_and_provenance(tmp_path):
    root = tmp_path / "resources"
    for i in range(5):
        folder = root / f"lba_{i:06d}_offset_0000"
        folder.mkdir(parents=True)
        (folder / "decoded.bin").write_bytes(_tim())
    output = tmp_path / "sheets"
    result = build_texture_sheets(root, output, per_group=3, tile=32, columns=2)
    assert result["errors"] == 0
    assert len(result["sheets"]) == 1
    group = result["sheets"][0]
    assert group["available"] == 5
    assert group["sampled"] == 3
    assert group["entries"][0]["file"] == "lba_000000_offset_0000/decoded.bin"
    assert group["entries"][-1]["file"] == "lba_000004_offset_0000/decoded.bin"
    assert (output / group["sheet"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert (output / "texture_sheets.json").is_file()


def test_texture_sheets_invalid_limits(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        build_texture_sheets(tmp_path, tmp_path / "out", per_group=0)
