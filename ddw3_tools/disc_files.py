"""Read ISO9660 directory entries from 2048-byte ISO or 2352-byte PS1 BIN.

Read-only; Mode 2 Form 2 data is intentionally rejected.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
SECTOR = 2048


class Disc:
    def __init__(self, path: Path):
        self.path = path
        self.handle = path.open("rb")
        self.size = path.stat().st_size
        self.raw = False
        if self.size >= 2352 and self.size % 2352 == 0:
            self.raw = self.handle.read(12) == SYNC
        self.handle.seek(0)

    def close(self):
        self.handle.close()

    def sector(self, lba: int) -> bytes:
        if lba < 0:
            raise ValueError("LBA negativo")
        unit = 2352 if self.raw else SECTOR
        if (lba + 1) * unit > self.size:
            raise ValueError(f"Sector fuera de disco: {lba}")
        self.handle.seek(lba * unit)
        raw = self.handle.read(unit)
        if not self.raw:
            return raw
        if raw[:12] != SYNC:
            raise ValueError(f"Sin sincronizacion PS1 en LBA {lba}")
        if raw[15] == 1:
            return raw[16:16 + SECTOR]
        if raw[15] == 2 and not (raw[18] & 0x20):
            return raw[24:24 + SECTOR]
        raise ValueError(f"Sector no compatible (Mode 2 Form 2) en LBA {lba}")

    def extent(self, lba: int, size: int) -> bytes:
        if size < 0:
            raise ValueError("Longitud negativa")
        return b"".join(self.sector(lba + i) for i in range((size + SECTOR - 1) // SECTOR))[:size]


def _record(data: bytes) -> dict:
    if len(data) < 34 or data[0] != len(data):
        raise ValueError("Registro ISO9660 invalido")
    lba = struct.unpack_from("<I", data, 2)[0]
    size = struct.unpack_from("<I", data, 10)[0]
    # ISO9660 duplicates both numbers in big endian.
    if struct.unpack_from(">I", data, 6)[0] != lba or struct.unpack_from(">I", data, 14)[0] != size:
        raise ValueError("Registro ISO9660 con endian inconsistente")
    length = data[32]
    if 33 + length > len(data):
        raise ValueError("Nombre ISO9660 truncado")
    name = data[33:33 + length].decode("ascii", errors="replace")
    return {"name": name.split(";")[0], "lba": lba, "size": size,
            "directory": bool(data[25] & 2)}


def list_files(disc: Disc, *, max_files: int = 100000, max_depth: int = 24) -> list[dict]:
    descriptor = disc.sector(16)
    if descriptor[0] != 1 or descriptor[1:6] != b"CD001" or descriptor[6] != 1:
        raise ValueError("No se encontro un descriptor ISO9660 primario en LBA 16")
    root_size = descriptor[156]
    root = _record(descriptor[156:156 + root_size])
    pending = [("", root, 0)]
    visited = set()
    files = []
    while pending:
        prefix, directory, depth = pending.pop()
        if depth > max_depth:
            raise ValueError("Profundidad ISO9660 excedida")
        key = (directory["lba"], directory["size"])
        if key in visited:
            continue
        visited.add(key)
        payload = disc.extent(directory["lba"], directory["size"])
        pos = 0
        while pos < len(payload):
            length = payload[pos]
            if not length:
                pos = ((pos // SECTOR) + 1) * SECTOR
                continue
            if length < 34 or pos + length > len(payload):
                raise ValueError("Directorio ISO9660 corrupto")
            record = _record(payload[pos:pos + length])
            pos += length
            if record["name"] in ("\x00", "\x01"):
                continue
            path = prefix + "/" + record["name"]
            if record["directory"]:
                pending.append((path, record, depth + 1))
            else:
                files.append({"path": path.lstrip("/"), "lba": record["lba"],
                              "size": record["size"]})
                if len(files) > max_files:
                    raise ValueError("Limite de archivos excedido")
    return sorted(files, key=lambda item: item["path"])


def catalog_disc(source: Path, output: Path, *, max_files: int = 100000) -> dict:
    disc = Disc(source)
    try:
        files = list_files(disc, max_files=max_files)
        result = {"source": str(source), "layout": "raw2352" if disc.raw else "iso2048",
                  "file_count": len(files), "files": files}
    finally:
        disc.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
