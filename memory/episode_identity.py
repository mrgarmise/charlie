"""Capture identity primitives shared by the existing diary and acquisition.

Occurrence is a durable origin declaration, manifest is exact package content,
content is correlated experience, and qualification requires external evidence.
None of these alone certifies physical gameplay or score.
"""
import json
import os
from pathlib import Path
import secrets
from datetime import datetime, timezone
import hashlib
import re
from .evidence import digest, canonical

ORIGIN = 'capture-origin.json'
MANIFEST = 'capture-manifest.json'
SCHEMA = 'charlie-capture-v1'
# Acquisition overlays are separate evidence, never captured source artifacts.
OVERLAYS = {'external-observations.json', 'episode-qualification.json'}
CORE = {'report.json', 'tracks.json', 'agency.jsonl', 'score.jsonl',
        'events.jsonl', 'steps.jsonl', 'summary.json'}


class IdentityIntegrityError(ValueError):
    pass


def artifact_manifest(root):
    root = Path(root).resolve()
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise IdentityIntegrityError('source contains symlink; association requires resolution')
        if p.is_file() and p.name not in OVERLAYS | {MANIFEST, MANIFEST+'.pending', ORIGIN+'.pending'}:
            result[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def _publish_once(path, value):
    """Durable no-clobber publication; an interrupted temp is never authority."""
    path = Path(path)
    pending = path.with_name(path.name+'.pending')
    with pending.open('w') as stream:
        stream.write(canonical(value)+'\n'); stream.flush(); os.fsync(stream.fileno())
    try:
        os.link(pending, path)
    except FileExistsError:
        if json.loads(path.read_text()) != value:
            raise IdentityIntegrityError('immutable capture document conflicts')
    finally:
        pending.unlink(missing_ok=True)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def begin_capture(root, *, provenance=None):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    path = root/ORIGIN
    if path.exists():
        origin = json.loads(path.read_text())
        validate_origin(origin)
        return origin
    # Recover the already persisted declaration after a interrupted publication.
    pending = root/(ORIGIN+'.pending')
    if pending.exists():
        origin = json.loads(pending.read_text()); validate_origin(origin)
    else:
        body = dict(schema=SCHEMA, nonce=secrets.token_hex(32),
                    created_at=datetime.now(timezone.utc).isoformat(), provenance=provenance or {})
        origin = dict(body, capture_id='capture:'+digest(body))
    _publish_once(path, origin)
    return origin


def validate_origin(origin):
    body = {k:v for k,v in origin.items() if k!='capture_id'}
    if (origin.get('schema') != SCHEMA or not isinstance(origin.get('nonce'), str)
            or re.fullmatch('[0-9a-f]{64}',origin['nonce']) is None or origin.get('capture_id') != 'capture:'+digest(body)):
        raise IdentityIntegrityError('malformed capture origin identifier')


def content_identity(root, artifacts):
    # Diagnostic/ancillary pixels and locations do not establish a new game.
    # Logs/trajectories are recorded content, still not independent truth.
    core = {k:v for k,v in artifacts.items() if k in CORE}
    return 'content:'+digest(core)


def finalize_capture(root):
    root = Path(root)
    origin = begin_capture(root)
    artifacts = artifact_manifest(root)
    if 'report.json' not in artifacts:
        raise IdentityIntegrityError('capture finalization requires a completed report')
    body = dict(schema=SCHEMA, capture_id=origin['capture_id'], artifacts=artifacts,
                content_id=content_identity(root, artifacts))
    manifest = dict(body, manifest_id='manifest:'+digest(body))
    _publish_once(root/MANIFEST, manifest)
    if artifact_manifest(root) != artifacts:
        raise IdentityIntegrityError('source artifacts changed during finalization')
    return manifest


def inspect_capture(root):
    """Read only. Missing legacy identifiers are derived in the journal, not source."""
    root = Path(root).resolve()
    artifacts = artifact_manifest(root)
    origin = None
    if (root/(ORIGIN+'.pending')).exists() and not (root/ORIGIN).exists():
        raise IdentityIntegrityError('capture origin publication interrupted; producer must resume')
    if (root/ORIGIN).exists():
        origin = json.loads((root/ORIGIN).read_text()); validate_origin(origin)
    if (root/MANIFEST).exists():
        manifest = json.loads((root/MANIFEST).read_text())
        body = {k:v for k,v in manifest.items() if k!='manifest_id'}
        if (manifest.get('schema') != SCHEMA or manifest.get('manifest_id') != 'manifest:'+digest(body)
                or not origin or manifest.get('capture_id') != origin['capture_id']
                or manifest.get('artifacts') != artifacts
                or manifest.get('content_id') != content_identity(root, artifacts)):
            raise IdentityIntegrityError('immutable capture manifest or source artifacts changed')
        status = 'finalized'
    elif origin:
        raise IdentityIntegrityError('capture finalization interrupted; producer must resume before ingestion')
    else:
        body = dict(schema=SCHEMA, artifacts=artifacts, content_id=content_identity(root, artifacts))
        manifest = dict(body, manifest_id='manifest:'+digest(body))
        status = 'legacy; occurrence unknown'
    content = manifest['content_id']
    legacy = ('episode:'+artifacts['report.json'] if 'report.json' in artifacts
              else 'partial-episode:'+digest(artifacts))
    capture = origin['capture_id'] if origin else 'legacy-package:'+digest(artifacts)
    report=json.loads((root/'report.json').read_text()) if (root/'report.json').exists() else {}
    declared=report.get('episode_id')
    diagnostics=('missing legacy identifier; content mapping derived' if declared is None else
                 'legacy identifier verified' if declared==legacy else
                 'malformed/conflicting reported identifier retained; derived alias repaired')
    return dict(declared_episode_id=declared,identifier_diagnostics=diagnostics,
                capture_id=capture, manifest_id=manifest['manifest_id'], content_id=content,
                experience_id=content, observation_id=None, independent_gameplay=False,
                legacy_episode_id=legacy, artifacts=artifacts, capture_status=status,
                provenance=origin.get('provenance', {}) if origin else (
                    json.loads((root/'report.json').read_text()).get('provenance',{})
                    if (root/'report.json').exists() else {}),
                original_origin=origin, original_manifest=manifest)
