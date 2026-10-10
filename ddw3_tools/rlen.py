"""Bounded RLEN decoder matching markisha64/dmw3-util/rlen.

The 32-bit little-endian value after RLEN is the decompressed byte count.
Returns consumed compressed bytes so embedded blocks can be located precisely.
"""
from __future__ import annotations

import struct


def decode_rlen(data: bytes, *, max_output: int = 32 * 1024 * 1024) -> tuple[bytes, int]:
    if len(data) < 8 or data[:4] != b"RLEN":
        raise ValueError("Cabecera RLEN invalida")
    expected = struct.unpack_from("<I", data, 4)[0]
    if expected > max_output:
        raise ValueError("RLEN excede el limite de salida")
    output = bytearray()
    cursor = 8
    while len(output) < expected:
        if cursor >= len(data):
            raise ValueError("RLEN truncado")
        control = data[cursor]
        cursor += 1
        if control < 0x80:
            length = control
            if cursor + length > len(data) or len(output) + length > expected:
                raise ValueError("RLEN literal fuera de limites")
            output.extend(data[cursor:cursor + length])
            cursor += length
        else:
            length = control - 0x80
            if cursor >= len(data) or len(output) + length > expected:
                raise ValueError("RLEN repeticion fuera de limites")
            output.extend(bytes((data[cursor],)) * length)
            cursor += 1
    return bytes(output), cursor
