import json

from ddw3_tools.sprites import write_png
from ddw3_tools.sprites_report import inspect_png, build_report


def test_inspect_png_alpha_bbox(tmp_path):
    image = tmp_path / "sample.png"
    pixels = bytearray(4 * 4 * 4)
    for x, y in ((1, 1), (2, 1), (2, 2)):
        pixels[(y * 4 + x) * 4 + 3] = 255
    write_png(image, 4, 4, bytes(pixels))
    result = inspect_png(image)
    assert result["content_bbox_xyxy"] == [1, 1, 3, 3]
    assert result["opaque_pixels"] == 3
    assert result["opaque_pixels_per_row"] == [0, 2, 1, 0]


def test_build_report(tmp_path):
    write_png(tmp_path / "tim.png", 1, 1, bytes((255, 0, 0, 255)))
    (tmp_path / "manifest.json").write_text(json.dumps({
        "source": "test.bin", "disc_layout": "raw2352",
        "images": [{"offset": 24, "logical_offset": 0, "bpp": 16,
                    "files": ["tim.png"]}]
    }), encoding="utf-8")
    destination = tmp_path / "report.json"
    report = build_report(tmp_path, destination)
    assert report["texture_count"] == 1
    assert report["textures"][0]["palettes"][0]["content_bbox_xyxy"] == [0, 0, 1, 1]
    assert json.loads(destination.read_text()) == report
