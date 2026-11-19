"""Repeatable headless benchmark. Ground truth is used only after the estimator returns."""

import argparse
import base64
import hashlib
import json
import platform
import resource
import sqlite3
import time
from pathlib import Path

import cv2
import numpy as np

from ..learner import Model
from .__main__ import body
from .camera import fixture, triangulate
from .experiment import run
from .qualification import practice, read_object


def interval(k, n):
    z = 1.96
    p = k / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [float(max(0, center - half)), float(min(1, center + half))]


def audit(sim, folder):
    if folder.exists():
        raise ValueError("benchmark requires a new output directory")
    t = time.perf_counter()
    cpu = time.process_time()
    result = run(sim, folder)
    wall = time.perf_counter() - t
    cpu = time.process_time() - cpu
    with sqlite3.connect(folder / "session.sqlite") as db:
        rows = [
            json.loads(s)
            for s, in db.execute(
                "select payload from events where phase='frame' order by rowid"
            )
        ]
    seen = [r for r in rows if r["feature"]]
    eligible = [r for r in rows if not r["dropped"] and not r["deliberately_occluded"]]
    hidden = [r for r in rows if r["deliberately_occluded"]]
    err = [
        np.linalg.norm(np.subtract(r["feature"]["uv"], r["marker_truth_uv"]))
        for r in seen
    ]
    cam = fixture(sim.body.name)
    xyz = np.array([r["marker_truth_xyz_m"] for r in rows])
    depths = (xyz @ cam.R.T + cam.t)[:, 2]
    b = fixture(sim.body.name, "secondary", 0.025)
    rng = np.random.default_rng(428)
    errs = []
    for p in xyz[::8]:
        uv = {c.camera_id: c.project(p)[0] + rng.normal(0, 0.12, 2) for c in (cam, b)}
        errs.append(np.linalg.norm(triangulate((cam, b), uv, (0, 0), (1, 0)) - p))

    # Reuse the UEL response model used by the dog adapter, with the same pixel and command evidence.
    def matrices(family):
        selected = [r for r in seen if r["family"] in family]
        return (
            np.array([[1.0, *r["command"]] for r in selected]),
            np.array([r["feature"]["uv"] for r in selected]),
        )

    x, y = matrices(["pulse"])
    old = Model.fit(x, y)
    x, y = matrices(["sine", "reverse"])
    old_error = float(np.sqrt(np.mean(np.sum((old.predict(x)[0] - y) ** 2, axis=1))))
    intervals = interval(len(seen), len(eligible))
    result.update(
        host=platform.platform(),
        python=platform.python_version(),
        numpy=np.__version__,
        opencv=cv2.__version__,
        session_bytes=(folder / "session.sqlite").stat().st_size,
        raw_png_bytes=sum(len(base64.b64decode(r["png"])) for r in rows),
        wall_s=wall,
        process_cpu_s=cpu,
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        frames=len(rows),
        retained=len(seen),
        visible_recall=len(seen) / len(eligible),
        visible_wilson95=intervals,
        hidden_false_positives=sum(bool(r["feature"]) for r in hidden),
        hidden_total=len(hidden),
        drops=sum(r["dropped"] for r in rows),
        localization_rms_px=float(np.sqrt(np.mean(np.square(err)))),
        fixture_fov_x_deg=float(np.rad2deg(2 * np.arctan(160 / cam.K[0, 0]))),
        scale_mm_per_px_range=(
            1000 * np.array([min(depths), max(depths)]) / cam.K[0, 0]
        ).tolist(),
        noise_stereo_median_error_mm=float(1000 * np.median(errs)),
        delay_ms=20 * result["delay"],
        injected_ms=60,
        old_linear_response_rms_px=old_error,
        pixels_and_commands_share_sim_clock=True,
        temperature_c=None,
        power_w=None,
        hailo_fps=None,
    )

    def metric_errors(delay):
        distances = []
        angles = []
        for family in ("sine", "reverse"):
            for seed in (47, 61, 83):
                tr = sim.predict(family, seed, 3)
                pred = sim.predict(family, seed, delay)
                distances.extend(np.linalg.norm(tr.xyz - pred.xyz, axis=1))
                if tr.limbs is not None:
                    a = tr.limbs[:, 0, 2] - tr.limbs[:, 0, 1]
                    b = pred.limbs[:, 0, 2] - pred.limbs[:, 0, 1]
                else:
                    a = tr.xyz - [0, 0, 0.1]
                    b = pred.xyz - [0, 0, 0.1]
                cosines = np.sum(a * b, axis=1) / (
                    np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)
                )
                angles.extend(np.rad2deg(np.arccos(np.clip(cosines, -1.0, 1.0))))
        return {
            "mean_distance_mm": 1000 * float(np.mean(distances)),
            "mean_link_angle_error_deg": float(np.mean(angles)),
        }

    result["sim_ground_truth_comparison"] = {
        "fixed": metric_errors(0),
        "fitted": metric_errors(result["delay"]),
    }
    result["heldout_mean_interval_coverage"] = float(
        np.mean(
            [
                v["coverage95"]
                for v in read_object(folder, result["qualification"])["withheld"]
            ]
        )
    )
    result["false_visibility_wilson95"] = interval(
        result["hidden_false_positives"], len(hidden)
    )
    # Recovery frequency over independent observations for every allowed true delay.
    from .fitting import Observations, fit
    from .perception import CPU, render

    correct = 0
    latency = []
    random_correct = 0
    for truth in range(5):
        for seed in (129, 180, 284):
            for selection, name in (
                ("informed", "pulse"),
                ("random", str(rng.choice(["pulse", "still"]))),
            ):
                tr = sim.predict(name, seed, truth)
                features = []
                for uv in cam.project(tr.xyz):
                    frame = render(uv, rng)
                    start = time.perf_counter()
                    features.append(CPU().detect(frame))
                    latency.append(time.perf_counter() - start)
                identified = fit(sim, cam, Observations(name, seed, features))[
                    "plausible"
                ] == [truth]
                if len(features) != len(tr.time):
                    raise ValueError("missing evidence")
                if selection == "informed":
                    correct += identified
                else:
                    random_correct += identified
    result.update(
        correct_delay_trials=int(correct),
        delay_trials=15,
        correct_wilson95=interval(correct, 15),
        random_question_correct=int(random_correct),
        detector_median_ms=1000 * float(np.median(latency)),
        detector_fps=len(latency) / sum(latency),
    )
    if hasattr(sim, "practice"):
        identifier, skills = practice(sim, folder, result["qualification"])
        result["skill_artifact"] = identifier
        result["skills"] = {
            k: dict(
                passed=sum(r["accepted"] for r in v["rollouts"]),
                trials=len(v["rollouts"]),
                worst_tilt_margin_rad=min(r["tilt_margin_rad"] for r in v["rollouts"]),
            )
            for k, v in skills.items()
        }
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=Path)
    p.add_argument("--body", choices=["dog", "rig"], required=True)
    args = p.parse_args()
    print(json.dumps(audit(body(args.body), args.folder), indent=2))
