"""Download the already-extracted map metadata and TIM PNG resources from ddw3."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

OWNER_REPO = "saitamOsirb/ddw3"
BRANCH = "master"
ALLOWED_ROOTS = ("map-tile/dw2003/z_stage", "tim/dw2003/z_stage")
API = "https://api.github.com/repos/" + OWNER_REPO + "/contents/"
USER_AGENT = "ddw3-tools/0.2"


def request_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urlopen(req, timeout=45) as response:
        return response.read()


def directory_entries(path: str) -> list[dict]:
    url = API + quote(path, safe="/") + "?ref=" + BRANCH
    result = json.loads(request_bytes(url))
    if not isinstance(result, list):
        raise ValueError(f"GitHub no devolvió un directorio: {path}")
    return result


def discover_maps(stage: str | None = None) -> list[dict]:
    """Discover map tile metadata and associated PNG/TOML files for one or all stages."""
    stages = [stage] if stage else [
        entry["name"] for entry in directory_entries(ALLOWED_ROOTS[0])
        if entry.get("type") == "dir"
    ]
    result: list[dict] = []
    for name in stages:
        if not name.startswith("s") or not name.endswith("pack") or "/" in name or ".." in name:
            raise ValueError("Nombre de stage no válido; ejemplo: s200pack")
        for root in ALLOWED_ROOTS:
            directory = root + "/" + name
            try:
                entries = directory_entries(directory)
            except HTTPError as exc:
                if exc.code == 404:
                    continue
                raise
            for entry in entries:
                if entry.get("type") != "file":
                    continue
                path = entry.get("path", "")
                suffix = PurePosixPath(path).suffix.lower()
                if suffix not in {".toml", ".png"} or not path.startswith(directory + "/"):
                    continue
                url = entry.get("download_url")
                if not isinstance(url, str) or not url.startswith("https://raw.githubusercontent.com/"):
                    continue
                result.append({"path": path, "url": url, "size": entry.get("size", 0)})
    return result


def download_maps(output: Path, *, stage: str | None, list_only: bool, max_files: int) -> tuple[int, int]:
    if max_files < 1:
        raise ValueError("--max-files debe ser mayor que cero")
    files = discover_maps(stage)
    print(f"Encontrados {len(files)} archivos de metadatos y texturas para mapas.")
    if len(files) > max_files:
        raise ValueError(f"Hay {len(files)} archivos; aumenta --max-files (actual: {max_files}).")
    downloaded = 0
    skipped = 0
    base = output.expanduser().resolve()
    for entry in files:
        rel = PurePosixPath(entry["path"])
        if rel.is_absolute() or ".." in rel.parts or rel.parts[0] not in {"tim", "map-tile"}:
            raise ValueError(f"Ruta insegura: {entry['path']}")
        dest = base.joinpath(*rel.parts)
        if not dest.resolve().is_relative_to(base):
            raise ValueError(f"Ruta fuera de destino: {dest}")
        if list_only:
            print(entry["path"])
            continue
        if dest.exists():
            skipped += 1
            continue
        data = request_bytes(entry["url"])
        size = entry["size"]
        if isinstance(size, int) and size >= 0 and len(data) != size:
            raise ValueError(f"Tamaño inesperado: {entry['path']}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        downloaded += 1
        print("OK", entry["path"])
    return downloaded, skipped
