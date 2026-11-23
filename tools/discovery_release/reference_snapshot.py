"""Reproduce the two redistributable reference tables from pinned local wheels."""
import ast
import base64
import hashlib
import importlib.metadata
import json
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[2] / "docs/discovery/reference-data"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verified_member(package, version, member):
    distribution = importlib.metadata.distribution(package)
    if distribution.version != version:
        raise ValueError(f"requires {package}=={version}")
    entry = next(f for f in distribution.files if str(f) == member)
    data = distribution.locate_file(entry).read_bytes()
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
    if entry.hash.mode != "sha256" or digest != entry.hash.value:
        raise ValueError(f"wheel RECORD mismatch: {member}")
    return data


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scipy_member = "scipy/constants/_codata.py"
    module = verified_member("scipy", "1.17.0", scipy_member)
    tree = ast.parse(module.decode())
    literal = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "txt2022" for t in n.targets))
    constants = ast.literal_eval(literal).encode()
    scipy_license = verified_member("scipy", "1.17.0", "scipy-1.17.0.dist-info/LICENSE.txt")
    (OUTPUT / "SCIPY-LICENSE.txt").write_bytes(scipy_license.split(b"\n----\n", 1)[0])
    coordinates = verified_member("tzdata", "2026.6", "tzdata/zoneinfo/zone1970.tab")
    if b"This file is in the public domain" not in coordinates:
        raise ValueError("missing redistribution declaration")
    rows = [
        ("codata-2022.txt", constants, dict(
            id="CODATA22", title="2022 CODATA recommended values, SciPy transcription",
            institution="CODATA via SciPy", version="SciPy 1.17.0, txt2022",
            url="https://github.com/scipy/scipy/blob/v1.17.0/scipy/constants/_codata.py",
            upstream_url="https://physics.nist.gov/cuu/Constants/", license="BSD-3-Clause",
            notice="SCIPY-LICENSE.txt", original_member=scipy_member, original_sha256=sha(module),
            original_bytes=len(module), limitation="Fixed-width decimal strings include truncated exact values, units and uncertainty. Preserve notation.")),
        ("zone1970.tab", coordinates, dict(
            id="TZ1970", title="Time zone principal locations", institution="IANA tzdb via tzdata",
            version="tzdata 2026.6", url="https://pypi.org/project/tzdata/2026.6/",
            upstream_url="https://www.iana.org/time-zones", license="Public domain",
            notice="zone1970.tab header", original_member="tzdata/zoneinfo/zone1970.tab",
            original_sha256=sha(coordinates), original_bytes=len(coordinates),
            limitation="Representative locations for civil timekeeping since 1970. The coordinates describe individual points.")),
    ]
    manifest = []
    for filename, data, metadata in rows:
        (OUTPUT / filename).write_bytes(data)
        manifest.append(dict(metadata, file=filename, sha256=sha(data), bytes=len(data),
                             acquired_utc="2026-11-23", acquisition="installed wheel, verified against RECORD",
                             reader="UTF-8 text", offline_present=True))
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
