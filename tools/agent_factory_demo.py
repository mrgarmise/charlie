"""Development-only LE organization demonstrations."""
import argparse
from contextlib import closing
from hashlib import sha256
import json
import os
from math import atan2, isfinite
from pathlib import Path
from random import Random
import signal
import subprocess
import sys
from time import monotonic

from learning.agent_factory import Assignment, Capability, Factory, check_worker_lease
from learning.sandbox_executive import SandboxLearningExecutive
from memory.evidence import EvidenceJournal


def synthesize_observation(goal, inputs):
    return {"mode": "synthetic", "unit": "rad", "frame": "model_world",
            "clock": "model_time", "initial_roll": 0, "physical_replay": "unavailable"}


def inspect_visual_replay(goal, inputs):
    try:
        from research.uel.visual import recording
    except ModuleNotFoundError as exc:
        if exc.name not in {"research", "research.uel", "research.uel.visual"}:
            raise
        return synthesize_observation(goal, inputs)

    manifest = Path(recording.__file__).with_name("evidence") / "recording.json"
    views, points, status = recording.ingest(manifest)
    return {
        "mode": "synthetic", "physical_replay": "unavailable",
        "manifest_sha256": sha256(manifest.read_bytes()).hexdigest(),
        "sources": {camera: {"samples": len(features),
                             "missing": sum(feature is None for feature in features)}
                    for camera, (_, _, features) in views.items()},
        "reconstructed_points": len(points), "replay_status": status,
        "example_point": points[0] if points else None,
    }


def simulate(goal, inputs):
    # The UEL adapter owns channel mapping, servo slew and environment stepping.
    from uel_adapter import DogTrial

    results = []
    trial = DogTrial(randomized=True)
    try:
        for seed in range(32):
            rng = Random(seed)
            trial.reset(seed)
            command = [rng.uniform(-.8, .8) if seed else 0 for _ in range(12)]
            peak = 0.0
            stop = "duration"
            for _ in range(20):
                try:
                    trial.step(command, .1)
                except RuntimeError:
                    if not trial.env.ended:
                        raise
                    stop = "environment_terminated"
                    break
                matrix = trial.env.data.xmat[1].reshape(3, 3)
                peak = max(peak, abs(atan2(matrix[2, 1], matrix[2, 2])))
            results.append(dict(seed=seed, peak_roll_rad=peak, stop=stop))
    finally:
        trial.env.close()
    return {"mode": "simulation", "trials": results,
            "criterion": "diagnostic only: DogEnv terminates above 0.7 rad roll or pitch"}


def assess_dog(goal, inputs):
    trials = inputs["batch"]["payload"]["result"]["trials"]
    return {"outcome": "inconclusive", "trials": len(trials),
            "terminated": sum(trial["stop"] == "environment_terminated" for trial in trials),
            "maximum_observed_roll_rad": max(trial["peak_roll_rad"] for trial in trials),
            "skill_qualification": "none", "physical_transfer": "unverified",
            "next_question": "Can a separately validated simulator mode continue through supported floor contact?"}


def search_rollover(goal, inputs, *, attempts=128):
    # The child command is fixed by this trusted adapter. Proposal data never
    # enters the environment, imports, arguments, or filesystem configuration.
    if type(attempts) is not int or attempts not in {8, 16, 128}:
        raise ValueError("unsupported development trial budget")
    command = """
import json
import resource
import sys
resource.setrlimit(resource.RLIMIT_CPU, (18, 19))
resource.setrlimit(resource.RLIMIT_AS, (536870912, 536870912))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
from rollover import run_search
print(json.dumps(run_search(int(sys.argv[1])), allow_nan=False))
"""
    environment = {key: os.environ[key] for key in ("PATH", "PYTHONPATH") if key in os.environ}
    environment.update(PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    argv = [sys.executable, "-c", command, str(attempts)]
    check_worker_lease()
    with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=environment, start_new_session=True) as process:
        deadline = monotonic() + 20
        try:
            while True:
                check_worker_lease()
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError("simulator exceeded its development lease")
                try:
                    stdout, stderr = process.communicate(timeout=min(.2, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, argv, stdout, stderr)
    return {"mode": "simulation", **json.loads(stdout)}


def compare_replay(reference, observation):
    """Estimate an integer sample lag on a labeled synthetic fixture."""
    fields = ("mode", "unit", "frame", "clock", "period_seconds")
    if (any(field not in reference or reference[field] != observation.get(field) for field in fields)
            or reference["mode"] != "synthetic" or reference["period_seconds"] != .02):
        raise ValueError("replay provenance or calibration mismatch")
    expected, measured = reference["samples"], observation["samples"]
    if (len(expected) != len(measured) or len(expected) < 10
            or any(type(value) not in {int, float} or not isfinite(value)
                   for value in expected + measured)):
        raise ValueError("missing aligned replay samples")
    # All hypotheses use the same comparison window.
    errors = [sum((expected[i - lag] - measured[i]) ** 2 for i in range(4, len(expected)))
              for lag in range(5)]
    lag = min(range(5), key=errors.__getitem__)
    if errors.count(errors[lag]) != 1:
        raise ValueError("lag is ambiguous")
    return lag


def synthetic_transfer(goal, inputs):
    meta = dict(mode="synthetic", unit="rad", frame="model_world", clock="fixture",
                period_seconds=.02)
    reference = [0, 0, 1, 0, 0, .5, 0, .25, 0, 0, 0, 0]
    measured = [0, 0] + reference[:-2]
    lag = compare_replay(dict(meta, samples=reference), dict(meta, samples=measured))
    holdout = [0, 0, 0, .5, 0, 0, 1, 0, .75, 0, 0, 0]
    observed = [0, 0] + holdout[:-2]
    original = sum((holdout[i] - observed[i]) ** 2 for i in range(4, len(holdout)))
    fitted = sum((holdout[i - lag] - observed[i]) ** 2 for i in range(4, len(holdout)))
    return {**meta, "lag_seconds": lag * meta["period_seconds"],
            "heldout_no_lag_squared_error": original,
            "heldout_fitted_squared_error": fitted,
            "twin_update": "fixture only"}


def review_transfer(goal, inputs):
    result = inputs["search"]["payload"]["result"]
    replay = inputs["observation"]["payload"]["result"]
    return {"mode": "simulation", "goal_achieved": result["accepted"],
            "source": replay["physical_replay"], "physical_transfer": "unverified",
            "skill_qualification": "none", "attempts": result["attempts"],
            "synthetic_transfer": inputs["transfer"]["digest"],
            "next_question": "Which contact conditions distinguish a half roll from a stable recovery?"}


def investigate(goal, inputs):
    # Synthetic sensor observations of an offset with a held-out measurement.
    calibration = [(0, 2), (10, 12), (20, 22)]
    return {"mode": "synthetic", "estimated_offset": sum(y - x for x, y in calibration) / len(calibration)}


def assess_offset(goal, inputs):
    offset = inputs["estimate"]["payload"]["result"]["estimated_offset"]
    return {"mode": "synthetic", "held_out_residual": abs(32 - offset - 30)}


def explain(view):
    lines = [f"Goal: {view['goal']}", f"State: {view['state']}"]
    if view.get("decision"):
        choice = view["decision"][0]
        lines.append(f"Selected {choice['template']} with rank {choice['value']:.2f} "
                     f"from {choice['samples']} distinct evaluation cases.")
    for assignment in view["nodes"]:
        name = assignment["name"]
        task = view["tasks"][name]
        dependencies = ", ".join(assignment["depends_on"]) or "none"
        lines.append(f"{name} uses {assignment['capability']} and depends on {dependencies}. "
                     f"Attempts: {task['attempts']}.")
        if task["evidence"]:
            result = task["evidence"]["payload"]["result"]
            if "next_question" in result:
                lines.append(result["next_question"])
            if result.get("physical_transfer") == "unverified":
                lines.append("Physical transfer remains unverified.")
    return "\n".join(lines)


def proposal(result, *assignments):
    return {**result, "organization_proposal": json.dumps(
        {"schema": 1, "assignments": list(assignments)})}


def start_rollover(goal, inputs):
    return proposal({"mode": "simulation"},
                    {"name": "replay", "capability": "visual-replay"},
                    {"name": "transfer", "capability": "transfer-supervisor", "depends_on": ["replay"]},
                    {"name": "search", "capability": "search-supervisor", "depends_on": ["transfer"]})


def plan_transfer(goal, inputs):
    estimate = synthetic_transfer(goal, inputs)
    return estimate


def plan_search(goal, inputs):
    # A synthetic lag estimate prioritizes checking the simulated delay range.
    # It never changes the physical twin or motion controls.
    transfer = inputs["transfer"]["payload"]["result"]
    attempts = 16 if transfer["heldout_fitted_squared_error"] < transfer["heldout_no_lag_squared_error"] else 8
    result = search_rollover(goal, inputs, attempts=attempts)
    return proposal({**result, "priority": "actuation-delay robustness",
                     "synthetic_lag_seconds": transfer["lag_seconds"]},
                    {"name": "qualification", "capability": "rollover-evaluator"})


def qualify_search(goal, inputs):
    result = inputs["search"]["payload"]["result"]
    return {"mode": "simulation", "goal_achieved": result["accepted"],
            "attempts": result["attempts"], "physical_transfer": "unverified",
            "skill_qualification": "none"}


def investigate_rig(goal, inputs):
    from tempfile import TemporaryDirectory
    from research.uel.visual.experiment import run
    from research.uel.visual.rig import Rig

    with TemporaryDirectory(prefix="charlie-rig-") as folder:
        return {"mode": "simulation", **run(Rig(), folder, seconds=10)}


def evaluate_rig(goal, inputs, *, calibrated):
    result = inputs["rig"]["payload"]["result"]
    baseline = result["fixed_rms_px"]
    observed = result["rms_px"] if calibrated else baseline
    return {"mode": "simulation", "evaluation_case": result["qualification"],
            "goal_achieved": observed < 1.0, "heldout_rms_px": observed,
            "organization_score": max(0.0, min(1.0, 1.0 - observed / baseline)),
            "skill_qualification": "none"}


def evaluate_calibrated(goal, inputs):
    return evaluate_rig(goal, inputs, calibrated=True)


def evaluate_baseline(goal, inputs):
    return evaluate_rig(goal, inputs, calibrated=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("mission")
    parser.add_argument("action", choices=("dog", "rollover", "dynamic-rollover", "rig", "offset", "status", "explain", "cancel", "pause", "resume", "stop"))
    parser.add_argument("--frozen", action="store_true", help="disable organization experience updates in selection")
    args = parser.parse_args()
    factory = Factory(args.database, [
        Capability("rollover-root", "v1", "supervisor", start_rollover,
                   ("visual-replay", "transfer-supervisor", "search-supervisor")),
        Capability("transfer-supervisor", "v1", "supervisor", plan_transfer),
        Capability("search-supervisor", "v1", "supervisor", plan_search, ("rollover-evaluator",), 24),
        Capability("rollover-evaluator", "v1", "evaluator", qualify_search),
        Capability("visual-rig", "v1", "worker", investigate_rig),
        Capability("rig-calibrated", "v1", "evaluator", evaluate_calibrated),
        Capability("rig-baseline", "v1", "evaluator", evaluate_baseline),
        Capability("observation", "v1", "supervisor", synthesize_observation),
        Capability("visual-replay", "v1", "supervisor", inspect_visual_replay),
        Capability("simulator", "v1", "worker", simulate),
        Capability("rollover-search", "v1", "supervisor", search_rollover),
        Capability("synthetic-transfer", "v1", "worker", synthetic_transfer),
        Capability("transfer-review", "v1", "evaluator", review_transfer),
        Capability("dog-review", "v1", "evaluator", assess_dog),
        Capability("offset", "v1", "worker", investigate),
        Capability("offset-review", "v1", "evaluator", assess_offset),
    ])
    if args.action == "stop":
        factory.stop()
        return
    if args.action in {"cancel", "pause", "resume"}:
        {"cancel": factory.cancel, "pause": factory.pause,
         "resume": factory.resume}[args.action](args.mission)
    if args.action in {"dog", "offset", "rollover", "dynamic-rollover", "rig"}:
        if args.action == "dog":
            goal = "Evaluate the existing Dog simulator as a baseline for roll-over research"
            plan = (Assignment("observation", "observation"),
                    Assignment("batch", "simulator", ("observation",), "observation"),
                    Assignment("assessment", "dog-review", ("batch", "observation")))
        elif args.action == "dynamic-rollover":
            goal = "Investigate Dog rollover with scoped simulation and replay supervisors"
            plan = (Assignment("root", "rollover-root"),)
        elif args.action == "rollover":
            goal = "Search for a continuous Dog roll ending in stable support in simulation"
            plan = (Assignment("observation", "visual-replay"),
                    Assignment("search", "rollover-search", ("observation",), "observation"),
                    Assignment("transfer", "synthetic-transfer", ("observation",)),
                    Assignment("assessment", "transfer-review", ("search", "observation", "transfer")))
        elif args.action == "rig":
            goal = "Estimate visual delay on the existing simulated pan and tilt rig"
            templates = {
                method: (Assignment("rig", "visual-rig"),
                         Assignment("evaluation", f"rig-{method}", ("rig",)))
                for method in ("baseline", "calibrated")
            }
        else:
            goal = "Investigate a synthetic sensor offset"
            plan = (Assignment("estimate", "offset"),
                    Assignment("assessment", "offset-review", ("estimate",)))
        with closing(EvidenceJournal(args.database)) as journal:
            executive = SandboxLearningExecutive(journal, None)
            if args.action == "rig":
                executive.select_sandbox_organization(factory, args.mission, goal, "rig", templates, frozen=args.frozen)
            else:
                limits = {"work_budget": 32} if args.action == "dynamic-rollover" else {}
                executive.commission_sandbox_organization(factory, args.mission, goal, plan, **limits)
            from learning.sandbox_events import LifecyclePublication
            from stimulus.bus import StimulusBus

            with LifecyclePublication(StimulusBus(), factory, args.mission) as publication:
                publication.flush()
                try:
                    while factory.step(args.mission):
                        publication.flush()
                except InterruptedError:
                    if factory.inspect(args.mission)["state"] not in {"paused", "cancelled", "expired"}:
                        raise
                publication.flush()
            executive.retain_sandbox_outcome(factory, args.mission)
    view = factory.inspect(args.mission)
    print(explain(view) if args.action == "explain" else json.dumps(view, indent=2))


if __name__ == "__main__":
    main()
