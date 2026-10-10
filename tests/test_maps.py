from pathlib import Path
from unittest.mock import patch

import pytest

from ddw3_tools.maps import discover_maps, download_maps


def test_discover_one_stage():
    def fake_entries(path):
        if path.startswith("map-tile/"):
            return [{"type": "file", "path": path + "/0.toml", "download_url": "https://raw.githubusercontent.com/example/file", "size": 4}]
        return [{"type": "file", "path": path + "/0.png", "download_url": "https://raw.githubusercontent.com/example/file", "size": 4}]
    with patch("ddw3_tools.maps.directory_entries", side_effect=fake_entries):
        result = discover_maps("s200pack")
    assert len(result) == 2


def test_download_stage(tmp_path):
    files = [{"path": "tim/dw2003/z_stage/s200pack/0.png", "url": "https://raw.githubusercontent.com/example/file", "size": 4}]
    with patch("ddw3_tools.maps.discover_maps", return_value=files), patch("ddw3_tools.maps.request_bytes", return_value=b"test"):
        assert download_maps(tmp_path, stage="s200pack", list_only=False, max_files=10) == (1, 0)
    assert (tmp_path / files[0]["path"]).read_bytes() == b"test"


def test_no_overwrite(tmp_path):
    files = [{"path": "tim/dw2003/z_stage/s200pack/0.png", "url": "https://raw.githubusercontent.com/example/file", "size": 4}]
    output = tmp_path / files[0]["path"]
    output.parent.mkdir(parents=True)
    output.write_bytes(b"keep")
    with patch("ddw3_tools.maps.discover_maps", return_value=files), patch("ddw3_tools.maps.request_bytes") as request:
        assert download_maps(tmp_path, stage=None, list_only=False, max_files=10) == (0, 1)
        request.assert_not_called()
    assert output.read_bytes() == b"keep"


def test_reject_too_many_files(tmp_path):
    with patch("ddw3_tools.maps.discover_maps", return_value=[{}, {}]):
        with pytest.raises(ValueError):
            download_maps(tmp_path, stage=None, list_only=True, max_files=1)
