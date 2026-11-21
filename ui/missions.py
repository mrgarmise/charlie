"""Read-only projection of the canonical repository campaign register."""
import json
import os
from pathlib import Path

REGISTER = Path(__file__).resolve().parents[1]/'release'/'mission-register.json'


def mission_status():
    if REGISTER.stat().st_size > 2*1024*1024:
        raise ValueError('mission register exceeds bound')
    register = json.loads(REGISTER.read_text())
    if (register.get('schema') != 'charlie.master-campaign.v1'
            or not isinstance(register.get('capabilities'), list)):
        raise ValueError('canonical mission register unavailable')
    result = dict(register=register,
                  freshness='Published checkpoint; inspect linked GitHub revisions for later changes',
                  installed='UNKNOWN; source publication is not installation',
                  physical_authorization=False)
    snapshot = os.environ.get("CHARLIE_DEV_FACTORY_VIEW")
    if snapshot:
        try:
            result["development_organization"] = read_development_organization(Path(snapshot))
        except (OSError, ValueError, TypeError):
            result["development_organization"] = {"state": "snapshot unavailable"}
    return result


def read_development_organization(path):
    """Read a CLI export selected by the development operator."""
    with path.open("rb") as source:
        raw = source.read(128 * 1024 + 1)
    if len(raw) > 128 * 1024:
        raise ValueError("development snapshot exceeds bound")
    view = json.loads(raw, parse_constant=lambda value: None)
    if (not isinstance(view, dict) or view.get("schema") != 1
            or not isinstance(view.get("nodes"), list) or len(view["nodes"]) > 12
            or not isinstance(view.get("tasks"), dict)):
        raise ValueError("development snapshot is invalid")
    result = {key: view.get(key) for key in ("goal", "state", "deadline", "seconds", "decision", "work_budget", "consumed_work_units")}
    result["assignments"] = []
    for node in view["nodes"]:
        if not isinstance(node, dict) or not isinstance(node.get("name"), str):
            raise ValueError("development assignment is invalid")
        task = view["tasks"].get(node["name"])
        if not isinstance(task, dict):
            raise ValueError("development task is invalid")
        result["assignments"].append({**node, **task})
    return result
