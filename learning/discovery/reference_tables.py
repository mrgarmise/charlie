"""Line-addressable data from two licensed, pinned scientific reference tables."""
import hashlib
import json
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parents[2] / "docs/discovery/reference-data"
PINS = {
    "SCIPY-LICENSE.txt": "221e59f5e910fd7f94e44f0dac77436a11338c285c6346232e4a850a50da0e94",
    "codata-2022.txt": "4fcfc9f62b1faa18276583f8e33f6ef51ff325db80bc788ac4e7753ec87323fb",
    "manifest.json": "c279e7f8a2aedc0178273dec67f2fca04295cb92858fdaf5877f41a73e3b2bd0",
    "zone1970.tab": "5f23781702bf51408ff1581daa109ab3b9257fb433b1554e579d92172892c0cf",
}


def reference_rows(path=None):
    root = Path(path) if path else REFERENCE_DIR
    files = {}
    for name, digest in PINS.items():
        member = root / name
        if member.is_symlink() or member.stat().st_size > 256_000:
            raise ValueError(f"invalid reference member: {name}")
        data = member.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"reference hash mismatch: {name}")
        files[name] = data
    for source in json.loads(files["manifest.json"]):
        for number, line in enumerate(files[source["file"]].decode().splitlines(), start=1):
            if not line.strip() or line.startswith("#"):
                continue
            if source["id"] == "TZ1970":
                countries, position, zone, *_ = line.split("\t")
                text = f"{zone} principal location: {position} (ISO 6709), countries {countries}."
            else:
                text = " ".join(line.split())
            yield dict(id=f'{source["id"]}-L{number}', text=text, source=source["id"],
                       kind="reference_table", sha256=hashlib.sha256(text.encode()).hexdigest(),
                       locator=f'{source["file"]}#L{number}')
