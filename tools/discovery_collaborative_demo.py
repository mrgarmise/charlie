"""Run the four offline development sessions in separate interpreter processes."""

from argparse import ArgumentParser
import json
from pathlib import Path
import resource
import subprocess
import sys
from time import perf_counter


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("sandbox", type=Path)
    args = parser.parse_args()
    if args.sandbox.exists() and any(args.sandbox.iterdir()):
        parser.error("demonstration requires a new or empty private directory")
    start = perf_counter()
    sessions = []
    for name, study, flags in (
        ("initial", "study-1", ()),
        ("retained", "study-1", ()),
        ("frozen", "study-1", ("--frozen",)),
        ("timing", "study-2", ()),
    ):
        stdout = subprocess.check_output([
            sys.executable, "-B", "-m", "tools.discovery_collaborative", "--sandbox",
            str(args.sandbox), "run", name, "--question", study, *flags,
        ], timeout=70, text=True)
        run = json.loads(stdout)
        session = run["session"]
        record = session["record"]
        details = record["collaborative"]
        sessions.append(dict(
            id=name, question_id=session["question_id"], prior=session["metadata"]["prior"],
            archive_manifest=session["metadata"]["archive_manifest_sha256"],
            template=run["organization"]["template"], decision=details["decision"],
            charged_turns=run["organization"]["consumed_work_units"],
            budget=run["organization"]["work_budget"], verdict=details["evaluation"],
            sources=record["citations"], next_question=record["followups"][0],
            role_order=list(record["collaborative"]["attempts"]),
        ))
    print(json.dumps(dict(schema="CollaborativeResearchDemo/v1",
                          measurement=dict(elapsed_seconds=round(perf_counter() - start, 3),
                                           child_peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                                           sandbox_file_bytes=sum(p.stat().st_size for p in args.sandbox.rglob("*")
                                                                  if p.is_file())),
                          sessions=sessions), indent=2))


if __name__ == "__main__":
    main()
