"""Versioned, local-only archive builder, audit and bounded read interface."""

import argparse
import csv
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re

from .reference_tables import PINS, REFERENCE_DIR, reference_rows
import sqlite3
import tempfile
from zipfile import ZipFile

MIB = 2**20
SEED_LIMIT = 256 * MIB
HARD_LIMIT = 8 * 1024 * MIB
# A bounded version plus its replacement, research growth and an offline reader.
RESERVES = {"rollback_bytes": SEED_LIMIT, "journal_budget_bytes": 128 * MIB,
            "reader_reserve_bytes": 256 * MIB}
LOCK = json.loads(Path(__file__).with_name("seed-lock.json").read_text())
OUTER = "Charlie_Offline_Reconstruction_Archive_v1.zip"
KNOWLEDGE = "Charlie_Offline_Knowledge_Library_v2.zip"
STARTERS = "Charlie_Starter_Questions_v1.zip"
SUPPLEMENT = "Charlie_Civilization_Inference_Gap_Supplement_v1.zip"
FOUNDATION = "Charlie_First_Principles_Foundation_v1.md"
STOP = set("a an and are as at be by can do does for from how in is it of on or than that the their to what when which why with would".split())
SCHEMA = """
CREATE TABLE content(sha256 TEXT PRIMARY KEY, text TEXT NOT NULL);
CREATE TABLE doc(id TEXT PRIMARY KEY, sha256 TEXT NOT NULL REFERENCES content,
                 kind TEXT NOT NULL, source TEXT NOT NULL, locator TEXT NOT NULL, tags TEXT NOT NULL);
CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED, tags, text, tokenize='porter unicode61');
CREATE TABLE question(id TEXT PRIMARY KEY, data TEXT NOT NULL);
PRAGMA user_version=1;
"""


def encoded(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_bounded(path, cap):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > cap:
        raise ValueError(f"invalid archive input: {path.name}")
    with path.open("rb") as stream:
        data = stream.read(cap + 1)
    if len(data) > cap:
        raise ValueError("source grew past byte budget")
    return data


def members(data):
    with ZipFile(io.BytesIO(data)) as pack:
        entries = pack.infolist()
        if len(entries) > 128 or sum(i.file_size for i in entries) > 16 * MIB:
            raise ValueError("ZIP expansion budget")
        output = {}
        for entry in entries:
            key = PurePosixPath(entry.filename)
            if (entry.is_dir() or key.is_absolute() or ".." in key.parts or "\\" in entry.filename
                    or key.name in output or entry.file_size > 8 * MIB):
                raise ValueError("ambiguous or unsafe ZIP entry")
            output[key.name] = (entry.filename, pack.read(entry))
        return output


def extract_seed(inputs, raw):
    outer = read_bounded(inputs / OUTER, LOCK[OUTER]["bytes"])
    if sha(outer) != LOCK[OUTER]["sha256"]:
        raise ValueError("reconstruction pack checksum")
    pack = members(outer)
    checksum_lines = pack["SHA256SUMS.txt"][1].decode().splitlines()
    if len(checksum_lines) != len(pack) - 1:
        raise ValueError("checksum coverage")
    for line in checksum_lines:
        expected, name = line.split("  ", 1)
        entry, data = pack[PurePosixPath(name).name]
        if entry.split("/", 1)[1] != name or sha(data) != expected:
            raise ValueError("embedded checksum mismatch")
    (raw / OUTER).write_bytes(outer)
    for name, desc in LOCK.items():
        if name == OUTER:
            continue
        data = pack[name][1]
        if sha(data) != desc["sha256"] or len(data) != desc["bytes"]:
            raise ValueError("embedded seed identity")
        # A supplied standalone copy must agree with the immutable nested bytes.
        if (inputs / name).exists() and read_bounded(inputs / name, desc["bytes"]) != data:
            raise ValueError(f"standalone copy disagrees: {name}")
    return pack


def decode_rows(entry):
    return [json.loads(line) for line in entry[1].decode().splitlines() if line.strip()]


def csv_rows(entry):
    return list(csv.DictReader(io.StringIO(entry[1].decode())))


def seed_records(pack):
    knowledge = members(pack[KNOWLEDGE][1])
    supplement = members(pack[SUPPLEMENT][1])
    starter = members(pack[STARTERS][1])
    if knowledge["00_original_foundation_240.md"][1] != pack[FOUNDATION][1]:
        raise ValueError("foundation sources diverged")
    documents = []
    def record(identifier, text, source, kind, locator, tags=""):
        documents.append(dict(id=identifier, text=text, source=source, kind=kind,
                              locator=locator, tags=tags))
    for line_no, line in enumerate(pack[FOUNDATION][1].decode().splitlines(), 1):
        matched = re.fullmatch(r"- \*\*(FP-\d{3}) \[([A-Z])\]\*\* (.+)", line)
        if matched:
            key, category, body = matched.groups()
            record(key, body, "owner foundation", "foundation_" + category,
                   f"{FOUNDATION}#L{line_no}")
    refs = json.loads(knowledge["03_sources.json"][1])
    for line_no, row in enumerate(decode_rows(knowledge["07_knowledge_records.jsonl"]), 1):
        record(row["id"], row["text"] + " [Scope: " + row["scope"] + "]",
               refs[row["source_id"]], row["type"],
               f"{KNOWLEDGE}!07_knowledge_records.jsonl#L{line_no}",
               row["domain"] + " " + row.get("subject", ""))
    sources = {x["id"]: x for x in csv_rows(supplement["source_registry_22.csv"])}
    for i, row in enumerate(decode_rows(supplement["bridge_cards_36.jsonl"]), 1):
        urls = [sources[s]["url"] for s in row["source_ids"].split(";")]
        record(row["id"], row["essential_anchor"] + " [Boundary: " + row["avoid_error"] + "]",
               " ".join(urls), "inherited_bridge", f"{SUPPLEMENT}!bridge_cards_36.jsonl#L{i}",
               row["title"] + " " + row["domain"])
    for name in ("04_calculation_cards.md", "05_physical_constants.md"):
        for line_no, line in enumerate(knowledge[name][1].decode().splitlines(), 1):
            if line.startswith(("- ", "| ")) and not line.startswith("| Symbol"):
                record(f"CARD-{name[:2]}-{line_no}", line, "owner reference card",
                       "inherited_reference", f"{KNOWLEDGE}!{name}#L{line_no}")
    questions = decode_rows(starter["starter_questions.jsonl"])
    gaps = {x["question_id"]: x for x in csv_rows(supplement["question_outcome_gap_map_112.csv"])}
    for row in questions:
        gap = gaps[row["id"]]
        row.update(prerequisites=row["prerequisite_hint"].split(), bridge_ids=gap["bridge_card_ids"].split(";"),
                   gap=gap["likely_gap_or_failure"], gap_status=gap["audit_status"])
    return documents, questions


def selection_matrix(pack):
    result = []
    for row in json.loads(pack["source_manifest.json"][1]):
        # Editorial ordinal scores, explicitly provisional. Unknown sizes stay unranked.
        size = row.get("estimated_mb")
        factors = dict(criticality={"P0": 3, "P1": 2}.get(row["priority"], 1),
                       difficulty_to_rederive=3, actionability=2, expected_question_coverage=1)
        estimated_bytes = round(size * 1_000_000) if isinstance(size, (float, int)) and size > 0 else None
        score = factors["criticality"] * 6 / estimated_bytes if estimated_bytes else None
        result.append(dict(row, offline_present=False, license="unverified", downloaded_bytes=0,
                           normalized_bytes=0, projected_bytes=estimated_bytes, factors=factors,
                           score_per_byte=score, limitation="Owner proposal; coverage and size estimates only",
                           review_before_acquisition=True))
    return result


def populate(path, documents, questions):
    db = sqlite3.connect(path)
    try:
        db.executescript(SCHEMA)
        known = {r["id"] for r in questions}
        if len(known) != len(questions):
            raise ValueError("duplicate question id")
        for row in sorted(questions, key=lambda item: item["id"]):
            if not all(isinstance(row.get(k), str) and row[k].strip() for k in ("id", "track", "question")):
                raise ValueError("missing question fields")
            if set(row.get("prerequisites", [])) - known:
                raise ValueError("unknown prerequisite")
            db.execute("INSERT INTO question VALUES (?,?)", (row["id"], encoded(row).decode()))
        for row in sorted(documents, key=lambda item: item["id"]):
            identifier, kind, source = (row[k] for k in ("id", "kind", "source"))
            body = " ".join(row["text"].split())
            if not body or len(body.encode()) > 8192 or not identifier or len(identifier) > 128:
                raise ValueError("invalid document")
            digest = sha(body.encode())
            locator = row.get("locator", "fixture:" + identifier)
            db.execute("INSERT OR IGNORE INTO content VALUES (?,?)", (digest, body))
            db.execute("INSERT INTO doc VALUES (?,?,?,?,?,?)",
                       (identifier, digest, kind, source, locator, row.get("tags", "")))
            db.execute("INSERT INTO search VALUES (?,?,?)", (identifier, row.get("tags", ""), body))
        db.commit()
    finally:
        db.close()


def make_manifest(stage, kind, documents, questions, matrix, provenance):
    files = {p.relative_to(stage).as_posix(): dict(sha256=sha(p.read_bytes()), bytes=p.stat().st_size)
             for p in sorted(stage.rglob("*")) if p.is_file()}
    counts = {}
    for row in documents:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    version = sha(encoded({"documents": documents, "questions": questions, "provenance": provenance,
                           "schema": 1, "type": kind}))
    manifest = dict(version=version, schema=1, type=kind, counts=counts, questions=len(questions),
                    unique_content=len({" ".join(row["text"].split()) for row in documents}),
                    files=files, provenance=provenance, selection_matrix=matrix,
                    reserves=RESERVES, operational_cap_bytes=HARD_LIMIT,
                    reader="Python 3 >=3.10, sqlite3 with FTS5, UTF-8 text, ZIP; never execute embedded programs",
                    seed_confidence="inherited synthesis; URLs identify cited works, not verification of claims",
                    hazardous_topics="medical, food, chemical, electrical and infrastructure claims require qualified human review")
    (stage / "manifest.json").write_bytes(encoded(manifest) + b"\n")


def materialize(inputs, stage, fixture=None, *, enriched=True):
    raw = stage / "raw"
    raw.mkdir()
    if fixture is not None:
        documents, questions = fixture
        kind, matrix, provenance = "synthetic-fixture", [], {}
    else:
        pack = extract_seed(inputs, raw)
        documents, questions = seed_records(pack)
        kind, matrix = "owner-seed", selection_matrix(pack)
        provenance = {name: dict(desc, locator="raw/" + OUTER +
                                 (("!seed/" + name) if name != OUTER else ""),
                                 offline_present=True, retrieved_utc_date="2026-11-23")
                      for name, desc in LOCK.items()}
        if enriched:
            local = stage / "reference-data"
            local.mkdir()
            for name in PINS:
                (local / name).write_bytes(read_bounded(REFERENCE_DIR / name, 256000))
            for row in reference_rows(local):
                row["locator"] = "reference-data/" + row["locator"]
                documents.append(row)
            for source in json.loads((local / "manifest.json").read_bytes()):
                selected = [r for r in documents if r["source"] == source["id"]]
                normalized = b"\n".join(r["text"].encode() for r in selected)
                provenance[source["id"]] = dict(source, normalized_bytes=len(normalized),
                    normalized_sha256=sha(normalized), records=len(selected))
    populate(stage / "archive.sqlite3", documents, questions)
    make_manifest(stage, kind, documents, questions, matrix, provenance)


def publish(dest, build):
    dest = Path(dest).absolute()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with (dest.parent / ("." + dest.name + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with tempfile.TemporaryDirectory(dir=dest.parent, prefix=".discovery-") as staging:
            stage = Path(staging) / "version"
            stage.mkdir()
            build(stage)
            result = audit_archive(stage)
            if dest.exists():
                prior = audit_archive(dest)
                if prior["version"] != result["version"]:
                    raise FileExistsError("immutable destination already holds another version")
                return prior
            # Flush the closed database and metadata before publishing the directory.
            for path in [*stage.rglob("*"), stage]:
                fd = os.open(path, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            stage.rename(dest)
            fd = os.open(dest.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            return result


def build_archive(inputs, dest, *, enriched=True):
    return publish(dest, lambda stage: materialize(Path(inputs), stage, enriched=enriched))


def build_fixture_archive(dest, documents, questions):
    return publish(dest, lambda stage: materialize(None, stage, (list(documents), list(questions))))


def audit_archive(dest, expected_manifest_sha256=None):
    root = Path(dest)
    manifest_data = read_bounded(root / "manifest.json", MIB)
    if expected_manifest_sha256 is not None and sha(manifest_data) != expected_manifest_sha256:
        raise ValueError("release manifest checksum mismatch")
    manifest = json.loads(manifest_data)
    if manifest["schema"] != 1 or manifest["type"] not in ("owner-seed", "synthetic-fixture"):
        raise ValueError("unknown archive schema")
    inventory = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if inventory != set(manifest["files"]) | {"manifest.json"} or any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("unexpected archive files")
    total = sum((root / name).stat().st_size for name in inventory)
    if total > SEED_LIMIT or total + sum(RESERVES.values()) > HARD_LIMIT:
        raise ValueError("archive capacity")
    for name, desc in manifest["files"].items():
        data = read_bounded(root / name, desc["bytes"])
        if sha(data) != desc["sha256"] or len(data) != desc["bytes"]:
            raise ValueError("archive checksum: " + name)
    if manifest["type"] == "owner-seed":
        if manifest["files"]["raw/" + OUTER]["sha256"] != LOCK[OUTER]["sha256"]:
            raise ValueError("source lock mismatch")
        if "reference-data/manifest.json" in inventory:
            for name, digest in PINS.items():
                if manifest["files"]["reference-data/" + name]["sha256"] != digest:
                    raise ValueError("reference source lock mismatch")
    with Archive(root) as archive:
        if archive.db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("index integrity")
        n = archive.db.execute("SELECT count(*) FROM search").fetchone()[0]
        kinds = dict(archive.db.execute("SELECT kind,count(*) FROM doc GROUP BY kind"))
        if (n != sum(kinds.values()) or kinds != manifest["counts"]
                or len(archive.questions()) != manifest["questions"]):
            raise ValueError("record count mismatch")
    return dict(version=manifest["version"], type=manifest["type"], measured_bytes=total,
                reserved_total_bytes=total + sum(RESERVES.values()), counts=kinds,
                questions=manifest["questions"], manifest_sha256=sha((root / "manifest.json").read_bytes()),
                external_datasets=2 if "reference-data/manifest.json" in inventory else 0,
                manifest_only=len(manifest["selection_matrix"]))


class Archive:
    def __init__(self, directory):
        self.root = Path(directory)
        self.version = json.loads(read_bounded(self.root / "manifest.json", MIB))["version"]
        uri = (self.root / "archive.sqlite3").resolve().as_uri() + "?mode=ro&immutable=1"
        self.db = sqlite3.connect(uri, uri=True)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA trusted_schema=OFF")
        self.db.execute("PRAGMA query_only=ON")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.close()

    def questions(self):
        return [json.loads(row[0]) for row in self.db.execute("SELECT data FROM question ORDER BY id")]

    def get(self, identifier):
        row = self.db.execute("SELECT id,text,source,kind,sha256,locator FROM doc JOIN content USING(sha256) "
                              "WHERE id=?", (identifier,)).fetchone()
        return dict(row) if row else None

    def retrieve(self, text, *, limit=4, budget=1800):
        """BM25 ranking; input never becomes FTS operators. Budget in UTF-8 body bytes."""
        if not isinstance(text, str) or len(text) > 4096 or not 1 <= limit <= 12 or not 1 <= budget <= 8192:
            raise ValueError("retrieval outside budget")
        words = [w for w in re.findall(r"[^\W_]+", text.lower()) if w not in STOP][:20]
        if not words:
            return []
        query = " OR ".join('"' + w + '"' for w in words)
        ids = self.db.execute("SELECT id FROM search WHERE search MATCH ? ORDER BY bm25(search),id LIMIT ?",
                              (query, limit)).fetchall()
        out = []
        for identifier, in ids:
            record = self.get(identifier)
            if not budget:
                break
            data = record["text"].encode()
            record["text"] = data[:budget].decode(errors="ignore")
            record["truncated"] = len(data) > budget
            budget -= len(record["text"].encode())
            if record["text"]:
                out.append(record)
        return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("inputs", type=Path)
    build.add_argument("destination", type=Path)
    build.add_argument("--seed-only", action="store_true")
    audit = sub.add_parser("audit", aliases=["archive-audit"])
    audit.add_argument("destination", type=Path)
    audit.add_argument("--expected-manifest-sha256")
    search = sub.add_parser("search")
    search.add_argument("destination", type=Path)
    search.add_argument("query")
    args = parser.parse_args()
    if args.command == "build":
        result = build_archive(args.inputs, args.destination, enriched=not args.seed_only)
    elif args.command == "search":
        with Archive(args.destination) as archive:
            result = archive.retrieve(args.query)
    else:
        result = audit_archive(args.destination, args.expected_manifest_sha256)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
