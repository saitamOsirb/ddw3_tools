import json
import struct
from ddw3_tools.assets_inventory import classify_member, inventory_packs
from ddw3_tools.sprites import MAGIC

def test_embedded_tim():
    tim = MAGIC + struct.pack("<I", 2) + struct.pack("<IHHHHH", 14, 0, 0, 1, 1, 31)
    result = classify_member(b"prefix" + tim)
    assert result["classification"] == "embedded_tim"
    assert result["tim"][0]["offset"] == 6

def test_inventory(tmp_path):
    root = tmp_path / "resources"
    root.mkdir()
    (root / "part_0000.bin").write_bytes(b"unknown")
    (root / "pack_manifest.json").write_text(json.dumps({"entries": [{"file": "part_0000.bin"}]}))
    result = inventory_packs(root, tmp_path / "inventory.json")
    assert result["members"] == 1
    assert result["classifications"]["unclassified"] == 1

def test_export_embedded_tim_preview(tmp_path):
    root = tmp_path / "resources"
    root.mkdir()
    tim = MAGIC + struct.pack("<I", 2) + struct.pack("<IHHHHH", 14, 0, 0, 1, 1, 31)
    (root / "part_0001.bin").write_bytes(b"prefix" + tim + b"suffix")
    (root / "pack_manifest.json").write_text(
        json.dumps({"entries": [{"file": "part_0001.bin"}]}))
    result = inventory_packs(root, tmp_path / "inventory.json", export_tim=True)
    assert result["tim_structures"] == 1
    assert result["png_previews"] == 1
    entry = result["entries"][0]
    assert entry["tim"][0]["offset"] == 6
    preview = root / entry["previews"][0]["file"]
    assert preview.read_bytes().startswith(bytes((137, 80, 78, 71)))
