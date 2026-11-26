"""Import evidence-backed records without silently guessing a legacy file format."""
import argparse
import hashlib
import shutil
from pathlib import Path

from archive import ROOT, load, rebuild, save_brief, validate_brief, write


def preserve(source, root=ROOT):
    source = Path(source).resolve()
    if source.suffix.lower() not in (".html", ".zip", ".json"):
        raise ValueError("Expected original HTML, ZIP or JSON")
    content_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    target = root / "legacy" / content_hash / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    write(target.parent / "provenance.json", {"original_name": source.name,
        "sha256": content_hash, "status": "preserved_not_migrated",
        "notice": "原件仅备份，未推断其结构或历史日期；尚未发布到网站。"})
    print("Original artifact preserved, not yet migrated: " + str(target))


def import_records(source, root=ROOT, revise=False):
    payload = load(source)
    records = payload if isinstance(payload, list) else payload.get("briefs", [payload])
    if not isinstance(records, list):
        raise ValueError("Expected a brief, list of briefs, or {briefs:[...]}")
    dates = set()
    # Validate the entire batch before writing any archive files.
    for brief in records:
        validate_brief(brief)
        if brief["origin"]["kind"] != "historical_import" or not brief["origin"]["reference"].strip():
            raise ValueError("Historical imports require an explicit evidence reference")
        if brief["date"] in dates:
            raise ValueError("Multiple incoming records for the same date")
        dates.add(brief["date"])
        from archive import daily_path
        current = daily_path(root, brief["date"])
        if current.exists() and load(current) != brief and not revise:
            raise ValueError("Existing date requires explicit --revise")
    for brief in records:
        save_brief(root, brief, revise=revise)
    rebuild(root)
    print(f"Imported {len(records)} evidence-backed records")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("--preserve-original", action="store_true")
    p.add_argument("--revise", action="store_true")
    a = p.parse_args()
    if a.preserve_original:
        preserve(a.source)
    else:
        import_records(a.source, revise=a.revise)
