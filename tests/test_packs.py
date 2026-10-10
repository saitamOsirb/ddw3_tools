import json
import struct

import pytest

from ddw3_tools.packs import unpack, extract_pack
from ddw3_tools.sprites import MAGIC


def make_pack(*parts):
    offset = 4 * len(parts)
    table = []
    payload = bytearray()
    for part in parts:
        if part:
            table.append(offset)
            payload.extend(part)
            offset += len(part)
        else:
            table.append(0)
    return struct.pack(f"<{len(table)}I", *table) + payload


def test_pack_extract_preserves_raw_and_previews_tim(tmp_path):
    tim = MAGIC + struct.pack("<I", 2) + struct.pack("<IHHHHH", 14, 1, 2, 1, 1, 31)
    source = tmp_path / "resource.bin"
    source.write_bytes(make_pack(b"hello", b"", tim))
    result = extract_pack(source, tmp_path / "out")
    assert [x["size"] for x in result["entries"]] == [5, 0, len(tim)]
    assert (tmp_path / "out/part_0000.bin").read_bytes() == b"hello"
    assert (tmp_path / "out/part_0002.bin").read_bytes() == tim
    assert result["entries"][2]["tim"]["image_position"] == [1, 2]
    assert (tmp_path / "out/part_0002_pal_000.png").exists()
    assert json.loads((tmp_path / "out/pack_manifest.json").read_text()) == result


def test_pack_rejects_invalid_offsets():
    for raw in (b"", b"\x03\x00\x00\x00",
                struct.pack("<I", 128),
                struct.pack("<2I", 8, 9999)):
        with pytest.raises(ValueError):
            unpack(raw)


def test_pack_duplicate_offsets_match_reference():
    # The upstream implementation seeks the next strictly greater offset.
    data = struct.pack("<3I", 12, 12, 14) + b"abcd"
    entries = unpack(data)
    assert [x["data"] for x in entries] == [b"ab", b"ab", b"cd"]
