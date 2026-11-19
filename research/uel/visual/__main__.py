"""Offline visual inquiry. All camera inputs are local files."""

import argparse
from dataclasses import asdict
import json
import sqlite3
from pathlib import Path
import cv2
import numpy as np

from .camera import calibrate
from .experiment import run
from .qualification import practice, read_object
from .rig import Rig


def body(name):
    if name == "dog":
        from visual_dog import VisualDog

        return VisualDog()
    return Rig()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    for name in (
        "demo",
        "inspect",
        "compare",
        "practice",
        "calibrate",
        "propose",
        "overlay",
        "recording",
        "review",
        "replay-skill",
        "fit-recordings",
    ):
        p = sub.add_parser(name)
        p.add_argument("folder", type=Path)
        if name == "fit-recordings":
            p.add_argument("training", type=Path)
            p.add_argument("heldout", type=Path, nargs="+")
        if name in ("demo", "fit-recordings"):
            p.add_argument("--body", choices=["dog", "rig"], default="rig")
        if name in ("practice", "compare", "propose", "review", "replay-skill"):
            p.add_argument("qualification")
        if name == "replay-skill":
            p.add_argument(
                "mode",
                choices=[
                    "stand",
                    "squat",
                    "step",
                    "walk",
                    "old-gait",
                    "unstable-start",
                    "leg-excursion",
                    "tripod",
                    "recovery",
                ],
            )
            p.add_argument("--index", type=int, default=0, choices=range(12))
        if name == "propose":
            p.add_argument("--hypothesis")
        if name == "calibrate":
            p.add_argument("--camera", required=True)
            p.add_argument("--square-m", type=float, required=True)
            p.add_argument("--pattern", nargs=2, type=int, required=True)
            p.add_argument("--world-id", required=True)
            p.add_argument("--world-image", required=True)
            p.add_argument("images", nargs="+")
    args = ap.parse_args()
    folder = args.folder
    if args.command == "demo":
        result = run(body(args.body), folder)
    elif args.command == "calibrate":

        def image(p):
            im = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
            if im is None:
                raise ValueError("unreadable board image")
            return im

        profile = calibrate(
            [image(p) for p in args.images],
            tuple(args.pattern),
            args.square_m,
            image(args.world_image),
            args.camera,
            args.world_id,
        )
        from .experiment import immutable

        folder.mkdir(exist_ok=True, parents=True)
        result = immutable(
            folder,
            {
                k: v.tolist() if isinstance(v, np.ndarray) else v
                for k, v in asdict(profile).items()
            },
        )
    elif args.command == "fit-recordings":
        from .recording import fit_recordings

        result = fit_recordings(body(args.body), folder, args.training, args.heldout)
    elif args.command == "recording":
        from .recording import ingest

        views, points, status = ingest(folder)
        result = {
            "status": status,
            "points": points,
            "cameras": {key: len(entry[1]) for key, entry in views.items()},
        }
    elif args.command == "inspect":
        with sqlite3.connect(
            (folder / "session.sqlite").resolve().as_uri() + "?mode=ro", uri=True
        ) as db:
            result = db.execute(
                "select session,phase,count(*) from events group by session,phase"
            ).fetchall()
    elif args.command == "practice":
        identifier, skills = practice(body("dog"), folder, args.qualification)
        result = {
            "id": identifier,
            "accepted_in_simulation": [
                k for k, v in skills.items() if v["simulation_accepted"]
            ],
        }
    elif args.command == "review":
        from .review import render_review

        page = folder / (args.qualification + ".html")
        page.write_text(render_review(folder, args.qualification))
        result = str(page)
    elif args.command == "replay-skill":
        skills = read_object(folder, args.qualification)
        row = skills[args.mode]["rollouts"][args.index]
        result = body("dog").practice(row["delay"], args.mode, row["seed"])
        if result != row:
            raise ValueError("skill replay diverged from evidence")
    elif args.command == "overlay":
        path = folder / "overlay.png"
        if not path.is_file():
            raise ValueError("run demo to generate the overlay")
        result = str(path)
    else:
        report = read_object(folder, args.qualification)
        if args.command == "compare":
            result = [
                {k: v for k, v in r.items() if k != "residual_px"}
                for r in report["withheld"]
            ]
        else:
            from .planning import propose

            result = propose(args.hypothesis)
            result["qualification"] = args.qualification
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
