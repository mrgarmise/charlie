"""Inspect and correct Charlie's memory judgments."""

import argparse
import json

from .gateway import MemoryGateway


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    listing = actions.add_parser("list", help="show recent candidates, including provisional ones")
    listing.add_argument("--limit", type=int, default=20)
    feedback = actions.add_parser("feedback", help="rate a memory's usefulness")
    feedback.add_argument("id")
    feedback.add_argument("verdict", choices=("helpful", "harmful"))
    feedback.add_argument("--evidence", required=True, help="unique observation or comparison ID")
    feedback.add_argument("--reason", required=True, help="why the verdict is justified")
    correction = actions.add_parser("correct", help="supersede an inaccurate memory")
    correction.add_argument("id")
    correction.add_argument("replacement")
    correction.add_argument("--evidence", required=True)
    correction.add_argument("--reason", required=True)
    args = parser.parse_args()
    gateway = MemoryGateway()
    try:
        if args.action == "list":
            result = gateway.evaluator.recent(args.limit)
        elif args.action == "feedback":
            result = {"recorded": gateway.feedback(args.id, args.verdict,
                                                    args.evidence, args.reason)}
        else:
            gateway.correct(args.id, args.replacement, args.reason, args.evidence)
            result = {"corrected": args.id}
    except (ValueError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
