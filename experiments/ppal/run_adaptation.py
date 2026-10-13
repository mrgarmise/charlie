"""Demonstrate PPAL-6 sequential learning after synthetic shot physics drift."""

import argparse
from pathlib import Path

from .arena_suite import evaluate, generated_arenas, named_arenas
from .shot_learning import ShotAdaptation, ShotModel, brier, collect_shots, save_replay


DEFAULT_MODEL = Path(__file__).parent / "models/synthetic_shot_model.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="PPAL-6 pixel-labeled shot adaptation")
    parser.add_argument("--initial", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--adapted", type=Path, default=Path("ppal6_adapted_model.json"))
    parser.add_argument("--replay", type=Path, default=Path("ppal6_shifted_shots.jsonl"))
    parser.add_argument("--seed", type=int, default=86)
    parser.add_argument("--shots", type=int, default=160)
    parser.add_argument("--held-out", type=int, default=80)
    parser.add_argument("--shot-scale", type=float, default=0.55)
    args = parser.parse_args()
    if args.shots < 16 or args.held_out < 16 or args.shot_scale <= 0:
        parser.error("shots and held-out must be >=16; shot-scale must be positive")
    frozen = ShotModel.load(args.initial)
    observed = collect_shots(args.shots, args.seed, args.shot_scale)
    held_out = collect_shots(args.held_out, args.seed + 1000, args.shot_scale)
    learner = ShotAdaptation(frozen)
    for row in observed:
        learner.accept_example(row)
    if not learner.updates:
        parser.error("shot stream has insufficient hits and misses for adaptation")
    save_replay(observed, args.replay)
    learner.model.save(args.adapted)
    arenas = named_arenas() + generated_arenas(args.seed + 2000, 20)
    frozen_results = [evaluate(arena, shot_model=frozen, shot_lane_scale=args.shot_scale)
                      for arena in arenas]
    adapted_results = [evaluate(arena, shot_model=learner.model, shot_lane_scale=args.shot_scale)
                       for arena in arenas]
    summary = lambda rows: (sum(row["status"] == "success" for row in rows),
                            sum(row["steps"] for row in rows))
    print(f"observed_shots={len(observed)} hits={sum(row.hit for row in observed)} "
          f"updates={learner.updates} held_out={len(held_out)}")
    print(f"held_out_brier frozen={brier(held_out, frozen):.4f} "
          f"adapted={brier(held_out, learner.model):.4f}")
    print(f"held_out_toy_arenas={len(arenas)} frozen_success_steps={summary(frozen_results)} "
          f"adapted_success_steps={summary(adapted_results)}")
    print(f"replay={args.replay} checkpoint={args.adapted} "
          "(synthetic only; no arcade controller commands sent)")


if __name__ == "__main__":
    main()
