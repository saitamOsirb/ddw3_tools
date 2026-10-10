from unittest.mock import patch

from ddw3_tools.cli import build_parser, convert, main


def test_parser_has_video_subcommands():
    parser = build_parser()
    for name in ("index", "list", "extract", "convert", "convert-dir"):
        assert name in parser.format_help()


def test_missing_input_returns_nonzero(tmp_path):
    assert main(["convert", "--input", str(tmp_path / "missing.avi"), "--output", str(tmp_path / "out.ogv")]) == 1


def test_convert_builds_ffmpeg_command(tmp_path):
    src = tmp_path / "video.avi"
    src.write_bytes(b"placeholder")
    output = tmp_path / "dir" / "video.ogv"
    with patch("ddw3_tools.cli.tool_command", return_value="ffmpeg"), patch("ddw3_tools.cli.run") as runner:
        convert(src, output, overwrite=False)
    args = runner.call_args.args[0]
    assert "libtheora" in args
    assert "libvorbis" in args
    assert str(output) == args[-1]


def test_convert_refuses_overwrite(tmp_path):
    src, output = tmp_path / "a.avi", tmp_path / "a.ogv"
    src.write_bytes(b"")
    output.write_bytes(b"")
    assert main(["convert", "--input", str(src), "--output", str(output)]) == 1
