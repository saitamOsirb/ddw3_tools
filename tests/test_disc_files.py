import json
import struct

from ddw3_tools.disc_files import Disc, catalog_disc
from ddw3_tools.disc_packs import plausible_pack, scan_disc_packs


def record(name, lba, size, directory=False):
    encoded = name.encode("ascii")
    length = 33 + len(encoded) + (len(encoded) % 2 == 0)
    buf = bytearray(length)
    buf[0] = length
    struct.pack_into("<I", buf, 2, lba)
    struct.pack_into(">I", buf, 6, lba)
    struct.pack_into("<I", buf, 10, size)
    struct.pack_into(">I", buf, 14, size)
    buf[25] = 2 if directory else 0
    buf[28:32] = bytes((1, 0, 0, 1))
    buf[32] = len(encoded)
    buf[33:33 + len(encoded)] = encoded
    return bytes(buf)


def make_iso(tmp_path):
    sectors = [bytes(2048) for _ in range(24)]
    descriptor = bytearray(2048)
    descriptor[:7] = b"\x01CD001\x01"
    root = record("\x00", 20, 2048, True)
    descriptor[156:156 + len(root)] = root
    sectors[16] = bytes(descriptor)
    members = b"HELLO" + b"WORLD"
    packed = struct.pack("<2I", 8, 13) + members
    sectors[21] = packed.ljust(2048, b"\x00")
    sectors[20] = (record("\x00", 20, 2048, True) +
                   record("DATA.BIN;1", 21, len(packed))).ljust(2048, b"\x00")
    path = tmp_path / "test.iso"
    path.write_bytes(b"".join(sectors))
    return path, packed


def test_catalog_and_pack_detection(tmp_path):
    iso, packed = make_iso(tmp_path)
    catalog = catalog_disc(iso, tmp_path / "catalog.json")
    assert catalog["file_count"] == 1
    assert catalog["files"][0]["path"] == "DATA.BIN"
    disc = Disc(iso)
    try:
        assert disc.extent(21, len(packed)) == packed
    finally:
        disc.close()
    result = scan_disc_packs(iso, tmp_path / "found", extract=True)
    assert result["pack_candidates"] == 1
    assert result["matches"][0]["extracted"] is True
    assert json.loads((tmp_path / "found/disc_packs.json").read_text()) == result


def test_pack_candidate_rejects_noise():
    assert not plausible_pack(bytes(2048), 2048)
    assert not plausible_pack(struct.pack("<2I", 8, 9999), 20)
