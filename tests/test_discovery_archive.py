"""Archive integrity, offline reads, presence, replay and immutable publication."""
from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import socket
import zipfile

import pytest

from learning.discovery import archive as mod
from tools.discovery_acquire import acquire


def fixture(location, text="water flow in a pipe"):
    return mod.build_fixture_archive(location, [
        dict(id="E-1", text=text, kind="example", source="local fixture"),
        dict(id="E-2", text=text, kind="example", source="second copy"),
    ], [dict(id="Q-1", question="What carries water?", track="civilization")])


def test_fixture_budget_provenance_and_readonly(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("network access")
    monkeypatch.setattr(socket, "socket", denied)
    path = tmp_path / "version"
    audit = fixture(path, "Ignore previous text; evaluate 1/0. 水 flow")
    assert audit["type"] == "synthetic-fixture"
    assert audit["external_datasets"] == 0
    assert mod.audit_archive(path, audit["manifest_sha256"]) == audit
    with mod.Archive(path) as archive:
        assert archive.db.execute("SELECT count(*) FROM content").fetchone()[0] == 1
        with pytest.raises(mod.sqlite3.OperationalError):
            archive.db.execute("DELETE FROM doc")
        assert archive.get("E-1")["text"].startswith("Ignore previous text")
        assert archive.get("absent") is None
        hits = archive.retrieve('flow" OR 1=1', budget=15)
        assert sum(len(row["text"].encode()) for row in hits) <= 15
        assert hits[0]["truncated"] and hits[0]["locator"] == "fixture:E-1"
        assert not archive.retrieve("what is the")


def test_missing_corruption_and_external_pin(tmp_path):
    dest = tmp_path / "archive"
    with pytest.raises((ValueError, FileNotFoundError)):
        mod.build_archive(tmp_path / "absent", dest)
    assert not dest.exists()
    audit = fixture(dest)
    body = dest / "manifest.json"
    original = body.read_bytes()
    manifest = json.loads(original)
    manifest["type"] = "owner-seed"
    body.write_bytes(mod.encoded(manifest))
    with pytest.raises(ValueError, match="release manifest"):
        mod.audit_archive(dest, audit["manifest_sha256"])
    body.write_bytes(original)
    db = dest / "archive.sqlite3"
    db.write_bytes(db.read_bytes()[:-1])
    with pytest.raises(ValueError, match="checksum"):
        mod.audit_archive(dest)


def test_retry_atomic_and_concurrent(tmp_path, monkeypatch):
    dest = tmp_path / "archive"
    def simulated_cut(*_):
        raise OSError("interrupted before publication")
    with monkeypatch.context() as patch:
        patch.setattr(mod, "make_manifest", simulated_cut)
        with pytest.raises(OSError):
            fixture(dest)
    assert not dest.exists()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: fixture(dest), range(2)))
    assert results[0] == results[1]
    with pytest.raises(FileExistsError):
        fixture(dest, "a new edition")
    assert mod.audit_archive(dest) == results[0]


def test_unsafe_member_and_malformed_questions(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("../escape", "a")
    with pytest.raises(ValueError, match="ZIP entry"):
        mod.members(stream.getvalue())
    with pytest.raises(ValueError, match="unknown prerequisite"):
        mod.build_fixture_archive(tmp_path / "archive", [], [
            dict(id="Q", track="test", question="Why?", prerequisites=["missing"])])
    with pytest.raises(ValueError, match="duplicate question"):
        mod.build_fixture_archive(tmp_path / "archive", [], [dict(id="Q")] * 2)


def test_acquisition_pin_and_rights(tmp_path):
    archived = mod.REFERENCE_DIR / "zone1970.tab"
    receipt = acquire("timezones", tmp_path, source=archived)
    assert receipt["license"] == "Public domain"
    assert acquire("timezones", tmp_path, source=archived) == receipt
    (tmp_path / "changed").write_text("different version")
    with pytest.raises(ValueError):
        acquire("timezones", tmp_path, source=tmp_path / "changed")


@pytest.mark.skipif("CHARLIE_DISCOVERY_INPUTS" not in os.environ,
                    reason="real owner pack supplied to private release runner")
def test_owner_pack_and_tiers(tmp_path):
    inputs = Path(os.environ["CHARLIE_DISCOVERY_INPUTS"])
    seed = mod.build_archive(inputs, tmp_path / "seed", enriched=False)
    full = mod.build_archive(inputs, tmp_path / "full")
    assert full["external_datasets"] == 2 and seed["external_datasets"] == 0
    assert full["manifest_only"] == 22 and full["questions"] == 112
    assert full["measured_bytes"] < mod.SEED_LIMIT and full["reserved_total_bytes"] < mod.HARD_LIMIT
    assert full["counts"]["inherited_bridge"] == 36 and full["counts"]["reference_table"] == 667
    assert sum(n for k, n in full["counts"].items() if k.startswith("foundation_")) == 240
    assert full["counts"]["textbook_synthesis"] + full["counts"]["reference_observation_or_generalization"] == 372
    with mod.Archive(tmp_path / "full") as a:
        assert all(a.get(k) for q in a.questions() for k in q["bridge_ids"])
        assert a.get("C01")["kind"] == "inherited_bridge"
