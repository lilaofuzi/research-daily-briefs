"""Versioned daily records and reproducible, cross-date indexes."""
import copy
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
TOPICS = ["Mechanobiology", "LLPS", "核力学", "肿瘤免疫", "基金政策"]
LABELS = ["原文", "摘要", "阶段汇总"]
EXCEL_STATUS = "unavailable"
EXCEL_NOTICE = "云端未连接或读取本地 LLPS Excel 数据库；仅对本站归档 DOI 去重，未声称更新 Excel。"


def obj(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


STR = {"type": "string"}
TEXT = {"type": "string", "minLength": 1}
NULL_STR = {"type": ["string", "null"]}
STRINGS = {"type": "array", "items": TEXT}
PAPER_SCHEMA = obj({
    "id": TEXT, "kind": {"enum": ["paper", "policy"]}, "doi": NULL_STR,
    "title": TEXT, "journal": STR, "publication_date": NULL_STR,
    "publication_date_basis": TEXT, "topics": {"type": "array", "minItems": 1,
        "uniqueItems": True, "items": {"enum": TOPICS}},
    "keywords": STRINGS, "summary": TEXT, "significance": STR, "limitations": STR,
    "editors_pick": {"type": "boolean"}, "pick_reason": STR,
    "source_url": TEXT, "evidence_level": {"enum": ["原文", "摘要"]},
    "oa": obj({"status": {"enum": ["verified", "unavailable"]},
               "url": NULL_STR, "evidence_url": NULL_STR}),
    "verification": obj({"status": {"enum": ["automated", "historical_unverified"]},
        "checked_at": STR, "metadata_url": STR, "evidence_url": STR, "evidence_quote": STR,
        "fact_check": STR}),
})
BRIEF_SCHEMA = obj({
    "schema_version": {"const": 1}, "date": TEXT, "title": TEXT,
    "source_label": {"enum": LABELS},
    "period": obj({"start": TEXT, "end": TEXT}),
    "origin": obj({"kind": {"enum": ["github_actions_independent", "historical_import"]},
        "reference": STR, "model": STR}),
    "generated_at": TEXT, "body": STR, "notes": STRINGS,
    "database_status": obj({"llps_excel": {"const": EXCEL_STATUS}, "notice": TEXT}),
    "search_sources": STRINGS,
    "items": {"type": "array", "items": PAPER_SCHEMA},
})


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(encoded(value))
    tmp.replace(path)


def normalize_doi(value):
    if not value:
        return None
    value = unquote(value.strip())
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)", "", value, flags=re.I)
    value = value.strip().rstrip(".,;")
    while value.endswith(")") and value.count(")") > value.count("("):
        value = value[:-1]
    value = value.lower()
    if not re.fullmatch(r"10\.\d{4,9}/[^\s?#]+", value):
        raise ValueError("Invalid DOI format")
    return value


def https_url(value):
    p = urlsplit(value or "")
    return p.scheme == "https" and bool(p.hostname) and not p.username and not p.password


def identity(item):
    if item["doi"]:
        return "doi:" + normalize_doi(item["doi"])
    return "url:" + hashlib.sha256((item["source_url"] + "\n" + item["title"]).encode()).hexdigest()[:24]


def validate_brief(brief):
    Draft202012Validator(BRIEF_SCHEMA).validate(brief)
    day = date.fromisoformat(brief["date"])
    if day.isoformat() != brief["date"]:
        raise ValueError("Archive date must be canonical YYYY-MM-DD")
    start = date.fromisoformat(brief["period"]["start"])
    end = date.fromisoformat(brief["period"]["end"])
    if start > end or end > day:
        raise ValueError("Invalid coverage period")
    if brief["source_label"] != "阶段汇总" and (start != day or end != day):
        raise ValueError("A daily brief must cover its own date")
    ids = set()
    for item in brief["items"]:
        doi = normalize_doi(item["doi"])
        if doi != item["doi"] or item["id"] != identity(item):
            raise ValueError("Noncanonical DOI or item id")
        if item["id"] in ids:
            raise ValueError("Duplicate paper within a brief")
        ids.add(item["id"])
        if not https_url(item["source_url"]):
            raise ValueError("Source URL must be HTTPS")
        if item["publication_date"] and date.fromisoformat(item["publication_date"]) > day:
            raise ValueError("Future publication date")
        if brief["origin"]["kind"] == "github_actions_independent" and not item["publication_date"]:
            raise ValueError("Live generation requires a verified exact publication date")
        if brief["origin"]["kind"] == "github_actions_independent" and item["verification"]["status"] != "automated":
            raise ValueError("Live generation must complete its verification pipeline")
        if brief["origin"]["kind"] == "github_actions_independent" and item["kind"] == "paper" and not doi:
            raise ValueError("Research papers require a DOI")
        if item["kind"] == "policy" and "基金政策" not in item["topics"]:
            raise ValueError("Policy topic missing")
        oa = item["oa"]
        if oa["status"] == "verified":
            if not https_url(oa["url"]) or not https_url(oa["evidence_url"]):
                raise ValueError("OA evidence required")
        elif oa["url"] is not None or oa["evidence_url"] is not None:
            raise ValueError("Unverified OA must not expose a download link")
        if item["editors_pick"] and not item["pick_reason"].strip():
            raise ValueError("Editor's Pick needs a reason")
    for url in brief["search_sources"]:
        if not https_url(url):
            raise ValueError("Invalid search source URL")
    return brief


def daily_path(root, day):
    date.fromisoformat(day)
    return Path(root) / "archive" / day[:4] / day[5:7] / (day + ".json")


def save_brief(root, brief, revise=False):
    brief = validate_brief(copy.deepcopy(brief))
    current = daily_path(root, brief["date"])
    if current.exists():
        old = load(current)
        if old == brief:
            return False
        if not revise:
            raise ValueError("Date already archived; explicit --revise required")
        # Also preserve records imported before the version store was introduced.
        write(Path(root) / "history" / brief["date"] / (digest(old) + ".json"), old)
    version = Path(root) / "history" / brief["date"] / (digest(brief) + ".json")
    if version.exists() and load(version) != brief:
        raise ValueError("Version hash collision")
    write(version, brief)
    write(current, brief)
    return True


def indexes(root):
    root = Path(root)
    briefs, papers = [], {}
    current_files = sorted((root / "archive").glob("*/*/*.json"))
    for path in current_files:
        b = validate_brief(load(path))
        if path != daily_path(root, b["date"]):
            raise ValueError("Archive path does not match record date")
        versions = []
        for version in sorted((root / "history" / b["date"]).glob("*.json")):
            prior = validate_brief(load(version))
            if prior["date"] != b["date"] or version.stem != digest(prior):
                raise ValueError("Corrupt history version")
            versions.append({"path": version.relative_to(root).as_posix(),
                             "generated_at": prior["generated_at"], "hash": version.stem})
        if not any(v["hash"] == digest(b) for v in versions):
            raise ValueError("Current record has no immutable version; use the import command")
        briefs.append({"date": b["date"], "title": b["title"], "source_label": b["source_label"],
            "period": b["period"], "origin": b["origin"]["kind"],
            "path": path.relative_to(root).as_posix(), "hash": digest(b),
            "topics": sorted({t for p in b["items"] for t in p["topics"]}),
            "paper_ids": [p["id"] for p in b["items"]], "versions": versions})
        for item in b["items"]:
            record = papers.setdefault(item["id"], {"id": item["id"], "metadata": item,
                "occurrences": [], "metadata_versions": []})
            record["metadata"] = item
            record["occurrences"].append({"date": b["date"], "path": path.relative_to(root).as_posix(),
                "metadata_hash": digest(item),
                "source_label": b["source_label"], "topics": item["topics"],
                "editors_pick": item["editors_pick"], "pick_reason": item["pick_reason"],
                "keywords": item["keywords"], "summary": item["summary"], "title": item["title"]})
    # Keep old metadata even when a correction removes a paper from the current brief.
    for version in sorted((root / "history").glob("*/*.json")):
        b = validate_brief(load(version))
        if version.stem != digest(b) or version.parent.name != b["date"]:
            raise ValueError("Corrupt history version")
        for item in b["items"]:
            record = papers.setdefault(item["id"], {"id": item["id"], "metadata": item,
                "occurrences": [], "metadata_versions": []})
            h = digest(item)
            found = next((v for v in record["metadata_versions"] if v["hash"] == h), None)
            if found is None:
                found = {"hash": h, "metadata": item, "sources": []}
                record["metadata_versions"].append(found)
            found["sources"].append(version.relative_to(root).as_posix())
    return ({"schema_version": 1, "briefs": briefs, "latest_date": briefs[-1]["date"] if briefs else None,
             "historical_import_status": "not_imported" if not any(b["origin"] == "historical_import" for b in briefs) else "imported",
             "database_status": {"llps_excel": EXCEL_STATUS, "notice": EXCEL_NOTICE}},
            {"schema_version": 1, "papers": sorted(papers.values(), key=lambda p: p["id"])})


def rebuild(root=ROOT):
    index, papers = indexes(root)
    write(Path(root) / "data/index.json", index)
    write(Path(root) / "data/papers.json", papers)
    return index, papers


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    if args.check:
        index, papers = indexes(ROOT)
        if index != load(ROOT / "data/index.json") or papers != load(ROOT / "data/papers.json"):
            raise SystemExit("Indexes are stale; run python scripts/archive.py")
        print("Archive, version hashes and indexes verified")
    else:
        rebuild()
