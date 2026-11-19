"""Atomic frames and content digests in the existing UEL journal. No device readers."""

import base64
from dataclasses import asdict, dataclass
import hashlib

import cv2
import numpy as np
from .perception import CPU, render


@dataclass(frozen=True)
class CameraSource:
    camera_id: str
    backend: str
    calibration_id: str | None = None

    def frames(self, journal=None):
        if self.backend not in {"synthetic", "recording", "imx708", "elegoo_optional"}:
            raise ValueError("unrecognized camera backend")
        if journal is None:
            return
        for _, phase, row in journal.read():
            if phase == "frame" and row["camera_id"] == self.camera_id:
                if row["calibration_id"] != self.calibration_id:
                    raise ValueError("camera calibration mismatch")
                yield row, decode(row) if row["png"] else None


def decode(row):
    raw = base64.b64decode(row["png"], validate=True)
    if hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise ValueError("corrupt recording")
    frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("invalid image")
    return frame


def capture(journal, camera, trajectory, family, seed, start, skip=0):
    rng = np.random.default_rng(seed)
    pixels = camera.project(trajectory.xyz)
    source = CameraSource(
        camera.camera_id, "synthetic", camera.world + "-" + camera.camera_id
    )
    found = []
    for i, (uv, t, command) in enumerate(
        zip(pixels, trajectory.time, trajectory.commands, strict=True)
    ):
        visible = i % 17 != 7
        dropped = i % 31 == 12
        limbs = (
            None
            if trajectory.limbs is None
            else camera.project(trajectory.limbs[i]).reshape(4, 4, 2)
        )
        frame = render(uv, rng, visible, limbs)
        if i < skip:
            continue
        feature = None if dropped else CPU().detect(frame)
        raw = cv2.imencode(".png", frame)[1].tobytes() if i % 16 == 0 else b""
        journal.append(
            start + i,
            "frame",
            dict(
                version=1,
                family=family,
                seed=seed,
                index=i,
                camera_id=source.camera_id,
                calibration_id=source.calibration_id,
                marker_truth_xyz_m=trajectory.xyz[i].tolist(),
                marker_truth_uv=uv.tolist(),
                deliberately_occluded=not visible,
                source="synthetic",
                clock="simulated",
                monotonic_s=float(t),
                wall_time=None,
                battery_v=None,
                command=command.tolist(),
                dropped=dropped,
                feature=asdict(feature) if feature else None,
                imu=None if trajectory.imu is None else trajectory.imu[i].tolist(),
                png=base64.b64encode(raw).decode(),
                sha256=hashlib.sha256(raw).hexdigest(),
                privacy="local synthetic only",
            ),
        )
        found.append(feature)
    return found
