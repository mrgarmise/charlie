from datetime import datetime, timezone
import sqlite3

import pytest

from learning.discovery.conversation import respond
from learning.discovery.journal import Journal


@pytest.fixture
def questions():
    return [dict(id="plant",question="What do plants use for energy?",track="life_sciences",priority="start"),
            dict(id="yield",question="What determines crop yield?",track="life_sciences",prerequisites=["plant"]),
            dict(id="trade",question="How can trade change productivity?",track="civilization")]


def test_restart_dedup_snapshot_and_calendar_boundaries(tmp_path, questions):
    book, snap = tmp_path/"book", tmp_path/"backup"
    with Journal(book) as j:
        j.add_questions(questions)
        j.add_questions(questions)
        assert j.db.execute("SELECT count(*) FROM questions").fetchone()[0] == 3
        with pytest.raises(ValueError):
            j.add_questions([dict(questions[0],question="Drift")])
        start = datetime(2026,4,1,tzinfo=timezone.utc).timestamp()
        j.begin("session","plant",now=start)
        assert respond(j,"What have you been thinking about lately?",now=start)["digest"]["in_progress_question_ids"] == ["plant"]
        j.finish("session",dict(status="hypothesis",findings=["A proposed explanation."],citations=["bk-01"],
                                uncertainty=["Missing measurements."],followups=["Which measurements are missing?"]),now=start)
        j.snapshot(snap)
        with pytest.raises(FileExistsError):
            j.snapshot(snap)
    with Journal(snap,read_only=True) as j:
        assert "A proposed explanation." in respond(j,"What did you discover about plants?")["text"]
        assert respond(j,"What questions have you been pondering this week?",now=start+7*86400-1)["digest"]["completed_sessions"]
        assert not respond(j,"What questions have you been pondering this week?",now=start+7*86400)["digest"]["completed_sessions"]
        assert "yield" not in [q["id"] for q in j._choices(start+7*86400)]
        with pytest.raises(PermissionError):
            respond(j,"Keep thinking about trees",owner=True)


def test_atomic_failures_recovery_and_duplicate_dispatch(tmp_path,questions):
    book = tmp_path/"book"
    with Journal(book) as left, Journal(book) as right:
        left.add_questions(questions,now=1)
        left.begin("s1","plant",now=2)
        with pytest.raises(ValueError):
            right.begin("s2","plant",now=2)
        left.checkpoint("s1","RETRIEVE",dict(ids=["A"]),now=3)
        with pytest.raises(ValueError):
            left.checkpoint("s1","SELECT",{},now=4)
        with pytest.raises(ValueError):
            left.finish("s1",dict(status="verified_formal",checks=[{"valid":False}],followups=["bad"]),now=5)
        with pytest.raises(ValueError):
            left.finish("s1",dict(status="unknown",followups=["new",""]),now=5)
        assert left.db.execute("SELECT count(*) FROM questions").fetchone()[0] == 3
        right.begin("s2","plant",now=3603)
        assert left.session("s1")["state"] == "deferred"
        assert left.session("s1")["checkpoint"] == {"ids":["A"]}
        with pytest.raises(ValueError):
            left.finish("s1",dict(status="unknown"),now=3603)
        right.defer("s2","stopped",now=3604)
        with pytest.raises(ValueError):
            left.begin("s3","plant",now=3700)
        assert "stopped" in respond(left,"What are you stuck on?",now=3700)["text"]


def test_owner_queue_corrections_and_source_immutability(tmp_path, questions):
    with Journal(tmp_path/"book") as j:
        j.add_questions(questions)
        with pytest.raises(PermissionError):
            respond(j,"Keep thinking about dams")
        q = respond(j,"Keep thinking about dams",owner=True)["next_question"]
        qid = q["id"]
        assert "owner" in q["selection_reason"]
        assert qid == j.queue("Dams!",owner=True)
        assert "queued" in respond(j,"Have you actually investigated this?",question_id=qid)["text"]
        j.begin("s",qid)
        j.finish("s",dict(status="contradicted",findings=["Conflicting values under the same reported scope."],
                          uncertainty=["Check original reports."],citations=["A","B"]))
        with pytest.raises(PermissionError):
            j.correct("s","Different date")
        j.correct("s","The archive later identified different dates.",owner=True)
        assert "different dates" in respond(j,"What changed your mind?")["text"]
        assert "Conflicting" in respond(j,"Show me the evidence for that conclusion.",session_id="s")["text"]
        assert "owner" in respond(j,"Why did you choose that question?",session_id="s")["text"]
        assert qid not in [x["id"] for x in j._choices(10**10)]
        with pytest.raises(sqlite3.IntegrityError):
            j.db.execute("DELETE FROM events")


def test_journal_refuses_foreign_database_or_public_paths(tmp_path):
    book = tmp_path/"book"
    with sqlite3.connect(book) as db:
        db.execute("CREATE TABLE other(v)")
    book.chmod(0o600)
    with pytest.raises(ValueError):
        Journal(book)
    book.chmod(0o644)
    with pytest.raises(PermissionError):
        Journal(book)
