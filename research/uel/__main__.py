"""Run one bounded, deterministic simulation session."""

import argparse

from .core import Journal, Session, encode
from .synthetic import LinearTwin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    parser.add_argument("--session", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()
    simulator = LinearTwin()
    journal = Journal(args.database, args.session, simulator.profile, args.revision)
    if args.export:
        for trial, phase, payload in journal.read():
            print(encode({"trial": trial, "phase": phase, "payload": payload}))
        return
    session = Session(simulator, journal, trials=args.trials, seconds=10)
    probes = ((0.0, 0.0), (0.5, 0.0), (-0.5, 0.0), (0.0, 0.5), (0.0, -0.5))
    for trial in range(session.next_trial, args.trials):
        session.run(probes[trial % len(probes)], 0.1, trial)
    session.cancel("session complete")


if __name__ == "__main__":
    main()
