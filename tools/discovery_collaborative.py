"""Run bounded collaborative research in a private, offline development directory."""

from argparse import ArgumentParser
from contextlib import redirect_stdout
import fcntl
import json
import os
from pathlib import Path
import sys

from learning.agent_factory import Factory, identifier
from learning.discovery.archive import Archive, audit_archive, build_fixture_archive
from learning.discovery.collaborative import (
    SCHEMA, STUDIES, capabilities, result, templates,
)
from learning.discovery.journal import Journal
from learning.discovery.reference_tables import REFERENCE_DIR, reference_rows
from learning.sandbox_lifecycle import run_organization


MARKER = "charlie-collaborative-development-v1"


def prepare(root):
    root.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink() or root.stat().st_uid != os.geteuid() or root.stat().st_mode & 0o077:
        raise PermissionError("use a private development directory")
    marker = root / MARKER
    if not marker.exists():
        if any(root.iterdir()):
            raise ValueError("refusing to initialize a nonempty directory")
        marker.touch(exist_ok=False)
    if marker.is_symlink() or not marker.is_file():
        raise ValueError("invalid development marker")
    if any(path.is_symlink() for path in root.iterdir()):
        raise ValueError("symbolic links in development directory")


def initialize_archive(path):
    if not path.exists():
        documents = list(reference_rows())
        questions = [dict(id=f"study-{number}", question=study.question,
                          track="metrology", priority="start")
                     for number, study in enumerate(STUDIES, 1)]
        build_fixture_archive(path, documents, questions)
    return audit_archive(path)


def finish_record(view):
    turns = {name: task["evidence"] for name, task in view["tasks"].items() if task["evidence"]}
    science = result(turns, "scientist", "CHALLENGE")
    references = result(turns, "researcher", "SOURCE_FINDING")["sources"]
    review_kind = turns["review"]["payload"]["result"]["kind"]
    summary = result(turns, "brief", "SUMMARY")
    evaluation = result(turns, "review", review_kind)
    return dict(status="contradicted" if summary["assessment"] == "contradicted" else "hypothesis",
                findings=[science["check"]["detail"],
                          f"Source comparison status: {summary['assessment']}."],
                citations=[dict(id=source["id"], sha256=source["sha256"]) for source in references],
                checks=[science["check"]], uncertainty=[science["limitation"]],
                followups=[summary["next_question"]],
                collaborative=dict(schema=SCHEMA, stop_reason=summary["stop_reason"],
                                   decision=view["decision"], deadline=view["deadline"],
                                   organization_state=view["state"],
                                   attempts={n: t["attempts"] for n, t in view["tasks"].items()},
                                   evaluation=evaluation, turns=list(turns.values())))


def conduct(root, archive, factory, mission, question_id=None, frozen=False, manifest_sha256=None):
    notebook = root / "research.sqlite3"
    with Journal(notebook) as journal:
        journal.add_questions(archive.questions())
        session = journal.session(mission)
        if session is None:
            active = journal.db.execute("SELECT id FROM sessions WHERE state='in_progress'").fetchone()
            if active is not None:
                raise ValueError(f"resume or cancel incomplete session {active[0]} first")
            if question_id:
                question = next((q for q in archive.questions() if q["id"] == question_id), None)
                if question is None:
                    raise ValueError("question is absent in the pinned demonstration curriculum")
                journal.queue(question["question"], owner=True)
            choice = journal.select()
            if choice is None:
                raise ValueError("no eligible research question")
            session = journal.begin(
                mission, choice["id"], mode="collaborative-development",
                goal=choice["question"], prior=choice["previous_session_id"], frozen=frozen,
                archive_version=archive.version, archive_manifest_sha256=manifest_sha256)
        meta = session["metadata"]
        if (meta.get("mode") != "collaborative-development"
                or meta.get("archive_version") != archive.version
                or meta.get("archive_manifest_sha256") != manifest_sha256
                or (question_id and session["question_id"] != question_id)):
            raise ValueError("session identity does not match this development invocation")
        if session["state"] != "in_progress":
            return session

        def commission(executive):
            executive.select_sandbox_organization(factory, mission, meta["goal"],
                                                  session["question_id"], templates(),
                                                  frozen=meta["frozen"], work_budget=12)

        database = root / "learning-evidence.sqlite3"
        with redirect_stdout(sys.stderr):
            run_organization(database, factory, mission, commission)
        view = factory.inspect(mission)
        if view["state"] == "completed":
            journal.finish(mission, finish_record(view))
        elif view["state"] in {"failed", "cancelled", "expired"}:
            journal.defer(mission, view["state"])
        return dict(session=journal.session(mission), organization=view)


def main(argv=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--sandbox", type=Path, required=True)
    parser.add_argument("action", choices=("run", "inspect", "pause", "resume", "cancel"))
    parser.add_argument("mission")
    parser.add_argument("--question")
    parser.add_argument("--archive", type=Path, help="read-only alternate Discovery archive")
    parser.add_argument("--archive-sha256", help="independently verified alternate manifest digest")
    parser.add_argument("--frozen", action="store_true")
    args = parser.parse_args(argv)
    identifier(args.mission)
    os.umask(0o077)
    root = args.sandbox.absolute()
    if args.action == "inspect":
        with Journal(root / "research.sqlite3", read_only=True) as notebook:
            print(json.dumps(notebook.session(args.mission), indent=2))
        return
    prepare(root)
    if bool(args.archive) != bool(args.archive_sha256):
        parser.error("--archive and --archive-sha256 must be supplied together")
    archive_path = args.archive.resolve() if args.archive else root / "archive"
    if args.archive and (root.is_relative_to(archive_path) or archive_path.is_relative_to(root)):
        parser.error("alternate archive and sandbox directory must be separate")
    provenance = {item["id"]: item for item in json.loads((REFERENCE_DIR / "manifest.json").read_text())}
    with (root / "research.lock").open("a+") as lock:
        if args.action in {"run", "resume"}:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            manifest = (audit_archive(archive_path, args.archive_sha256) if args.archive
                        else initialize_archive(archive_path))
            identity = root / "archive-identity"
            manifest_digest = manifest["manifest_sha256"]
            if identity.exists():
                if identity.read_text() != manifest_digest:
                    raise ValueError("sandbox is already bound to another archive")
            else:
                with identity.open("x") as handle:
                    handle.write(manifest_digest)
            for filename in ("organization.sqlite3", "learning-evidence.sqlite3"):
                ledger = root / filename
                if ledger.exists() and ledger.stat().st_size >= 16 * 1024**2:
                    raise OverflowError("development ledger has reached its byte budget")
        with Archive(archive_path) as archive:
            factory = Factory(root / "organization.sqlite3", capabilities(archive, provenance))
            if args.action in {"pause", "cancel"}:
                getattr(factory, args.action)(args.mission)
                view = factory.inspect(args.mission)
            else:
                if args.action == "resume":
                    try:
                        status = factory.inspect(args.mission)["state"]
                    except KeyError:
                        status = None  # Discovery checkpoint may precede commissioning.
                    if status == "paused":
                        factory.resume(args.mission)
                view = conduct(root, archive, factory, args.mission, args.question, args.frozen,
                               manifest_digest)
    print(json.dumps(view, indent=2))


if __name__ == "__main__":
    main()
