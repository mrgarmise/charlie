"""Local operator CLI. Use python -m tools.discovery --help."""

import argparse
import json
import os
from pathlib import Path
import sys

from learning.discovery.conversation import respond
from learning.discovery.journal import Journal


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--archive", required=True, type=Path)
    ask = commands.add_parser("ask")
    ask.add_argument("text")
    ask.add_argument("--question-id")
    ask.add_argument("--session-id")
    queue = commands.add_parser("queue")
    queue.add_argument("topic")
    correct = commands.add_parser("correct")
    correct.add_argument("session_id")
    correct.add_argument("note")
    backup = commands.add_parser("snapshot", help="back up or restore to a new private notebook")
    backup.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.command == "init":
            from learning.discovery.archive import Archive
            if args.journal.resolve().is_relative_to(args.archive.resolve()):
                raise ValueError("journal must be outside the immutable archive")
            with Archive(args.archive) as archive, Journal(args.journal) as journal:
                journal.add_questions(archive.questions())
                result = dict(text="Initialized research notebook.", next_question=journal.select())
        else:
            # The private file and current OS uid authenticate the local operator.
            # "ask" always opens read-only; unauthenticated text cannot choose a mutation.
            with Journal(args.journal, read_only=args.command in ("ask","snapshot")) as journal:
                if args.command == "ask":
                    result = respond(journal,args.text,question_id=args.question_id,session_id=args.session_id)
                elif args.command == "queue":
                    result = respond(journal,"Keep thinking about " + args.topic,owner=True)
                elif args.command == "snapshot":
                    journal.snapshot(args.destination)
                    result = dict(text="Saved verified research notebook snapshot.")
                else:
                    journal.correct(args.session_id,args.note,owner=True)
                    result = dict(text="Recorded owner correction.",session_id=args.session_id)
    except (ValueError, PermissionError, OSError, KeyError) as exc:
        print(str(exc),file=sys.stderr)
        return 2
    print(json.dumps(result,ensure_ascii=False,indent=2) if args.json else result["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
