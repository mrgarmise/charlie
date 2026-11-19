"""Offline camera calibration, pinhole projection and gated stereo."""

from dataclasses import dataclass
import cv2
import numpy as np


@dataclass
class Camera:
    camera_id: str
    K: np.ndarray
    R: np.ndarray
    t: np.ndarray
    distortion: np.ndarray
    world: str
    rms: float

    def __post_init__(self):
        self.K, self.R, self.t, self.distortion = map(
            lambda x: np.asarray(x, dtype=float),
            (self.K, self.R, self.t, self.distortion),
        )
        if (
            self.K.shape != (3, 3)
            or self.R.shape != (3, 3)
            or self.t.shape != (3,)
            or self.distortion.size not in (4, 5, 8, 12, 14)
            or not all(
                np.isfinite(a).all() for a in (self.K, self.R, self.t, self.distortion)
            )
            or min(self.K[0, 0], self.K[1, 1]) <= 0
            or not np.allclose(self.K[2], [0, 0, 1])
            or not np.allclose(self.R.T @ self.R, np.eye(3), atol=1e-5)
            or not np.isclose(np.linalg.det(self.R), 1)
            or not 0 <= self.rms <= 1
        ):
            raise ValueError("invalid calibration or excessive reprojection error")

    def project(self, xyz):
        xyz = np.asarray(xyz, dtype=float).reshape(-1, 3)
        if not np.all(np.isfinite(xyz)) or np.any((xyz @ self.R.T + self.t)[:, 2] <= 0):
            raise ValueError("invalid point or negative depth")
        return cv2.projectPoints(
            xyz, cv2.Rodrigues(self.R)[0], self.t, self.K, self.distortion
        )[0][:, 0]


def fixture(body, camera_id="primary", baseline=0.0):
    # Camera looks along +Y with vertical up mapped to negative image Y.
    R = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0.0]])
    focal = 3500 if body == "fnk0050" else 700
    origin_x = 0.026 if body == "fnk0050" else 0
    K = np.array([[focal, 0, 160], [0, focal, 120], [0, 0, 1.0]])
    return Camera(
        camera_id,
        K,
        R,
        np.array([-origin_x - baseline, 0.06, 0.5]),
        np.zeros(5),
        "fixture-m",
        0.0,
    )


def calibrate(images, pattern, square_m, world_image, camera_id, world):
    if (
        not np.isfinite(square_m)
        or not 0 < square_m <= 1
        or min(pattern) < 3
        or not world
    ):
        raise ValueError("measured square size and world frame required")
    grid = np.zeros((np.prod(pattern), 3), np.float32)
    grid[:, :2] = np.mgrid[: pattern[0], : pattern[1]].T.reshape(-1, 2) * square_m
    found = []
    size = world_image.shape[:2][::-1]
    for image in images:
        if image.shape[:2][::-1] != size:
            raise ValueError("image sizes differ")
        ok, pts = cv2.findChessboardCornersSB(image, pattern)
        if ok:
            found.append(pts)
    if len(found) < 6:
        raise ValueError("six distinct tilted board views required")
    diversity = np.stack([p.reshape(-1, 2)[[0, pattern[0] - 1, -1]] for p in found])
    if np.max(np.std(diversity, axis=0)) < 5:
        raise ValueError("board poses lack diversity")
    rms, K, d, _, _ = cv2.calibrateCamera([grid] * len(found), found, size, None, None)
    ok, pts = cv2.findChessboardCornersSB(world_image, pattern)
    if not ok:
        raise ValueError("fixed world reference missing")
    ok, r, t = cv2.solvePnP(grid, pts, K, d)
    if not ok:
        raise ValueError("world pose unsolved")
    cam = Camera(camera_id, K, cv2.Rodrigues(r)[0], t.ravel(), d, world, rms)
    if np.sqrt(np.mean((cam.project(grid) - pts.reshape(-1, 2)) ** 2)) > 1:
        raise ValueError("world reference residual too high")
    return cam


def sync(a, b):
    """Corresponding flash events in each clock, in seconds. Return B-to-A affine map."""
    a, b = np.asarray(a), np.asarray(b)
    if (
        a.shape != b.shape
        or len(a) < 3
        or any(not np.all(np.diff(x) > 0) for x in (a, b))
    ):
        raise ValueError("need three ordered shared clock events")
    rate, offset = np.polyfit(b, a, 1)
    if abs(rate - 1) > 0.002 or max(abs(rate * b + offset - a)) > 0.005:
        raise ValueError("clock instability")
    return rate, offset


def triangulate(cameras, features, times, clock):
    a, b = cameras
    if (
        a.camera_id == b.camera_id
        or not a.world
        or a.world != b.world
        or set(features) != {a.camera_id, b.camera_id}
        or not np.isfinite(clock).all()
        or abs(clock[0] - 1) > 0.002
        or not np.isfinite(times).all()
        or abs(times[0] - (clock[0] * times[1] + clock[1])) > 0.01
    ):
        raise ValueError("unsynchronized or unregistered cameras")
    rays = []
    for cam in cameras:
        uv = np.asarray(features[cam.camera_id], float).reshape(1, 1, 2)
        ray = cv2.undistortPoints(uv, cam.K, cam.distortion).ravel()
        rays.append(ray)
    directions = [cam.R.T @ np.r_[ray, 1.0] for cam, ray in zip(cameras, rays)]
    if (
        np.linalg.norm(np.cross(*directions))
        / np.prod([np.linalg.norm(v) for v in directions])
        < 0.03
    ):
        raise ValueError("insufficient parallax")
    h = cv2.triangulatePoints(
        *[np.column_stack((c.R, c.t)) for c in cameras],
        *[r.reshape(2, 1) for r in rays]
    ).ravel()
    xyz = h[:3] / h[3]
    if any(
        np.linalg.norm(cam.project(xyz)[0] - features[cam.camera_id]) > 1
        for cam in cameras
    ):
        raise ValueError("inconsistent stereo observations")
    return xyz


def pair_frames(primary, secondary, clock):
    """One-to-one nearest exposures; unpaired views remain independent 2D evidence."""
    rate, offset = clock
    a = np.asarray(primary, float)
    b = rate * np.asarray(secondary, float) + offset
    if any(not np.isfinite(x).all() or np.any(np.diff(x) <= 0) for x in (a, b)):
        raise ValueError("nonmonotonic stream")
    pairs = []
    j = 0
    for i, t in enumerate(a):
        while j + 1 < len(b) and abs(t - b[j + 1]) < abs(t - b[j]):
            j += 1
        if j < len(b) and abs(t - b[j]) <= 0.01:
            pairs.append((i, j, float(t - b[j])))
            j += 1
    return pairs


def verify_world(cameras, references):
    """Reject a false scale/orientation using independent metric reference points."""
    xyz = np.asarray([p["world_m"] for p in references], float)
    if len(xyz) < 3 or np.linalg.matrix_rank(xyz - xyz.mean(axis=0)) < 2:
        raise ValueError("need three noncollinear measured world points")
    for cam in cameras:
        observed = np.asarray([p["pixels"][cam.camera_id] for p in references], float)
        predicted = cam.project(xyz)
        if (
            observed.shape != predicted.shape
            or not np.isfinite(observed).all()
            or np.max(np.linalg.norm(predicted - observed, axis=1)) > 1.5
        ):
            raise ValueError("world scale or camera correspondence inconsistent")


def stereo_covariance(cameras, coords, times, clock, sigmas):
    """First-order uncertainty conditional on the calibrated extrinsics."""
    cols = []
    for cam, sigma in zip(cameras, sigmas, strict=True):
        if not np.isfinite(sigma) or sigma <= 0:
            raise ValueError("invalid image uncertainty")
        for axis in np.eye(2):
            plus = dict(coords)
            minus = dict(coords)
            plus[cam.camera_id] = np.asarray(coords[cam.camera_id]) + 0.01 * axis
            minus[cam.camera_id] = np.asarray(coords[cam.camera_id]) - 0.01 * axis
            cols.append(
                sigma
                * (
                    triangulate(cameras, plus, times, clock)
                    - triangulate(cameras, minus, times, clock)
                )
                / 0.02
            )
    jac = np.column_stack(cols)
    cov = jac @ jac.T
    if np.linalg.eigvalsh(cov).max() > 0.02**2:
        raise ValueError("stereo depth uncertainty exceeds 20 mm")
    return cov
