"""Train and evaluate the PPAL-5 synthetic shot predictor."""

import argparse
from pathlib import Path

from .arena_suite import evaluate, generated_arenas, named_arenas
from .shot_learning import brier, collect_shots, save_replay, train


def main() -> None:
    parser = argparse.ArgumentParser(description="PPAL-5 synthetic pixel-reward training")
    parser.add_argument("--samples", type=int, default=240)
    parser.add_argument("--validation", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--replay", type=Path, default=Path("ppal5_replay.jsonl"))
    parser.add_argument("--model", type=Path, default=Path("ppal5_shot_model.json"))
    args = parser.parse_args()
    if args.samples < 16 or args.validation < 16:
        parser.error("samples and validation must each be at least 16")
    training = collect_shots(args.samples, args.seed)
    validation = collect_shots(args.validation, args.seed + 1000)
    model = train(training)
    save_replay(training, args.replay)
    model.save(args.model)
    baseline = sum(row.hit for row in training) / len(training)
    constant_brier = sum((baseline - row.hit) ** 2 for row in validation) / len(validation)
    print(f"shots training={len(training)} hits={sum(row.hit for row in training)} "
          f"held_out={len(validation)} hits={sum(row.hit for row in validation)}")
    print(f"held_out_brier constant={constant_brier:.4f} learned={brier(validation, model):.4f}")
    arenas = named_arenas() + generated_arenas(42, 20)
    plain = [evaluate(arena) for arena in arenas]
    coached = [evaluate(arena, shot_model=model) for arena in arenas]
    successes = lambda rows: sum(row["status"] == "success" for row in rows)
    steps = lambda rows: sum(row["steps"] for row in rows)
    print(f"toy_arenas={len(arenas)} baseline_success={successes(plain)} "
          f"coached_success={successes(coached)} "
          f"baseline_steps={steps(plain)} coached_steps={steps(coached)}")
    print(f"replay={args.replay} model={args.model} "
          "(synthetic only; no arcade controller commands sent)")


if __name__ == "__main__":
    main()
