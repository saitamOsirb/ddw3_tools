import struct

from ddw3_tools.region_preview import preview_regions, split_preview


def make_tim():
    # 16-bit image, 4 pixels x 2 rows. Pixels have distinct values.
    image = b"".join(struct.pack("<H", i) for i in range(1, 9))
    return (b"\x10\x00\x00\x00" + struct.pack("<I", 2)
            + struct.pack("<IHHHH", 12 + len(image), 0, 0, 4, 2) + image)


def make_payload(split=2):
    header = struct.pack("<4I", 28, 1, 0, 0)
    header += struct.pack("<6H", split, 0, 4 - split, 2, 0, 0)
    return header + make_tim()


def test_preview_lossless_split_and_stack():
    preview, reason = split_preview(make_payload())
    assert reason is None
    assert (preview["width"], preview["height"]) == (2, 4)
    assert preview["left_width"] == 2
    assert preview["right_width"] == 2
    assert len(preview["rgba"]) == 2 * 4 * 4


def test_preview_rejects_invalid_geometry():
    result, reason = split_preview(make_payload(split=0))
    assert result is None
    assert reason == "split_does_not_cover_tim"
    result, reason = split_preview(make_tim())
    assert result is None
    assert reason == "invalid_header"


def test_previews_write_only_output(tmp_path):
    folder = tmp_path / "src" / "lba_000001_offset_0000"
    folder.mkdir(parents=True)
    payload = make_payload()
    (folder / "decoded.bin").write_bytes(payload)
    out = tmp_path / "previews"
    result = preview_regions(tmp_path / "src", out)
    assert result["counts"]["exported"] == 1
    assert (out / "lba_000001_offset_0000_split_vertical.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert (folder / "decoded.bin").read_bytes() == payload
