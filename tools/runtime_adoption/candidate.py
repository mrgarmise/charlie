"""Build an unapproved, fully disabled candidate proposal from observed identities."""
import hashlib
from .promotion import canonical, require


def assemble(ledger, inventory, receipts, *, rollback_sha, backup_manifests):
    require(ledger.get('schema')=='charlie-ability-ledger-v2','ability ledger schema')
    require(bool(backup_manifests),'explicit backup manifest paths required')
    observed={x['path']:x['sha256'] for x in inventory.get('protected',[])}
    require(all(p in observed for p in backup_manifests),'backup manifest not inventoried')
    identity=lambda value:{k:value[k] for k in ('sha','tree')}
    source=identity(inventory['candidate']);baseline=identity(inventory['baseline'])
    abilities=[]
    for row in ledger['abilities']:
        touches=row.get('touches',{})
        abilities.append(dict(id=row['id'],purpose=row['purpose'],enabled=False,
            source_present=row.get('source_present',False),dependencies=row.get('dependencies',[]),
            provenance=row.get('latest_source'),integration_revision=row.get('integration_revision'),
            motion=touches.get('motion',False),touches_firmware=any(n in (29,30,31,32) for n in row.get('owning_prs',[])),
            autonomous_consultation=row.get('native_autonomous_consultation','NOT APPLICABLE')!='NOT APPLICABLE',
            required_native_gates=row.get('prerequisites',[]),native_gates={},installed_firmware_sha256=None,
            physical_stop_verified=False,rp2040_ack_ttl_qualified=False,authentic_eligible_question=False))
    guards=inventory.get('manual_llm_guards',{})
    return dict(schema='charlie-adoption-candidate-v2',version='source-'+source['sha'],candidate=source,baseline=baseline,
        state_migration='none',unreconciled_branches=[],protected=observed,
        rollback=dict(sha=rollback_sha,backup_manifests={p:observed[p] for p in backup_manifests}),
        manual_llm_guards=dict(baseline_preserved=bool(guards.get('baseline')) and guards.get('baseline')==guards.get('candidate'),
            resource_limits_changed=False,autonomous_enabled=False,guardian_started=False,
            source_sha256={k:v for k,v in guards.get('baseline',{}).items() if not k.startswith('function:')}),
        required_ci=['full','contracts','baseline-llm','browser','firmware-host','firmware-build','neural-cpu'],
        ci_bundle_sha256=hashlib.sha256(canonical(receipts)).hexdigest(),abilities=abilities,
        proposal_only=True,approved=False,installed=False,
        warnings=['Native results deliberately unknown; disabled source is not qualification.',
                  'Historical backup manifests do not establish a fresh complete release backup.'])
