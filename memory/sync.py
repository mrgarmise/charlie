"""Deliver selected Charlie memories: python3 -m memory.sync."""

import argparse
import json
import os
from pathlib import Path

from .marm import DEFAULT_OUTBOX, MarmClient, MarmOutbox


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outbox", type=Path, default=DEFAULT_OUTBOX)
    parser.add_argument("--url", default=os.environ.get("CHARLIE_MARM_URL", "http://127.0.0.1:8001"))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()
    if args.limit < 1 or args.timeout <= 0:
        parser.error("limit and timeout must be positive")
    try:
        client = MarmClient(args.url, timeout=args.timeout)
    except ValueError as error:
        parser.error(str(error))
    report = MarmOutbox(args.outbox).flush(client, args.limit)
    print(json.dumps(report))
    return 1 if report["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
