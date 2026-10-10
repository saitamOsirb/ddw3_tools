"""Command-line interface for jPSXdec and FFmpeg, with no network downloads."""
from __future__ import annotations

import argparse
from pathlib import Path

from .maps import download_maps
from .sprites import extract_sprites
from .sprites_report import build_report
from .packs import extract_pack
from .disc_files import catalog_disc
from .disc_packs import scan_disc_packs
from .assets_inventory import inventory_packs
from .embedded_packs import scan_embedded_packs
from .disc_layout import analyze_layout
from .disc_survey import survey_regions
from .rlen_extract import extract_rlen_at
from .rlen_batch import extract_rlen_batch
from .resource_inspector import inspect_extractions
from .prefix_inspector import inspect_prefixes
from .header_structure import inspect_header_structure
from .record_analysis import analyze_records
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

    records = sub.add_parser("records-analyze", help="Analizar registros de 12 bytes como seis u16 y contrastarlos con dimensiones TIM.")
    records.add_argument("--input", required=True)
    records.add_argument("--output", required=True)
    records.add_argument("--max-files", type=int, default=10000)

    structure = sub.add_parser("headers-structure", help="Verificar cabeceras 16+12*N y distribuir campos sin atribuir significado.")
    structure.add_argument("--input", required=True)
    structure.add_argument("--output", required=True)
    structure.add_argument("--max-files", type=int, default=10000)

    headers = sub.add_parser("headers-inspect", help="Agrupar cabeceras desconocidas anteriores a las texturas TIM.")
    headers.add_argument("--input", required=True, help="Carpeta rlen_full con decoded.bin.")
    headers.add_argument("--output", required=True, help="Informe JSON con familias de cabeceras.")
    headers.add_argument("--max-files", type=int, default=10000)

    inspect = sub.add_parser("resources-inspect", help="Inventariar TIM, CLUT, VRAM y bytes desconocidos en datos RLEN ya extraidos.")
    inspect.add_argument("--input", required=True, help="Carpeta rlen_batch/rlen_full o decoded.bin individual.")
    inspect.add_argument("--output", required=True, help="Archivo JSON del inventario.")
    inspect.add_argument("--max-files", type=int, default=10000)

    batch = sub.add_parser("rlen-batch", help="Extraer en lote firmas RLEN de un informe disc-survey.")
    batch.add_argument("--disc", required=True)
    batch.add_argument("--survey", required=True)
    batch.add_argument("--output", required=True)
    batch.add_argument("--max-blocks", type=int, default=100)

    rlen = sub.add_parser("rlen-extract", help="Descomprimir un bloque RLEN por LBA y offset.")
    rlen.add_argument("--disc", required=True)
    rlen.add_argument("--lba", required=True, type=int)
    rlen.add_argument("--offset", required=True, type=int)
    rlen.add_argument("--output", required=True)

    survey = sub.add_parser("disc-survey", help="Inspeccionar regiones no catalogadas y localizar firmas RLEN.")
    survey.add_argument("--disc", required=True)
    survey.add_argument("--output", required=True)
    survey.add_argument("--stride", type=int, default=1, help="Leer un sector de cada N.")
    survey.add_argument("--max-hits", type=int, default=200)

    layout = sub.add_parser("disc-layout", help="Medir regiones físicas no catalogadas por ISO9660.")
    layout.add_argument("--disc", required=True)
    layout.add_argument("--output", required=True)

    embedded = sub.add_parser("disc-scan-embedded", help="Buscar cabeceras PACK alineadas a sectores dentro de archivos grandes.")
    embedded.add_argument("--disc", required=True)
    embedded.add_argument("--output", required=True)
    embedded.add_argument("--max-sectors", type=int, default=400000)
    embedded.add_argument("--max-hits", type=int, default=1000)

    inventory = sub.add_parser("assets-inventory", help="Inventariar entradas PACK y TIM internos.")
    inventory.add_argument("--input", required=True, help="Carpeta de pack-extract o disc-packs --extract.")
    inventory.add_argument("--output", required=True, help="Ruta del JSON de inventario.")
    inventory.add_argument("--export-tim", action="store_true", help="Exportar PNG de TIM incrustados.")

    catalog = sub.add_parser("disc-catalog", help="Catalogar archivos ISO9660 dentro de un BIN/ISO PS1.")
    catalog.add_argument("--disc", required=True)
    catalog.add_argument("--output", required=True)
    catalog.add_argument("--max-files", type=int, default=100000)

    packs = sub.add_parser("disc-packs", help="Buscar contenedores PACK candidatos en archivos del disco.")
    packs.add_argument("--disc", required=True)
    packs.add_argument("--output", required=True)
    packs.add_argument("--extract", action="store_true", help="Extraer candidatos (puede ocupar mucho espacio).")
    packs.add_argument("--max-extract", type=int, default=50)

    pack = sub.add_parser("pack-extract", help="Extraer entradas de un contenedor PACK DW3 y previsualizar TIM completos.")
    pack.add_argument("--input", required=True, help="Archivo PACK/BIN individual, no la imagen completa del disco.")
    pack.add_argument("--output", required=True, help="Carpeta para entradas y manifiesto.")
    pack.add_argument("--max-entries", type=int, default=65536)

    report = sub.add_parser("sprites-report", help="Diagnosticar contenido y transparencias de TIM exportados.")
    report.add_argument("--input", required=True, help="Carpeta con manifest.json y PNG.")
    report.add_argument("--output", required=True, help="Ruta del informe JSON.")

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
    if command == "records-analyze":
        result = analyze_records(Path(namespace.input), Path(namespace.output),
                                 max_files=namespace.max_files)
        c = result["counts"]
        print(f"Cabeceras: {c.get('valid_headers', 0)}; "
              f"coincidencias con ancho TIM: {c.get('last_record_width_match', 0)}; "
              f"informe: {namespace.output}")
        return
    if command == "headers-structure":
        result = inspect_header_structure(Path(namespace.input), Path(namespace.output),
                                          max_files=namespace.max_files)
        c = result["counts"]
        print(f"Cabeceras: {c.get('with_prefix', 0)}; "
              f"forma 16+12*N: {c.get('shape_match', 0)}; "
              f"longitud en primer campo: {c.get('length_match', 0)}; "
              f"informe: {namespace.output}")
        return
    if command == "headers-inspect":
        result = inspect_prefixes(Path(namespace.input), Path(namespace.output),
                                  max_files=namespace.max_files)
        print(f"Binarios: {result['files_scanned']}; "
              f"sin prefijo: {result['files_without_prefix']}; "
              f"familias: {len(result['families'])}; informe: {namespace.output}")
        return
    if command == "resources-inspect":
        result = inspect_extractions(Path(namespace.input), Path(namespace.output),
                                     max_files=namespace.max_files)
        print(f"Binarios: {result['file_count']}; "
              f"TIM validados: {result['summary'].get('tim_count', 0)}; "
              f"errores: {result['summary'].get('errors', 0)}; "
              f"informe: {namespace.output}")
        return
    if command == "rlen-batch":
        result = extract_rlen_batch(file_path(namespace.disc),
                                    file_path(namespace.survey),
                                    Path(namespace.output),
                                    max_blocks=namespace.max_blocks)
        print(f"RLEN intentados: {result['attempted']}; "
              f"correctos: {result['successful']}; PNG: {result['png_count']}")
        return
    if command == "rlen-extract":
        result = extract_rlen_at(file_path(namespace.disc), Path(namespace.output),
                                 lba=namespace.lba, offset=namespace.offset)
        print(f"RLEN descomprimido: {result['decompressed_bytes']} bytes; "
              f"PNG: {len(result['previews'])}")
        return
    if command == "disc-survey":
        result = survey_regions(file_path(namespace.disc), Path(namespace.output),
                                max_hits=namespace.max_hits, stride=namespace.stride)
        print(f"Firmas RLEN: {result['rlen_total']}; "
              f"regiones inspeccionadas: {len(result['regions'])}")
        return
    if command == "disc-layout":
        result = analyze_layout(file_path(namespace.disc), Path(namespace.output))
        print(f"Sectores: {result['total_sectors']}; "
              f"regiones no catalogadas: {len(result['unlisted_ranges'])}; "
              f"informe: {namespace.output}")
        return
    if command == "disc-scan-embedded":
        result = scan_embedded_packs(file_path(namespace.disc), Path(namespace.output),
                                     max_sectors=namespace.max_sectors,
                                     max_hits=namespace.max_hits)
        print(f"Sectores revisados: {result['sectors_checked']}; "
              f"PACK internos candidatos: {result['candidates']}; "
              f"busqueda truncada: {result['truncated']}")
        return
    if command == "assets-inventory":
        result = inventory_packs(Path(namespace.input), Path(namespace.output),
                                 export_tim=namespace.export_tim)
        print(f"Contenedores: {result['pack_manifests']}; recursos: {result['members']}; "
              f"tipos: {result['classifications']}")
        return
    if command == "disc-catalog":
        result = catalog_disc(file_path(namespace.disc), Path(namespace.output),
                              max_files=namespace.max_files)
        print(f"Archivos ISO9660: {result['file_count']}; catalogo: {namespace.output}")
        return
    if command == "disc-packs":
        result = scan_disc_packs(file_path(namespace.disc), Path(namespace.output),
                                 extract=namespace.extract, max_extract=namespace.max_extract)
        print(f"Archivos revisados: {result['files_checked']}; "
              f"PACK candidatos: {result['pack_candidates']}")
        return
    if command == "pack-extract":
        result = extract_pack(file_path(namespace.input), Path(namespace.output),
                              max_entries=namespace.max_entries)
        print(f"Entradas PACK: {len(result['entries'])}; TIM completos: "
              f"{sum(e['tim'] is not None for e in result['entries'])}")
        return
    if command == "sprites-report":
        report = build_report(Path(namespace.input), Path(namespace.output))
        print(f"Texturas analizadas: {report['texture_count']}; informe: {namespace.output}")
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
