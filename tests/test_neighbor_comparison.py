import json
import struct

from ddw3_tools.neighbor_comparison import compare_neighbor_atlases


def _tim(index):
    colors = [0, 0x001f, 0x03e0] + [0] * 13
    pal = struct.pack("<16H", *colors)
    clut = struct.pack("<IHHHH", 12 + len(pal), 0, 0, 16, 1) + pal
    pixels = bytes((index | (index << 4), 0))
    image = struct.pack("<IHHHH", 12 + len(pixels), 0, 0, 1, 1) + pixels
    return b"\x10\x00\x00\x00" + struct.pack("<I", 8) + clut + image


def test_neighbor_comparison_exact_positions_and_differences(tmp_path):
    source = tmp_path / "rlen"
    for lba, offset, index in ((24226, 1732, 1), (24241, 668, 2)):
        folder = source / f"lba_{lba:06d}_offset_{offset:04d}"
        folder.mkdir(parents=True)
        (folder / "decoded.bin").write_bytes(_tim(index))
    output = tmp_path / "out"
    result = compare_neighbor_atlases(
        source, output, targets=((24226, 1732), (24241, 668), (24233, 540)),
        tile=64)
    assert [r["status"] for r in result["resources"]] == ["tim", "tim", "missing"]
    pair = result["pairwise"][0]
    assert pair["same_dimensions_bpp"]
    assert pair["same_clut"]
    assert not pair["same_indexed_pixels"]
    assert pair["palette0_changed_rgba_pixels"] == 2
    assert (output / "neighbor_comparison.png").read_bytes().startswith(bytes((137, 80, 78, 71)))
    assert json.loads((output / "neighbor_comparison.json").read_text())["resources"][2]["status"] == "missing"


def test_identical_files_compare_equal(tmp_path):
    source = tmp_path / "rlen"
    for lba in (1, 2):
        folder = source / f"lba_{lba:06d}_offset_0000"
        folder.mkdir(parents=True)
        (folder / "decoded.bin").write_bytes(_tim(1))
    result = compare_neighbor_atlases(source, tmp_path / "out",
                                      targets=((1, 0), (2, 0)), tile=64)
    pair = result["pairwise"][0]
    assert pair["same_indexed_pixels"] and pair["same_clut"]
    assert pair["palette0_changed_rgba_pixels"] == 0
