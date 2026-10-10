import pytest

from ddw3_tools.rlen import decode_rlen


def test_rlen_literal_and_repetition():
    # literal ABC, then repeat Z three times.
    data = b"RLEN" + (6).to_bytes(4, "little") + bytes([3]) + b"ABC" + bytes([0x83, 90])
    decoded, consumed = decode_rlen(data)
    assert decoded == b"ABCZZZ"
    assert consumed == len(data)


def test_rlen_rejects_bad_streams():
    for data in (b"bad", b"RLEN" + (2).to_bytes(4, "little") + b"\x03abc",
                 b"RLEN" + (3).to_bytes(4, "little") + b"\x83"):
        with pytest.raises(ValueError):
            decode_rlen(data)


def test_rlen_output_limit():
    with pytest.raises(ValueError):
        decode_rlen(b"RLEN" + (100).to_bytes(4, "little"), max_output=10)
