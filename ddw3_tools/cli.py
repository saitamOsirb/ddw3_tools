"""Command-line interface for jPSXdec and FFmpeg, with no network downloads."""
from __future__ import annotations

import argparse
from pathlib import Path

from .maps import download_maps
from .sprites import extract_sprites
import shutil
import subprocess
import sys

VIDEO_SUFFIXES = {".avi", ".mp4", ".mkv", ".mov", ".webm", ".mpg", ".mpeg"}


def file_path(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"El archivo no existe: {path}")
    return path


def jpsxdec_command(jpsxdec: str) -> list[str]:
    path = Path(jpsxdec).expanduser()
    if path.suffix.lower() == ".jar":
        jar = file_path(jpsxdec)
        java = shutil.which("java")
        if not java:
            raise ValueError("Java no está instalado o no está disponible en PATH.")
        return [java, "-jar", str(jar)]
    exe = shutil.which(jpsxdec)
    if not exe and path.is_file():
        exe = str(path.resolve())
    if not exe:
        raise ValueError(f"No se encontró el ejecutable de jPSXdec: {jpsxdec}")
    return [exe]


def tool_command(name: str) -> str:
    tool = shutil.which(name)
    if tool is None:
        raise ValueError(f"No se encontró {name} en PATH.")
    return tool


def run(args: list[str]) -> None:
    print("+", subprocess.list2cmdline(args), flush=True)
    completed = subprocess.run(args, check=False)
    if completed.returncode:
        raise RuntimeError(f"El proceso terminó con código {completed.returncode}")


def convert(source: Path, destination: Path, *, overwrite: bool) -> None:
    if source.resolve() == destination.resolve():
        raise ValueError("La entrada y salida deben ser archivos distintos.")
    if destination.exists() and not overwrite:
        raise ValueError(f"El archivo de salida ya existe: {destination}. Usa --overwrite.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    run([
        tool_command("ffmpeg"), "-hide_banner", "-nostdin",
        "-y" if overwrite else "-n", "-i", str(source),
        "-map", "0:v:0", "-map", "0:a:0?",
        "-c:v", "libtheora", "-q:v", "7",
        "-c:a", "libvorbis", "-q:a", "5",
        "-f", "ogg", str(destination),
    ])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ddw3", description="Extraer videos de PS1 y convertirlos para Godot.")
    sub = parser.add_subparsers(dest="command", required=True)

    maps = sub.add_parser("maps-download", help="Descargar PNG y metadatos de mapas desde ddw3 (GitHub).")
    maps.add_argument("--output", required=True, help="Carpeta destino; preserva tim/ y map-tile/.")
    maps.add_argument("--stage", help="Un stage específico, por ejemplo s200pack; omitir para todos.")
    maps.add_argument("--list-only", action="store_true", help="Listar sin descargar.")
    maps.add_argument("--max-files", type=int, default=100000, help="Límite de archivos a descargar.")

    sprites = sub.add_parser("sprites-extract", help="Escanear TIM de BIN/ISO y exportar PNG y manifest.json.")
    sprites.add_argument("--disc", required=True)
    sprites.add_argument("--output", required=True)
    sprites.add_argument("--max-images", type=int, default=10000)

    index = sub.add_parser("index", help="Indexar BIN/ISO con jPSXdec.")
    index.add_argument("--disc", required=True)
    index.add_argument("--jpsxdec", required=True)
    index.add_argument("--output", required=True)

    listing = sub.add_parser("list", help="Mostrar índice de jPSXdec con números e IDs de elementos.")
    listing.add_argument("--index", required=True)
    listing.add_argument("--jpsxdec", required=True)

    extract = sub.add_parser("extract", help="Extraer un video mediante su ID jPSXdec.")
    extract.add_argument("--index", required=True)
    extract.add_argument("--jpsxdec", required=True)
    extract.add_argument("--item", required=True)
    extract.add_argument("--output", required=True)

    conv = sub.add_parser("convert", help="Convertir un video a OGV/Theora para Godot.")
    conv.add_argument("--input", required=True)
    conv.add_argument("--output", required=True)
    conv.add_argument("--overwrite", action="store_true")

    folder = sub.add_parser("convert-dir", help="Convertir videos de una carpeta a OGV.")
    folder.add_argument("--input", required=True)
    folder.add_argument("--output", required=True)
    folder.add_argument("--overwrite", action="store_true")
    return parser


def execute(namespace: argparse.Namespace) -> None:
    command = namespace.command
    if command == "sprites-extract":
        manifest = extract_sprites(file_path(namespace.disc), Path(namespace.output), max_images=namespace.max_images)
        print(f"TIM encontrados: {manifest['tim_count']}; PNG exportados: {manifest['png_count']}")
        return
    if command == "maps-download":
        downloaded, skipped = download_maps(Path(namespace.output), stage=namespace.stage, list_only=namespace.list_only, max_files=namespace.max_files)
        print(f"Descargados: {downloaded}; existentes omitidos: {skipped}")
        return
    if command in {"index", "list", "extract"}:
        base = jpsxdec_command(namespace.jpsxdec)
        if command == "index":
            source = file_path(namespace.disc)
            out = Path(namespace.output).expanduser().resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists():
                raise ValueError(f"Ya existe el índice: {out}")
            run(base + ["-f", str(source), "-x", str(out)])
        elif command == "list":
            index_path = file_path(namespace.index)
            print(index_path.read_text(encoding="utf-8-sig", errors="replace"))
        else:
            index = file_path(namespace.index)
            out = Path(namespace.output).expanduser().resolve()
            out.mkdir(parents=True, exist_ok=True)
            # Use absolute destination prefix, to avoid writing beside the input disc.
            run(base + ["-x", str(index), "-i", namespace.item, "-dir", str(out), "-quality", "high", "-vf", "avi:rgb"])
        return
    if command == "convert":
        convert(file_path(namespace.input), Path(namespace.output).expanduser().resolve(), overwrite=namespace.overwrite)
        return
    source_dir = Path(namespace.input).expanduser().resolve()
    if not source_dir.is_dir():
        raise ValueError(f"No existe la carpeta de entrada: {source_dir}")
    target_dir = Path(namespace.output).expanduser().resolve()
    if target_dir == source_dir:
        raise ValueError("Las carpetas de entrada y salida deben ser diferentes.")
    files = sorted(path for path in source_dir.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES)
    if not files:
        raise ValueError("No se encontraron videos AVI/MP4/MKV/MOV/WEBM/MPG/MPEG.")
    for source in files:
        convert(source, target_dir / f"{source.stem}.ogv", overwrite=namespace.overwrite)


def main(argv: list[str] | None = None) -> int:
    try:
        execute(build_parser().parse_args(argv))
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0
