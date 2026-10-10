"""Inventory extracted DW3 PACK members without assuming each TIM is a sprite."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .sprites import MAGIC, parse_tim


def classify_member(data: bytes, *, max_tim: int = 100) -> dict:
    """Report complete TIM structures at any byte offset within a member."""
    found = []
    cursor = 0
    while len(found) < max_tim:
        offset = data.find(MAGIC, cursor)
        if offset < 0:
            break
        tim = parse_tim(data, offset)
        if tim is not None:
            found.append({
                "offset": offset, "length": tim["end"] - offset,
                "width": tim["width"], "height": tim["height"],
                "bpp": tim["bpp"], "palettes": len(tim["palettes"]),
                "image_position": tim["image_position"],
                "clut_position": tim["clut_position"],
            })
            cursor = tim["end"]
        else:
            cursor = offset + 4
    return {
        "bytes": len(data), "tim_count": len(found), "tim": found,
        "tim_limit_reached": len(found) == max_tim,
        "classification": (
            "tim_at_start" if found and found[0]["offset"] == 0
            else "embedded_tim" if found else "unclassified"
        ),
    }


def inventory_packs(folder: Path, output: Path, *,
                    max_member_bytes: int = 32 * 1024 * 1024) -> dict:
    """Inspect outputs from pack-extract or disc-packs --extract."""
    manifests = sorted(folder.rglob("pack_manifest.json"))
    entries = []
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for member in manifest.get("entries", []):
            filename = member.get("file")
            if not filename:
                continue
            path = manifest_path.parent / filename
            if not path.is_file():
                continue
            if path.stat().st_size > max_member_bytes:
                entries.append({"path": str(path.relative_to(folder)),
                                "classification": "too_large",
                                "bytes": path.stat().st_size})
                continue
            info = classify_member(path.read_bytes())
            entries.append({"path": str(path.relative_to(folder)), **info})
    counts = dict(Counter(x["classification"] for x in entries))
    result = {
        "root": str(folder), "pack_manifests": len(manifests),
        "members": len(entries), "classifications": counts,
        "entries": entries,
        "note": "TIM identification does not establish character identity or animation frames.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
