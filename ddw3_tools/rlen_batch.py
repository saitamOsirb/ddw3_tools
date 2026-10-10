"""Batch extraction of RLEN hits previously discovered by disc-survey."""
from __future__ import annotations

import json
from pathlib import Path

from .rlen_extract import extract_rlen_at


def extract_rlen_batch(source: Path, survey: Path, output: Path, *,
                       max_blocks: int = 100) -> dict:
    if max_blocks < 1:
        raise ValueError("max_blocks debe ser positivo")
    report = json.loads(survey.read_text(encoding="utf-8"))
    hits = []
    seen = set()
    for region in report.get("regions", []):
        for hit in region.get("rlen_hits", []):
            key = (int(hit["lba"]), int(hit["sector_offset"]))
            if key not in seen:
                hits.append(key)
                seen.add(key)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for lba, offset in hits[:max_blocks]:
        folder = output / f"lba_{lba:06d}_offset_{offset:04d}"
        try:
            result = extract_rlen_at(source, folder, lba=lba, offset=offset)
            records.append({"lba": lba, "offset": offset, "status": "ok",
                            "decoded_bytes": result["decompressed_bytes"],
                            "png_count": len(result["previews"]),
                            "directory": folder.name})
        except (ValueError, OSError) as exc:
            records.append({"lba": lba, "offset": offset, "status": "error",
                            "error": str(exc)})
    result = {"source": str(source), "survey": str(survey),
              "available_hits": len(hits), "attempted": len(records),
              "successful": sum(x["status"] == "ok" for x in records),
              "png_count": sum(x.get("png_count", 0) for x in records),
              "records": records,
              "note": "The survey stores only its capped rlen_hits, not all occurrences."}
    (output / "rlen_batch.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
