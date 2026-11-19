"""Headless experiment orchestration. Each completed trajectory is a resumable checkpoint."""

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np
from ..core import Channel, Journal, Profile, encode
from ..inquiry import Question, choose, investigate
from .camera import fixture
from .fitting import Observations, fit, validate
from .perception import render
from .replay import capture


def object_id(obj):
    return hashlib.sha256(encode(obj).encode()).hexdigest()


def immutable(folder, obj):
    name = object_id(obj)
    path = folder / (name + ".json")
    if (
        not path.exists()
        and sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
        + len(encode(obj).encode())
        > 16_000_000
    ):
        raise ValueError("session directory budget exceeded")
    if path.exists():
        if path.read_text() != encode(obj):
            raise ValueError("corrupt lineage")
    else:
        import os, tempfile

        with tempfile.NamedTemporaryFile(dir=folder, mode="w", delete=False) as f:
            f.write(encode(obj))
        try:
            try:
                os.link(f.name, path)
            except FileExistsError:
                if path.read_text() != encode(obj):
                    raise ValueError("lineage collision")
        finally:
            os.unlink(f.name)
    return name


def question(sim, cam):
    questions = []
    for family in ("still", "pulse"):
        a = cam.project(sim.predict(family, 11, 0).xyz)
        b = cam.project(sim.predict(family, 11, 4).xyz)
        value = float(np.linalg.norm(a - b, axis=1).mean())
        questions.append(
            Question(
                family,
                "visual-delay",
                "experimental",
                "Which delay predicts the visible marker?",
                True,
                value,
                0.1,
            )
        )
    return choose(questions)


def run(sim, folder, *, truth=3, seconds=60):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    cam = fixture(sim.body.name)
    q = question(sim, cam)
    profile = Profile(
        sim.body.name,
        sim.body.baseline,
        (Channel("fixture", "normalized", -1, 1),),
        (Channel("pixel", "px", -10000, 10000),),
        (0.0,),
    )
    journal = Journal(
        folder / "session.sqlite",
        "synthetic-" + str(truth),
        profile,
        "visual-v1",
        8_000_000,
    )
    deadline = time.monotonic() + seconds
    try:
        return cycle(sim, cam, folder, journal, q, truth, deadline)
    finally:
        journal.db.close()


def cycle(sim, cam, folder, journal, q, truth, deadline):
    from .perception import Feature

    plan = [(q.key, 11), ("still", 12)] + [
        (f, s) for f in ("sine", "reverse") for s in (47, 61, 83)
    ]
    data = []
    for k, (family, seed) in enumerate(plan):
        if time.monotonic() > deadline or (folder / "CANCEL").exists():
            raise TimeoutError("checkpoint retained")
        rows = [
            row
            for _, phase, row in journal.read()
            if phase == "frame" and (row["family"], row["seed"]) == (family, seed)
        ]
        if [r["index"] for r in rows] != list(range(len(rows))):
            raise ValueError("noncontiguous trajectory checkpoint")
        features = [Feature(**r["feature"]) if r["feature"] else None for r in rows]
        trajectory = sim.predict(family, seed, truth)
        if len(rows) < len(trajectory.time):
            features.extend(
                capture(journal, cam, trajectory, family, seed, k * 100, skip=len(rows))
            )
        data.append(Observations(family, seed, features))
    candidate = fit(sim, cam, data[0])
    candidate["training_digest"] = object_id(
        [asdict(f) if f else None for f in data[0].features]
    )
    candidate["calibration_digest"] = object_id(
        {
            k: v.tolist() if isinstance(v, np.ndarray) else v
            for k, v in asdict(cam).items()
        }
    )
    candidate_id = immutable(folder, candidate)
    report = validate(sim, cam, candidate, data[2:])
    report["candidate"] = candidate_id
    if not report.get("passed") and "withheld" not in report:
        return dict(
            body=asdict(sim.body),
            candidate=candidate_id,
            qualification=immutable(folder, report),
            passed=False,
            reason=report["reason"],
            plausible=candidate["plausible"],
        )

    qualification_id = immutable(folder, report)
    ambiguous = fit(sim, cam, data[1])
    selected = candidate["plausible"][0]
    sample = data[2]
    observed = [f.uv[0] for f in sample.features if f]

    def predicted(delay):
        return [
            float(p[0])
            for p, f in zip(
                cam.project(sim.predict(sample.family, sample.seed, delay).xyz),
                sample.features,
            )
            if f
        ]

    prior = list(journal.read())
    if not any(phase == "inquiry" for _, phase, _ in prior):
        investigate(
            journal,
            900,
            q,
            {"baseline": predicted(0), "candidate": predicted(selected)},
            observed,
            1.0,
            [qualification_id],
        )
    uv = cam.project(sim.predict(sample.family, sample.seed, selected).xyz)
    frame = np.full((240, 320, 3), 22, np.uint8)
    for i, (p, f) in enumerate(zip(uv, sample.features)):
        if f:
            cv2.circle(frame, tuple(np.rint(p).astype(int)), 4, (0, 155, 255), 1)
            cv2.circle(frame, tuple(np.rint(f.uv).astype(int)), 1, (255, 240, 100), -1)
    cv2.putText(
        frame,
        "ring: twin  dot: observed (pixels)",
        (5, 230),
        0,
        0.44,
        (240, 240, 240),
        1,
    )
    cv2.imwrite(str(folder / "overlay.png"), frame)
    return dict(
        body=asdict(sim.body),
        candidate=candidate_id,
        qualification=qualification_id,
        delay=selected,
        passed=report["passed"],
        ambiguous=ambiguous["plausible"],
        rms_px=report["mean_rms_px"],
        ci95=report["trajectory_bootstrap95"],
        fixed_rms_px=float(np.mean([r["fixed"] for r in report["withheld"]])),
        random_rms_px=float(np.mean([r["random"] for r in report["withheld"]])),
        proposal={
            "objective": "observe a stationary metric reference board",
            "authorization": "operator review pending",
            "hardware_accepted": False,
        },
    )
