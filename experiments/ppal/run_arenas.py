"""Run with: python3 -m experiments.ppal.run_arenas"""

import argparse
from pathlib import Path

from .arena_suite import evaluate, generated_arenas, named_arenas, report, save_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate PPAL in varied toy arenas")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--random-count", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=80)
    parser.add_argument("--json", type=Path, default=Path("ppal_arenas.json"))
    parser.add_argument("--trace-case", help="print every decision for one named or seeded arena")
    args = parser.parse_args()
    if args.random_count < 0 or args.max_steps < 1:
        parser.error("random-count must be nonnegative and max-steps must be positive")
    arenas = named_arenas() + generated_arenas(args.seed, args.random_count)
    if args.trace_case and not any(arena.name == args.trace_case for arena in arenas):
        parser.error("trace-case must match an arena name in the current run")
    data = report(arenas, args.max_steps)
    save_report(data, args.json)
    for result in data["results"]:
        print(f"{result['arena']:<20} {result['status']:<8} steps={result['steps']:>2} "
              f"rescues={result['rescues']}/{result['targets']} "
              f"shots={result['shots']:>2} hits={result['hits']:>2} evades={result['evades']:>2}")
    summary = data["summary"]
    print(f"TOTAL {summary['total']}  success={summary['successes']} "
          f"death={summary['deaths']} timeout={summary['timeouts']}  report={args.json}")
    if args.trace_case:
        arena = next(arena for arena in arenas if arena.name == args.trace_case)
        trace: list[dict] = []
        evaluate(arena, args.max_steps, trace=trace)
        print(f"TRACE {arena.name}: player={arena.player} targets={arena.targets} threats={arena.threats}")
        for row in trace:
            print(f"{row['tick']:02d} at={row['player']} goal={row['goal']} "
                  f"intent={row['intent']}:{row['intent_target']} "
                  f"move={row['move']} fire={row['fire']} "
                  f"after={row['after']} events={','.join(row['events']) or '-'}")


if __name__ == "__main__":
    main()
