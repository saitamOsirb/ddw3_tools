import json
import struct

from ddw3_tools.resource_inspector import inspect_payload, inspect_extractions


def make_tim_16bpp():
    # Header: magic, mode 16bpp (no CLUT), image block size, VRAM x/y, w/h.
    return (b"\x10\x00\x00\x00" + struct.pack("<I", 2)
            + struct.pack("<IHHHH", 16, 320, 64, 2, 1)
            + b"\x1f\x00\xe0\x03")


def test_inspector_reports_tim_vram_and_unknown_bytes():
    payload = b"ABCD" + make_tim_16bpp() + b"END"
    result = inspect_payload(payload)
    assert result["classification"] == "tim_and_unclassified_bytes"
    assert result["tim_count"] == 1
    assert result["tim_images"][0]["width"] == 2
    assert result["tim_images"][0]["height"] == 1
    assert result["tim_images"][0]["bpp"] == 16
    assert result["tim_images"][0]["image_vram_xy"] == [320, 64]
    assert result["tim_images"][0]["has_embedded_clut"] is False
    assert result["unclassified_bytes"] == 7
    assert result["geometry_detected"] is False


def test_inspector_directory_and_origin(tmp_path):
    folder = tmp_path / "lba_001613_offset_0024"
    folder.mkdir()
    (folder / "decoded.bin").write_bytes(make_tim_16bpp())
    (folder / "rlen_manifest.json").write_text(json.dumps({
        "lba": 1613, "sector_offset": 24, "compressed_bytes": 14978
    }))
    target = tmp_path / "report.json"
    result = inspect_extractions(tmp_path, target)
    assert result["summary"]["tim_count"] == 1
    assert result["resources"][0]["origin"]["lba"] == 1613
    assert result["resources"][0]["classification"] == "tim_only"
    assert json.loads(target.read_text()) == result


def test_inspector_unknown_data_and_limit(tmp_path):
    (tmp_path / "decoded.bin").write_bytes(b"not a TIM")
    result = inspect_extractions(tmp_path / "decoded.bin", tmp_path / "report.json")
    assert result["resources"][0]["classification"] == "unclassified_binary"
    assert result["resources"][0]["unclassified_bytes"] == 9
