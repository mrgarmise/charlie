"""Strict JSON profile loading against a locally pinned simulation manifest."""

from dataclasses import fields
import hashlib
import hmac
import json

from .core import Channel, Profile


def unique_object(entries):
    result = {}
    for key, value in entries:
        if key in result:
            raise ValueError(f"duplicate manifest key: {key}")
        result[key] = value
    return result


def load_manifest(payload: bytes, *, approved_digest: str) -> Profile:
    """Use a digest from operator configuration, never from the proposal."""
    if not isinstance(payload, bytes) or not 0 < len(payload) <= 64 * 1024:
        raise ValueError("invalid manifest size")
    if not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), approved_digest):
        raise PermissionError("simulation manifest not approved")
    try:
        raw = json.loads(payload, object_pairs_hook=unique_object)
    except (UnicodeError, RecursionError) as err:
        raise ValueError("invalid manifest encoding") from err
    if not isinstance(raw, dict) or set(raw) != {field.name for field in fields(Profile)}:
        raise ValueError("unknown or missing profile fields")
    if raw["transport"] != "simulation":
        raise PermissionError("DENIED_PHYSICAL_AUTHORITY")
    if type(raw["version"]) is not int:
        raise ValueError("invalid profile version")
    for key in ("name", "revision", "source"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise ValueError(f"invalid profile {key}")
    for key in ("max_duration", "stale_after"):
        if type(raw[key]) not in (int, float):
            raise ValueError(f"invalid profile {key}")
    for group in ("actuators", "sensors"):
        entries = raw[group]
        if not isinstance(entries, list) or not 0 < len(entries) <= 128:
            raise ValueError("invalid channel inventory")
        channels = []
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"name", "unit", "low", "high"}:
                raise ValueError("invalid channel fields")
            if any(not isinstance(entry[key], str) or not entry[key].strip() for key in ("name", "unit")):
                raise ValueError("invalid channel labels")
            if any(type(entry[key]) not in (int, float) for key in ("low", "high")):
                raise ValueError("invalid channel limits")
            channels.append(Channel(**entry))
        raw[group] = tuple(channels)
    if not isinstance(raw["neutral"], list):
        raise ValueError("invalid neutral command")
    raw["neutral"] = tuple(raw["neutral"])
    return Profile(**raw)
