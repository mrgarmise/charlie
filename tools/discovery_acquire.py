"""Development-only acquisition of pinned reference source bytes. No runtime imports."""

import argparse
import hashlib
import os
from pathlib import Path
import tempfile
from urllib.request import HTTPRedirectHandler, build_opener

# Files approved for these particular revisions. Licensing evidence travels with
# the release. New entries require human review before this allowlist changes.
SOURCES = {
    "codata": (
        "https://raw.githubusercontent.com/scipy/scipy/v1.17.0/scipy/constants/_codata.py",
        "005317bcd5e11a7cf5c51420a0027399a5c6e39149f3a124e22382dc384cd102",
        202549, "BSD-3-Clause", "scipy-codata-source.txt",
    ),
    "timezones": (
        "https://raw.githubusercontent.com/eggert/tz/2026f/zone1970.tab",
        "5f23781702bf51408ff1581daa109ab3b9257fb433b1554e579d92172892c0cf",
        17592, "Public domain", "zone1970.tab",
    ),
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def acquire(key, destination, source=None):
    url, digest, length, license_name, filename = SOURCES[key]
    stream = (Path(source).open("rb") if source is not None
              else build_opener(NoRedirect()).open(url, timeout=15))
    with stream:
        data = stream.read(length + 1)
    if len(data) != length or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("unrecognized upstream bytes")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / filename
    with tempfile.NamedTemporaryFile(dir=destination) as stage:
        stage.write(data)
        stage.flush()
        os.fsync(stage.fileno())
        try:
            os.link(stage.name, target)  # concurrent requests cannot replace a release
        except FileExistsError:
            if target.is_symlink() or target.stat().st_size != length or target.read_bytes() != data:
                raise FileExistsError("destination has different bytes")
    return dict(source=url, file=str(target), bytes=length, sha256=digest, license=license_name)


if __name__ == "__main__":
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", choices=SOURCES)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--source", type=Path, help="verify a local copy instead of downloading")
    args = parser.parse_args()
    print(json.dumps(acquire(args.reference, args.destination, args.source), indent=2))
