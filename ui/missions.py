"""Read-only projection of the canonical repository campaign register."""
import json
from pathlib import Path

REGISTER = Path(__file__).resolve().parents[1]/'release'/'mission-register.json'


def mission_status():
    if REGISTER.stat().st_size > 2*1024*1024:
        raise ValueError('mission register exceeds bound')
    register = json.loads(REGISTER.read_text())
    if (register.get('schema') != 'charlie.master-campaign.v1'
            or not isinstance(register.get('capabilities'), list)):
        raise ValueError('canonical mission register unavailable')
    return dict(register=register,
                freshness='Published checkpoint; inspect linked GitHub revisions for later changes',
                installed='UNKNOWN; source publication is not installation',
                physical_authorization=False)
