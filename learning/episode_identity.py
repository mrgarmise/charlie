"""Autonomous identity verification owned by existing evidence acquisition.

All repairs are append-only journal projections. Original IDs and bytes remain
unchanged; source locators enforce integrity, never establish independence.
"""
import json
from pathlib import Path
from memory.episode_identity import inspect_capture, IdentityIntegrityError, CORE
from memory.evidence import digest
from .datasets import SCOPE, sha

VERSION = 'episode-identity-v1'


def _events(journal, category):
    return [r for r in journal.records('event') if r.data['payload'].get('category')==category]


def _append(journal, category, payload):
    return journal.append('event', dict(category=category, **payload), episode=SCOPE,
                          producer='existing-evidence-acquisition', version=VERSION)


def _qualification(root, identity):
    path = Path(root)/'episode-qualification.json'
    if not path.is_file():
        return identity
    proof = json.loads(path.read_text())
    if (proof.get('schema')!='episode-identity-witness-v1'
            or proof.get('source') not in ('independent_measurement','external_annotation')
            or not proof.get('observer') or not proof.get('occurrence_key')
            or proof.get('capture_id')!=identity['capture_id']
            or proof.get('manifest_id')!=identity['manifest_id']):
        raise IdentityIntegrityError('independent occurrence witness malformed or not bound to capture manifest')
    boundaries = proof.get('boundaries', {})
    if set(boundaries)!={'start','terminal'}:
        raise IdentityIntegrityError('independent start and terminal witness required')
    hashes = []
    for ref in boundaries.values():
        if not isinstance(ref,dict) or identity['artifacts'].get(ref.get('path'))!=ref.get('sha256'):
            raise IdentityIntegrityError('independent boundary artifacts not in immutable manifest')
        hashes.append(ref['sha256'])
    if len(set(hashes))!=2:
        raise IdentityIntegrityError('distinct independently observed boundaries required')
    occurrence = dict(observer=proof['observer'], occurrence_key=proof['occurrence_key'])
    return dict(identity, observation_id='qualified-observation:'+digest(proof),
                experience_id='experience:'+digest(occurrence), independent_gameplay=True,
                qualification=proof)


def quarantine(journal, root, reason, *, identity=None, competing=()):
    root = str(Path(root).resolve())
    try:
        from memory.episode_identity import artifact_manifest
        observed = artifact_manifest(root)
    except (OSError,ValueError):
        observed = None
    case = dict(source_root=root, reason=reason, observed_artifacts=observed,
        capture_id=(identity or {}).get('capture_id'), manifest_id=(identity or {}).get('manifest_id'),
        competing_associations=list(competing),
        hypotheses=['separate capture package with correlated experience',
                    'modified original source or inconsistent provenance'],
        required_evidence=['Original immutable manifest/origin and matching bytes',
                           'Independent hash-bound start/terminal occurrence witness for distinct gameplay'],
        excluded_from_evaluation=True, new_physical_experience=False)
    record = _append(journal,'episode_identity_quarantine',case)
    _append(journal,'episode_identity_location',dict(source_root=root,status='quarantined',case_id=record.id,
        manifest_id=case['manifest_id'],observed_digest=digest(observed)))
    return dict(status='quarantined',record_id=record.id,reason=reason,**{k:v for k,v in (identity or {}).items() if k not in ('status','record_id','reason')})


def reconcile(root, journal):
    """Called on every normal acquisition/recovery pass; retry unresolved cases."""
    root = Path(root).resolve()
    identity = None
    try:
        identity = _qualification(root, inspect_capture(root))
        artifacts = identity['artifacts']
        bindings = _events(journal,'episode_identity_binding')
        for r in bindings:
            old = r.data['payload']
            if old['capture_id']==identity['capture_id'] and old['manifest_id']!=identity['manifest_id']:
                raise IdentityIntegrityError('previously verified capture artifacts changed')
            # Same externally observed occurrence cannot acquire conflicting content.
            if (identity['independent_gameplay'] and old['experience_id']==identity['experience_id']
                    and old['content_id']!=identity['content_id']):
                raise IdentityIntegrityError('qualified occurrence has conflicting experience content')
        locations = _events(journal,'episode_identity_location')
        verified = [r.data['payload'] for r in locations if r.data['payload']['source_root']==str(root)
                    and r.data['payload']['status']=='verified']
        if verified and any(r['manifest_id']!=identity['manifest_id'] for r in verified):
            raise IdentityIntegrityError('previously verified source locator artifacts changed')
        # Original journal manifests are authoritative even before migration.
        legacy = identity['legacy_episode_id']
        originals = [r for r in journal.records('observation') if
            r.data['payload'].get('category')=='learning_context_reference'
            and r.data['payload'].get('source_episode')==legacy]
        frozen = []
        for r in originals:
            p=r.data['payload']
            saved=p.get('inventory')
            if saved is None and p.get('source_journal'):
                from memory.evidence import EvidenceJournal
                candidate=journal.path.parent/'episodes'/Path(p['source_journal']).name
                if candidate.is_file():
                    source=EvidenceJournal(candidate,read_only=True)
                    try:
                        saved=next(({k:v['sha256'] for k,v in e.data['payload']['artifacts'].items()}
                            for e in source.records('episode') if e.data['episode']==legacy),None)
                    finally: source.close()
            if saved: frozen.append((r,saved))
        # Ancillary image differences do not collide with gameplay identity.
        prior = [r.data['payload'] for r in bindings if r.data['payload']['legacy_episode_id']==legacy]
        prior_cores = [{k:v for k,v in b['artifacts'].items() if k in CORE} for b in prior]
        prior_cores += [{k:v for k,v in a.items() if k in CORE} for _,a in frozen]
        core={k:v for k,v in artifacts.items() if k in CORE}
        if prior_cores and any(c!=core for c in prior_cores) and not identity['independent_gameplay']:
            return quarantine(journal,root,'legacy report alias has incompatible experience content; occurrence uncertain',
                identity=identity,competing=[r.id for r in originals]+[r.id for r in bindings
                    if r.data['payload']['legacy_episode_id']==legacy])
        # A known historical original location is an integrity constraint.
        for r,a in frozen:
            p=r.data['payload']
            recorded=p.get('source_root')
            if recorded==str(root) and a!=artifacts:
                raise IdentityIntegrityError('historically recorded source artifacts changed')
        # Keep legacy developmental identity where unambiguous. Separate qualified
        # occurrences sharing a report use their externally supported identity.
        same = next((b for b in prior if b['experience_id']==identity['experience_id']),None)
        episode = same['source_episode'] if same else (
            identity['experience_id'] if identity['independent_gameplay'] else legacy)
        payload=dict(identity,source_episode=episode,
                     alias_status='legacy alias retained; source occurrence not inferred from report',
                     historical_context_ids=[r.id for r in originals if not r.data['payload'].get('manifest_id')],new_physical_experience=False)
        binding=_append(journal,'episode_identity_binding',payload)
        location=_append(journal,'episode_identity_location',dict(source_root=str(root),status='verified',
            manifest_id=identity['manifest_id'],binding_id=binding.id))
        return dict(payload,status='verified',binding_id=binding.id,location_id=location.id)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        return quarantine(journal,root,str(exc),identity=identity)


def bindings(journal):
    return [r.data['payload'] for r in _events(journal,'episode_identity_binding')]


def canonical_experience(journal, episode):
    values={b['experience_id'] for b in bindings(journal) if b['source_episode']==episode}
    return next(iter(values)) if len(values)==1 else episode


def eligible(journal, payload):
    """A quarantined locator does not invalidate a verified copy or other source."""
    locations={}
    for r in _events(journal,'episode_identity_location'):
        locations[r.data['payload']['source_root']]=r.data['payload']
    candidates=[b for b in bindings(journal) if b['source_episode']==payload.get('source_episode')]
    manifest=payload.get('manifest_id')
    if manifest: candidates=[b for b in candidates if b['manifest_id']==manifest]
    if not candidates:
        return True  # Historical evidence is not retroactively declared missing.
    return any(l['status']=='verified' and l['manifest_id']==b['manifest_id']
               for b in candidates for l in locations.values())


def verified_tracks(journal):
    locations={r.data['payload']['source_root']:r.data['payload'] for r in _events(journal,'episode_identity_location')}
    result={}
    for b in bindings(journal):
        expected=b['artifacts'].get('tracks.json')
        if not expected: continue
        for root,l in locations.items():
            p=Path(root)/'tracks.json'
            if (l['status']=='verified' and l['manifest_id']==b['manifest_id']
                    and p.is_file() and sha(p)==expected):
                result.setdefault(b['source_episode'],p)
    return result


def current_conflicts(journal):
    locations={r.data['payload']['source_root']:r.data['payload'] for r in _events(journal,'episode_identity_location')}
    return [dict(case_id=l['case_id'],**journal.get(l['case_id']).data['payload'])
            for l in locations.values() if l['status']=='quarantined']
