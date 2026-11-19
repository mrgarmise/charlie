import pytest
from .contracts import SimulationPermit, physical_command


def test_no_motion_authority():
    for token in (None, SimulationPermit(), {"scope": "physical", "expires": -1}):
        with pytest.raises(PermissionError):
            physical_command(token, "move")


import json
from dataclasses import replace
import cv2
import numpy as np

from .camera import fixture, triangulate, sync, pair_frames, calibrate
from .contracts import BodyDescription
from .experiment import run
from .fitting import fit, Observations, validate
from .perception import CPU, Aruco, Hailo, Silhouette, render, stabilize
from .qualification import read_object
from .replay import CameraSource, decode
from .rig import Rig


def test_invalid_units_and_optimizer_inputs():
    with pytest.raises(ValueError):
        BodyDescription("rig", ("pan",), "p", "base", "inches")
    for family, delay in [("pulse", 10000), ("__import__('os')", 0), ("still", True)]:
        with pytest.raises(ValueError):
            Rig().predict(family, 1, delay)
    with pytest.raises(PermissionError):
        SimulationPermit("motors")


def test_stereo():
    a = fixture("rig")
    b = fixture("rig", "elegoo", 0.06)
    xyz = np.array([0.03, 0.10, 0.09])
    uv = {c.camera_id: c.project(xyz)[0] for c in (a, b)}
    clock = sync([0, 1, 2], [0.2, 1.2, 2.2])
    assert pair_frames([0, 0.02, 0.04], [0.2, 0.24], clock)[-1][:2] == (2, 1)
    assert np.allclose(triangulate((a, b), uv, (1, 1.2), clock), xyz)
    for cams, features, t in [
        ((a, b), uv, (1, 2)),
        ((a, b), dict(reversed(list(uv.items()))), (0, 0.9)),
        ((a, b), {"primary": uv["elegoo"], "elegoo": uv["primary"]}, (1, 1.2)),
        ((a, replace(b, world="unknown")), uv, (1, 1.2)),
        ((a, a), uv, (1, 1.2)),
        ((a, b), {"primary": uv["primary"]}, (1, 1.2)),
    ]:
        with pytest.raises(ValueError):
            triangulate(cams, features, t, clock)
    for kwargs in (dict(R=np.eye(3) * 2), dict(rms=4), dict(K=np.zeros((3, 3)))):
        with pytest.raises(ValueError):
            replace(a, **kwargs)
    with pytest.raises(ValueError):
        sync([0, 1, 2], [0, 1.06, 2])
    assert list(CameraSource("elegoo", "elegoo_optional").frames()) == []


def test_perception():
    frame = render(np.array([88.0, 122.0]), np.random.default_rng(4))
    f = CPU().detect(frame)
    assert np.linalg.norm(np.array(f.uv) - [88, 122]) < 1
    blank = np.full_like(frame, 22)
    assert CPU().detect(blank) is None
    assert Silhouette(blank).detect(frame).sigma_px > f.sigma_px
    assert Hailo(CPU().detect).detect(frame) == f
    with pytest.raises(RuntimeError):
        Hailo().detect(frame)
    with pytest.raises(ValueError):
        Hailo(lambda _: 1).detect(frame)
    shifted = np.array([[4, 8], [54, 8], [4, 88]])
    stabilized = stabilize(f, shifted, shifted - [4, 8])
    assert np.allclose(stabilized.uv, np.array(f.uv) - [4, 8])
    assert stabilize(f, shifted * 2, shifted) is None
    marker = cv2.aruco.generateImageMarker(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), 7, 80
    )
    assert Aruco(7).detect(
        cv2.copyMakeBorder(marker, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
    )
    with pytest.raises(ValueError):
        decode({"png": "QUJD", "sha256": "000"})


def board_images():
    K = np.array([[600.0, 0, 320], [0, 600, 240], [0, 0, 1]])
    square = 0.024
    board = np.zeros((6 * 60, 8 * 60), np.uint8)
    for j in range(6):
        for i in range(8):
            board[j * 60 : (j + 1) * 60, i * 60 : (i + 1) * 60] = 255 * ((i + j) % 2)
    src = np.float32([[0, 0], [480, 0], [480, 360], [0, 360]])
    corners = np.float32(
        [[0, 0, 0], [8 * square, 0, 0], [8 * square, 6 * square, 0], [0, 6 * square, 0]]
    )
    rng = np.random.default_rng(25)
    for i in range(12):
        r = rng.uniform(-0.4, 0.4, 3)
        t = np.array(
            [
                -0.10 + rng.uniform(-0.02, 0.02),
                -0.07 + rng.uniform(-0.02, 0.02),
                rng.uniform(0.38, 0.60),
            ]
        )
        dst = cv2.projectPoints(corners, r, t, K, None)[0].reshape(4, 2)
        yield cv2.warpPerspective(
            board, cv2.getPerspectiveTransform(src, dst), (640, 480), borderValue=127
        )


def test_board_calibration():
    imgs = list(board_images())
    c = calibrate(imgs, (7, 5), 0.024, imgs[0], "primary", "board")
    assert c.rms < 0.5 and abs(c.K[0, 0] - 600) < 16
    with pytest.raises(ValueError):
        calibrate(imgs[:1], (7, 5), 0.024, imgs[0], "primary", "board")


def test_cycle_resume_and_holdout(tmp_path):
    rig = Rig()
    with pytest.raises(TimeoutError):
        run(rig, tmp_path, seconds=0)
    report = run(rig, tmp_path)
    assert run(rig, tmp_path) == report
    assert report["delay"] == 3 and report["passed"] and len(report["ambiguous"]) == 5
    obj = read_object(tmp_path, report["candidate"])
    with pytest.raises(ValueError):
        validate(rig, fixture("rig"), obj, [Observations("pulse", 88, [])])
    with pytest.raises(ValueError):
        fit(rig, fixture("rig"), Observations("still", 1, [None] * 64))
    with pytest.raises(ValueError):
        read_object(tmp_path, "../bad")
    (tmp_path / (report["candidate"] + ".json")).write_text("{}")
    with pytest.raises(ValueError):
        read_object(tmp_path, report["candidate"])


def test_ingest_uncalibrated_optional(tmp_path):
    import hashlib
    from .recording import ingest

    im = render(np.array([123, 77]), np.random.default_rng(5))
    raw = cv2.imencode(".png", im)[1].tobytes()
    (tmp_path / "sample.png").write_bytes(raw)
    row = dict(time_s=0.02, path="sample.png", sha256=hashlib.sha256(raw).hexdigest())
    streams = [
        dict(source=dict(camera_id="primary", backend="synthetic"), frames=[row]),
        dict(
            source=dict(camera_id="elegoo", backend="elegoo_optional"),
            aruco_id=2,
            frames=[],
        ),
    ]
    manifest = tmp_path / "recording.json"
    manifest.write_text(json.dumps(dict(version=1, sources=streams)))
    views, points, status = ingest(manifest)
    assert views["primary"][2][0] and not points and status == "independent 2D"
    (tmp_path / "sample.png").write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        ingest(manifest)


def test_recorded_train_holdout(tmp_path):
    import hashlib
    from dataclasses import asdict
    from .recording import fit_recordings

    rig = Rig()
    cam = fixture("rig")

    def recording(family, seed):
        tr = rig.predict(family, seed, 2)
        root = tmp_path / family
        root.mkdir()
        rows = []
        rng = np.random.default_rng(seed)
        for i, (uv, t) in enumerate(zip(cam.project(tr.xyz), tr.time)):
            raw = cv2.imencode(".png", render(uv, rng))[1].tobytes()
            path = root / f"{i}.png"
            path.write_bytes(raw)
            rows.append(
                dict(time_s=t, path=path.name, sha256=hashlib.sha256(raw).hexdigest())
            )
        source = dict(
            camera_id=cam.camera_id, backend="synthetic", calibration_id="fixture"
        )
        profile = {
            k: v.tolist() if isinstance(v, np.ndarray) else v
            for k, v in asdict(cam).items()
        }
        exp = dict(
            camera_id=cam.camera_id,
            baseline=rig.body.baseline,
            marker=rig.body.marker,
            family=family,
            seed=seed,
            commands=tr.commands.tolist(),
            units="model-native",
            fixed_camera=True,
            timebase="shared-control-clock",
        )
        path = root / "recording.json"
        path.write_text(
            json.dumps(
                dict(
                    version=1,
                    experiment=exp,
                    sources=[dict(source=source, frames=rows, calibration=profile)],
                )
            )
        )
        return path

    train = recording("pulse", 7)
    held = recording("reverse", 8)
    result = fit_recordings(rig, tmp_path / "lineage", train, [held])
    assert result["passed"]
    doc = json.loads(held.read_text())
    doc["experiment"]["commands"][10][0] += 1
    held.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        fit_recordings(rig, tmp_path / "lineage", train, [held])


def test_cli_review(tmp_path, capsys):
    from .__main__ import main
    from .planning import propose
    from unittest.mock import patch

    def invoke(*args):
        with patch("sys.argv", ["visual", *map(str, args)]):
            main()
        return json.loads(capsys.readouterr().out)

    result = invoke("demo", tmp_path)
    qualification = result["qualification"]
    assert invoke("inspect", tmp_path)
    assert invoke("compare", tmp_path, qualification)
    assert "review" in open(invoke("review", tmp_path, qualification)).read().lower()
    assert not invoke(
        "propose", tmp_path, qualification, "--hypothesis", "run shell commands"
    )["hardware_accepted"]
    with pytest.raises(ValueError):
        propose({"commands": ["move"]})


def test_stereo_world_and_uncertainty():
    from .camera import verify_world, stereo_covariance

    cams = (fixture("rig"), fixture("rig", "elegoo", 0.09))
    points = [
        np.array(x) for x in ((0, 0.12, 0.06), (0.03, 0.12, 0.06), (0.03, 0.12, 0.09))
    ]
    refs = [
        dict(
            world_m=x.tolist(),
            pixels={c.camera_id: c.project(x)[0].tolist() for c in cams},
        )
        for x in points
    ]
    verify_world(cams, refs)
    cov = stereo_covariance(cams, refs[0]["pixels"], (1, 1), (1, 0), (0.4, 0.4))
    assert np.linalg.eigvalsh(cov).min() > 0
    refs[1]["world_m"][0] = 0.1
    with pytest.raises(ValueError):
        verify_world(cams, refs)


def test_core_has_no_device_transport():
    import ast
    from pathlib import Path

    root = Path(__file__).parent
    forbidden = {
        "hardware",
        "serial",
        "socket",
        "picamera2",
        "hailo_platform",
        "requests",
        "subprocess",
        "motion",
        "RPi",
        "smbus",
        "smbus2",
    }
    for path in root.glob("*.py"):
        if path.name.startswith("test_"):
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [n.name for n in node.names]
                if isinstance(node, ast.Import)
                else ([node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            )
            assert not forbidden.intersection(n.split(".")[0] for n in names), path


def test_dual_recorded_session_end_to_end(tmp_path):
    import hashlib
    from dataclasses import asdict
    from .recording import ingest

    cams = (fixture("rig"), fixture("rig", "elegoo", 0.09))
    refs = [
        np.array(p) for p in ((0.0, 0.12, 0.06), (0.03, 0.12, 0.06), (0.03, 0.12, 0.09))
    ]
    streams = []
    for cam, t in zip(cams, [1.0, 1.2]):
        uv = cam.project(refs[0])[0]
        raw = cv2.imencode(".png", render(uv, np.random.default_rng(1)))[1].tobytes()
        path = tmp_path / (cam.camera_id + ".png")
        path.write_bytes(raw)
        streams.append(
            dict(
                source=dict(
                    camera_id=cam.camera_id,
                    backend="synthetic",
                    calibration_id="survey",
                ),
                calibration={
                    k: v.tolist() if isinstance(v, np.ndarray) else v
                    for k, v in asdict(cam).items()
                },
                frames=[
                    dict(
                        time_s=t, path=path.name, sha256=hashlib.sha256(raw).hexdigest()
                    )
                ],
            )
        )
    doc = dict(
        version=1,
        sources=streams,
        sync_events=[[0, 1, 2], [0.2, 1.2, 2.2]],
        world_references=[
            dict(
                world_m=p.tolist(),
                pixels={c.camera_id: c.project(p)[0].tolist() for c in cams},
            )
            for p in refs
        ],
    )
    manifest = tmp_path / "stereo.json"
    manifest.write_text(json.dumps(doc))
    views, points, status = ingest(manifest)
    assert (
        status == "metric stereo"
        and np.linalg.norm(np.subtract(points[0]["xyz_m"], refs[0])) < 0.004
    )
    del doc["world_references"]
    manifest.write_text(json.dumps(doc))
    assert ingest(manifest)[2] == "independent 2D"
