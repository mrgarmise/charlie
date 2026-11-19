"""Simulation-only skill export and provenance checks."""

import json
import re
from .experiment import immutable, object_id


def read_object(folder, name):
    if not re.fullmatch("[0-9a-f]{64}", name):
        raise ValueError("expected immutable object id")
    obj = json.loads((folder / (name + ".json")).read_text())
    if object_id(obj) != name:
        raise ValueError("lineage digest mismatch")
    return obj


def practice(sim, folder, qualification):
    report = read_object(folder, qualification)
    candidate = read_object(folder, report["candidate"])
    if (
        not report["passed"]
        or candidate["baseline"] != sim.body.baseline
        or len(candidate["plausible"]) != 1
    ):
        raise ValueError("independent validation required")
    delay = candidate["plausible"][0]
    delays = sorted({max(0, delay - 1), delay, min(4, delay + 1)})
    modes = (
        "stand",
        "squat",
        "step",
        "walk",
        "old-gait",
        "unstable-start",
        "leg-excursion",
        "tripod",
        "recovery",
    )
    skills = {}
    for mode in modes:
        rows = [sim.practice(d, mode, s) for s in (137, 181, 223, 311) for d in delays]
        skills[mode] = dict(
            version=1,
            qualification=qualification,
            hardware_accepted=False,
            simulation_accepted=all(r["accepted"] for r in rows),
            rollouts=rows,
        )
    return immutable(folder, skills), skills
