from dataclasses import asdict
import hashlib

import pytest

from .core import encode
from .manifest import load_manifest
from .synthetic import LinearTwin


def checked(payload):
    return load_manifest(payload, approved_digest=hashlib.sha256(payload).hexdigest())


def test_profile_round_trip_and_pin():
    profile = LinearTwin().profile
    payload = encode(asdict(profile)).encode()
    assert checked(payload) == profile
    with pytest.raises(PermissionError):
        load_manifest(payload, approved_digest="0" * 64)


@pytest.mark.parametrize("changes", [
    {"transport": "physical"}, {"version": True}, {"sensors": []},
    {"actuators": [{"name": "axis", "unit": [], "low": 0, "high": 1}]},
    {"command": "invented executable payload"}, {"max_duration": "0.25"},
])
def test_rejected_manifests(changes):
    profile = asdict(LinearTwin().profile)
    with pytest.raises((PermissionError, ValueError)):
        checked(encode(profile | changes).encode())


def test_invalid_json_and_duplicate_keys():
    for payload in (b"{", b'{"a":1,"a":2}'):
        with pytest.raises(ValueError):
            checked(payload)
