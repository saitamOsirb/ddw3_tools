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