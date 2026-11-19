"""Read a bounded v1 local recording manifest. Never open a URI or a live camera."""

import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from .camera import (
    Camera,
    pair_frames,
    sync,
    triangulate,
    verify_world,
    stereo_covariance,
)
from .perception import Aruco, CPU
from .replay import CameraSource


def local_file(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("invalid local recording path")
    return path


def ingest(manifest):
    root = manifest.resolve().parent
    if manifest.stat().st_size > 2_000_000:
        raise ValueError("manifest budget exceeded")
    doc = json.loads(manifest.read_text())
    if doc["version"] != 1 or len(doc["sources"]) not in (1, 2):
        raise ValueError("expected one or two v1 sources")
    views = {}
    remaining = 32_000_000
    for stream in doc["sources"]:
        spec = CameraSource(**stream["source"])
        if (
            spec.backend not in ("recording", "synthetic", "imx708", "elegoo_optional")
            or spec.camera_id in views
        ):
            raise ValueError("unsupported or duplicate camera")
        profile = stream.get("calibration")
        cam = Camera(**profile) if profile else None
        if cam and (cam.camera_id != spec.camera_id or not spec.calibration_id):
            raise ValueError("calibration identity mismatch")
        detector = Aruco(stream["aruco_id"]) if "aruco_id" in stream else CPU()
        if spec.backend != "synthetic" and not isinstance(detector, Aruco):
            raise ValueError("recorded camera requires a specified marker")
        features = []
        times = []
        if len(stream["frames"]) > 4096:
            raise ValueError("too many frames")
        for row in stream["frames"]:
            t = row["time_s"]
            if not np.isfinite(t) or times and t <= times[-1]:
                raise ValueError("invalid exposure timestamps")
            times.append(t)
            if row.get("dropped"):
                features.append(None)
                continue
            path = local_file(root, row["path"])
            remaining -= path.stat().st_size
            if remaining < 0:
                raise ValueError("recording exceeds byte budget")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError("recorded hash mismatch")
            from PIL import Image
            import io

            with Image.open(io.BytesIO(raw)) as img:
                if img.width * img.height > 4_000_000:
                    raise ValueError("frame dimensions exceed budget")
            frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("invalid image")
            features.append(detector.detect(frame))
        views[spec.camera_id] = (cam, times, features)
    points = []
    status = "independent 2D"
    streams = list(views.values())
    if (
        len(streams) == 2
        and all(s[0] is not None for s in streams)
        and doc.get("world_references")
        and doc.get("sync_events")
    ):
        a, b = streams
        verify_world((a[0], b[0]), doc["world_references"])
        clock = sync(*doc["sync_events"])
        for i, j, skew in pair_frames(a[1], b[1], clock):
            if a[2][i] and b[2][j]:
                coords = {a[0].camera_id: a[2][i].uv, b[0].camera_id: b[2][j].uv}
                xyz = triangulate((a[0], b[0]), coords, (a[1][i], b[1][j]), clock)
                cov = stereo_covariance(
                    (a[0], b[0]),
                    coords,
                    (a[1][i], b[1][j]),
                    clock,
                    (a[2][i].sigma_px, b[2][j].sigma_px),
                )
                points.append(
                    dict(
                        indices=[i, j],
                        xyz_m=xyz.tolist(),
                        covariance_m2=cov.tolist(),
                        skew_s=skew,
                    )
                )
        if points:
            status = "metric stereo"
    return views, points, status


def aligned_observations(sim, manifest):
    """Convert an externally supplied command-aligned replay to the shared estimator."""
    from .fitting import Observations
    from .contracts import validate_trial

    views, _, _ = ingest(manifest)
    doc = json.loads(manifest.read_text())
    experiment = doc["experiment"]
    family, seed = experiment["family"], experiment["seed"]
    validate_trial(family, seed, 0)
    if (
        experiment["baseline"] != sim.body.baseline
        or experiment["marker"] != sim.body.marker
    ):
        raise ValueError("body baseline or tracked marker mismatch")
    if (
        experiment.get("timebase") != "shared-control-clock"
        or experiment.get("units") != "model-native"
    ):
        raise ValueError("command alignment and units required")
    trajectory = sim.predict(family, seed, 0)
    cam, times, features = views[experiment["camera_id"]]
    if cam is None or not cam.world or not experiment.get("fixed_camera"):
        raise ValueError("fixed metric camera profile required")
    cmds = np.asarray(experiment["commands"], float)
    if (
        cmds.shape != trajectory.commands.shape
        or not np.allclose(cmds, trajectory.commands, atol=1e-8)
        or len(times) != len(trajectory.time)
        or not np.allclose(times, trajectory.time, rtol=0, atol=0.004)
    ):
        raise ValueError("recorded commands or clock do not match simulated proposal")
    return cam, Observations(family, seed, features)


def fit_recordings(sim, folder, training, heldout):
    from dataclasses import asdict
    from .experiment import immutable
    from .fitting import fit, validate

    folder.mkdir(parents=True, exist_ok=True)
    camera, train = aligned_observations(sim, training)

    def profile(c):
        return {
            k: v.tolist() if isinstance(v, np.ndarray) else v
            for k, v in asdict(c).items()
        }

    valid = []
    for path in heldout:
        c, data = aligned_observations(sim, path)
        if profile(c) != profile(camera):
            raise ValueError("replay calibration differs across trials")
        valid.append(data)
    candidate = fit(sim, camera, train)
    candidate["training_digest"] = hashlib.sha256(training.read_bytes()).hexdigest()
    cid = immutable(folder, candidate)
    report = validate(sim, camera, candidate, valid)
    report.update(
        candidate=cid,
        hardware_accepted=False,
        heldout_digests=[hashlib.sha256(p.read_bytes()).hexdigest() for p in heldout],
    )
    return dict(
        candidate=cid, qualification=immutable(folder, report), passed=report["passed"]
    )
