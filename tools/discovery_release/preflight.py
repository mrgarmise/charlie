"""Read-only inventory for a later operator. Does not admit a slot or start a service."""
import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path


def command(args):
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, timeout=10, check=True, env=env)
    return result.stdout.strip()


def file_digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(repo, ops, disk, expected_commit, expected_tree):
    for value in (expected_commit, expected_tree):
        if not re.fullmatch("[0-9a-f]{40}", value):
            raise ValueError("supply full release commit and tree")
    git = ["git", "-C", str(repo)]
    blockers = []
    commit = command(git + ["rev-parse", "HEAD"])
    tree = command(git + ["rev-parse", "HEAD^{tree}"])
    if (commit, tree) != (expected_commit, expected_tree):
        blockers.append("candidate identity differs from release")
    if command(git + ["status", "--porcelain", "--untracked-files=normal"]):
        blockers.append("candidate worktree differs from recorded tree")
    if platform.machine() != "aarch64":
        blockers.append("native aarch64 comparison unavailable")
    controls = {}
    for name in ("QUALIFICATION.md", "approved.sha", "start-stationary.sh", "run-historical-consultation.py"):
        path = ops / name
        if path.is_file():
            controls[name] = file_digest(path)
        else:
            blockers.append(f"missing operational evidence: {name}")
    pin = ops / "approved.sha"
    active_pin = pin.read_text().strip() if pin.is_file() and pin.stat().st_size < 256 else None
    if not active_pin or not re.fullmatch("[a-f0-9]{40}", active_pin):
        blockers.append("current approved revision unavailable")
    disk_free = shutil.disk_usage(disk).free
    policy = Path("/etc/charlie-meditation/policy.json")
    files = {}
    for name in ("/sys/fs/cgroup/cgroup.controllers", "/sys/class/thermal/thermal_zone0/temp"):
        path = Path(name)
        files[name] = path.read_text().strip() if path.is_file() else None
    resources = {line.split(":")[0]: line.split(":")[1].strip()
                 for line in Path("/proc/meminfo").read_text().splitlines()
                 if line.split(":")[0] in ("MemAvailable", "SwapTotal", "SwapFree")}
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE VIRTUAL TABLE verify USING fts5(content)")
    return dict(schema=1, at=dt.datetime.now(dt.timezone.utc).isoformat(), candidate=commit,
                tree=tree, approved_pin=active_pin, control_hashes=controls,
                python=platform.python_version(), sqlite=sqlite3.sqlite_version, fts5=True,
                platform=platform.machine(), free_bytes=disk_free, memory=resources, kernel=files,
                native_policy_sha256=file_digest(policy) if policy.is_file() else None,
                comparison_blockers=blockers, admission_issued=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "ops", "disk"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-tree", required=True)
    result = inventory(**vars(parser.parse_args()))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["comparison_blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
