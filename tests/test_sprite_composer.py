import json
import struct

import pytest

from ddw3_tools.sprite_composer import (
    _over, compose_sprite, make_composition_recipe,
)


def _tim():
    colors = [0, 0x001f, 0x03e0] + [0] * 13
    palette = struct.pack("<16H", *colors)
    clut = struct.pack("<IHHHH", 12 + len(palette), 0, 0, 16, 1) + palette
    # 8 pixels: group 0 uses palette index 1, group 1 index 2
    pixels = bytes((0x11, 0, 0x22, 0))
    image = struct.pack("<IHHHH", 12 + len(pixels), 0, 0, 2, 1) + pixels
    return b"\x10\x00\x00\x00" + struct.pack("<I", 8) + clut + image


def _prepare(tmp_path):
    resources = tmp_path / "resources"
    folder = resources / "lba_024241_offset_0668"
    folder.mkdir(parents=True)
    (folder / "decoded.bin").write_bytes(_tim())
    aligned = tmp_path / "aligned"
    aligned.mkdir()
    manifest = {
        "source": "lba_024241_offset_0668/decoded.bin",
        "atlas_size": [8, 1],
        "palettes": [{"palette": 0, "status": "partial"}],
        "groups": [
            {"id": 0, "box": {"x": 0, "y": 0, "w": 2, "h": 1}},
            {"id": 1, "box": {"x": 4, "y": 0, "w": 2, "h": 1}},
        ],
    }
    (aligned / "aligned_candidates.json").write_text(json.dumps(manifest))
    return resources, aligned


def test_recipe_and_composition_by_original_tim(tmp_path):
    resources, aligned = _prepare(tmp_path)
    recipe_path = tmp_path / "recipe.json"
    recipe = make_composition_recipe(aligned, recipe_path)
    assert [p["id"] for p in recipe["parts"]] == [0, 1]
    recipe["parts"][1]["x"] = 0
    recipe["parts"][1]["z"] = 10
    recipe_path.write_text(json.dumps(recipe))
    result = compose_sprite(aligned, resources, recipe_path, tmp_path / "sprite.png")
    assert result["size"] == [2, 1]
    assert (tmp_path / "sprite.png").read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / "sprite.json").is_file()
    assert (resources / "lba_024241_offset_0668" / "decoded.bin").read_bytes() == _tim()


def test_composer_rejects_untrusted_source_and_empty_layout(tmp_path):
    resources, aligned = _prepare(tmp_path)
    recipe_path = tmp_path / "recipe.json"
    recipe = make_composition_recipe(aligned, recipe_path)
    for part in recipe["parts"]:
        part["enabled"] = False
    recipe_path.write_text(json.dumps(recipe))
    with pytest.raises(ValueError, match="habilitadas"):
        compose_sprite(aligned, resources, recipe_path, tmp_path / "bad.png")
    report_path = aligned / "aligned_candidates.json"
    report = json.loads(report_path.read_text())
    report["source"] = "../outside/decoded.bin"
    report_path.write_text(json.dumps(report))
    recipe["source"] = "../outside/decoded.bin"
    recipe["parts"][0]["enabled"] = True
    recipe_path.write_text(json.dumps(recipe))
    with pytest.raises(ValueError, match="fuera de los recursos"):
        compose_sprite(aligned, resources, recipe_path, tmp_path / "bad.png")


def test_source_over_opaque_and_transparent():
    canvas = bytearray((0, 0, 255, 255))
    _over(canvas, 0, bytes((255, 0, 0, 0)), 0)
    assert bytes(canvas) == bytes((0, 0, 255, 255))
    _over(canvas, 0, bytes((255, 0, 0, 255)), 0)
    assert bytes(canvas) == bytes((255, 0, 0, 255))
