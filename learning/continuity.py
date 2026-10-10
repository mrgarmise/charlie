"""Read-only restart acceptance for the existing Executive, never a scheduler.

An interrupted run may append causal work. Immutable history, commission
identity and computed checkpoint continuity must survive that continuation.
Status clocks and process activity are not developmental progress.
"""
import json
from collections import Counter
from pathlib import Path
from memory.evidence import SCHEMA, digest


class ContinuityError(ValueError):
    pass


def require(condition, reason):
    if not condition:raise ContinuityError(reason)


def _records(snapshot):
    originals=snapshot['original_records']
    require(snapshot['records']==len(originals),'snapshot record count inconsistent')
    rows={}
    for row in originals:
        data=json.loads(row['document'])
        require(data.get('schema')==SCHEMA and digest(data)==row['id'],'record integrity changed')
        require(row['id'] not in rows,'duplicate record identity')
        require(all(s in rows for s in data['sources']),'record provenance missing or reordered')
        rows[row['id']]=data
    return rows


def _unique(rows):
    keys={}
    for identifier,d in rows.items():
        p=d['payload'];category=p.get('category');key=None
        if category=='reflection_commission':key=(category,p['context_id'])
        elif category=='learning_context_reference' and p.get('source_episode'):
            key=(category,p['source_episode'])
        elif category=='normal_meditation_result':key=(category,p['context_id'],p['status'])
        elif category=='normal_meditation_yield':
            key=(category,p['context_id'],p['commission_id'],p['checkpoint_sha256'])
        elif category=='preserved_meditation':key=(category,p['source_episode'],p['artifact_sha256'])
        elif category=='preserved_meditation_rejection':key=(category,p['source_episode'],p['artifact_sha256'],p['validator'])
        elif category=='retrospective_meditation_continuation':key=(category,p['ingestion_id'],p.get('meditation_id'),p.get('meditation_rejection_id'))
        elif category=='offline_experiment_plan':key=(category,p['plan']['prediction_id'])
        elif category=='learning_evidence_request' and p.get('dependency_key'):
            key=(category,p['dependency_key'])
        elif category=='acquisition_dependency_satisfied':key=(category,p['request_id'])
        elif d['kind']=='resolution':key=('resolution',p['prediction_id'])
        if key:
            require(key not in keys,'duplicate commission, experience, finding, plan or dependency: '+str(key))
            keys[key]=identifier


def _checkpoints(snapshot, rows):
    checkpoints={}
    for entry in snapshot['checkpoints']:
        path=Path(entry['path']);parts=path.parts
        require('meditations' in parts,'checkpoint outside meditation namespace')
        relative=parts[parts.index('meditations')+1:];context=relative[0]
        d=entry['document']
        require(context in rows,'checkpoint context missing')
        require(rows[context]['payload'].get('category')=='learning_context_reference','checkpoint context is not experience')
        require(d.get('context_id',context)==context,'checkpoint context reset')
        commission=next((i for i,r in rows.items() if r['payload'].get('category')=='reflection_commission'
            and r['payload']['context_id']==context),None)
        require(commission is not None and d.get('commission_id',commission)==commission,'checkpoint commission reset')
        if 'state_digest' in d:
            require(d['state_digest']==digest({k:v for k,v in d.items() if k!='state_digest'}),'checkpoint integrity changed')
        r=d.get('reconstruction',{});left=r.get('left',0);neighbor=r.get('neighbor',0)
        require(isinstance(left,int) and isinstance(neighbor,int) and 0<=left<=len(d['tracks']) and neighbor>=0,'invalid reconstruction cursor')
        checkpoints[tuple(relative)]=dict(entry,context_id=context,commission_id=commission)
    return checkpoints


def fingerprint(checkpoints, context):
    stages=[]
    for key,c in sorted(checkpoints.items()):
        if c['context_id']!=context:continue
        p=c['document'];r=p.get('reconstruction',{})
        stages.append(dict(source=p['source_sha256'],iterations=len(p['history']),
            tracks=digest(p['tracks']),left=r.get('left',0),neighbor=r.get('neighbor',0),
            candidates=len(r.get('candidates',[])),rebuilt=digest(r.get('rebuilt'))))
    return digest(stages)


def _checkpoint_transition(old,new):
    a,b=old['document'],new['document']
    require(old['context_id']==new['context_id'] and old['commission_id']==new['commission_id'],'retained checkpoint identity lost')
    require(a['source_sha256']==b['source_sha256'],'retained checkpoint evidence changed')
    require(b['history'][:len(a['history'])]==a['history'],'completed meditation iteration repeated or reset')
    require(b['merges'][:len(a['merges'])]==a['merges'],'retained reconstruction findings changed')
    if len(b['history'])>len(a['history']):
        count=len(a['tracks']);merges=0
        for i,h in enumerate(b['history'][len(a['history']):],len(a['history'])+1):
            require(h['iteration']==i and h['tracks_before']==count and h['tracks_after']==count-h['merges'],
                'completed iteration accounting inconsistent')
            count=h['tracks_after'];merges+=h['merges']
        require(count==len(b['tracks']) and len(b['merges'])-len(a['merges'])==merges,'iteration lost tracks or merge records')
        def points(tracks):return Counter(digest(p) for t in tracks for p in t.get('path',[]))
        require(points(a['tracks'])==points(b['tracks']),'reconstruction fabricated or discarded observations')
    if len(a['history'])==len(b['history']):
        require(a['tracks']==b['tracks'],'tracks changed without a completed iteration')
        x,y=a.get('reconstruction',{}),b.get('reconstruction',{})
        require((y.get('left',0),y.get('neighbor',0))>=(x.get('left',0),x.get('neighbor',0)),'reconstruction cursor reset')
        require(y.get('candidates',[])[:len(x.get('candidates',[]))]==x.get('candidates',[]),'completed pair comparisons lost or repeated')
        if 'rebuilt' in x:require(y.get('rebuilt')==x['rebuilt'],'completed reconstruction reset')


# A closed protocol vocabulary: arbitrary journal additions cannot pass restart
# acceptance merely because they have a timestamp or a valid content hash.
EXECUTIVE_OPS={'proposed','assessment','selected','outcome','lifecycle','agenda_relationship',
    'agenda_scope_added','evidence_added','investigation_bookmark','meditation_dispatch',
    'evidence_continuation','evidence_search_received','portfolio_deferred','developmental_progress','developmental_wait','operational_feedback'}
CATEGORIES={
    'ScoreObserver':{'score_review_source','score_review_proposal','score_game_record'},
    'human-score-review':{'score_human_annotation','score_review_status'},
    'MemoryEvaluator':{'evaluated_memory_recalled','score_reader_review_reconciliation','score_reader_candidate_evaluation','score_reader_frozen_baseline'},
    'Reflection':{'reflection_commission','normal_meditation_yield','normal_meditation_result',
        'perceptual_experiment_proposal','learning_project_proposal','model_deployment_proposal','retrieval_experiment_reflection','perceptual_learning_deferred'},
    'LearningExecutive':{'reflection_commission'},
    'existing-evidence-consolidation':{'consolidated_evidence_reference','learning_context_reference',
        'retrospective_ingestion','preserved_meditation','preserved_meditation_rejection','retrospective_meditation_continuation','normal_history_restore','notebook_history_recovery'},
    'existing-evidence-acquisition':{'episode_identity_binding','episode_identity_location','episode_identity_alias','episode_identity_quarantine'},
    'ExperienceDataset':{'experience_example','experience_dataset_snapshot','artifact_location'},
    'archive-measurement-service':{'observation_qualification'},
    'existing-acquisition-capability':{'learning_evidence_request','acquisition_delivery','acquisition_delivery_rejected','acquisition_dependency_satisfied','acquisition_search_result'},
    'external-motion-qualification':{'independent_motion_corpus'},
    'offline-orchestrator':{'offline_experiment_deferred'},
    'verified-artifact-resolution':{'experience_artifact_location'},
    'Meditation:learned-representation':{'opaque_visual_groups'},
    'existing-chooser':{'offline_experiment_plan'},
    'ModelFoundry':{'meditation_candidate_evaluation','offline_model_evaluation','model_training','model_candidate_selected','motion_final_consultation'},
    'independent-deployment-boundary':{'offline_authorization_request','qualified_policy_export_blocked'},
    'authorized-capability-deployment':{'capability_activation'},
    'existing-planner-offline-outcome':{'offline_operational_outcome'},
    'controlled-motion-adapter':{'motion_operational_shadow'},
    'controlled-policy-adapter':{'decision_policy_shadow'},
}


def compare_restart(before,after):
    old=_records(before);rows=_records(after)
    require(after['original_records'][:len(old)]==before['original_records'],'original evidence lost, changed, reordered or recommitted')
    _unique(rows)
    for s in (before,after):
        require(s.get('physical_authorization') is False,'physical authorization boundary changed')
        status=s.get('status') or {}
        require(status.get('physical_authorization') is False and not status.get('error'),'developmental lifecycle error or physical authority')
    oc,nc=_checkpoints(before,old),_checkpoints(after,rows)
    require(set(oc)<=set(nc),'durable meditation checkpoint lost')
    advanced=[]
    for key,c in oc.items():
        _checkpoint_transition(c,nc[key])
        if fingerprint(oc,c['context_id'])!=fingerprint(nc,c['context_id']):advanced.append(c['context_id'])
    progress={i:d['payload'] for i,d in old.items() if d['payload'].get('op')=='developmental_progress'}
    latest={p['work_id']:(i,p) for i,p in progress.items()}
    substantive=[];counts={};new_ids=list(rows)[len(old):]
    for identifier in new_ids:
        d=rows[identifier];p=d['payload'];category=p.get('category');op=p.get('op');producer=d['producer']
        allowed=(producer=='LearningExecutive' and op in EXECUTIVE_OPS or
            category in CATEGORIES.get(producer,set()) or
            d['kind'] in ('prediction','resolution') and producer in ('existing-memory-offline-test','ModelFoundry') or
            producer.startswith('CapabilityRegistry:') and category=='model_diagnostic_retrieval')
        require(allowed,'unclassified restart evidence requires review: '+producer+'/'+str(category or op or d['kind']))
        require(p.get('physical_authorization') is not True,'restart record grants physical authority')
        if category=='capability_activation':
            require(p.get('authorization',{}).get('execution')!='physical','physical activation during offline acceptance')
        label=category or op or d['kind'];counts[label]=counts.get(label,0)+1
        if category=='preserved_meditation_rejection':
            context=rows.get(p.get('context_id'),{}).get('payload',{})
            h=p.get('artifact_sha256','')
            require(context.get('category')=='learning_context_reference' and
                context.get('source_episode')==p.get('source_episode') and p.get('context_id') in d['sources'] and
                len(h)==64 and all(c in '0123456789abcdef' for c in h) and p.get('artifact_path') and
                p.get('status')=='rejected' and p.get('reason') and p.get('validator') and p.get('resumption_condition'),
                'rejected finding lacks exact source context, hash or resumption dependency')
        elif category=='retrospective_meditation_continuation':
            origin=rows.get(p.get('ingestion_id'),{}).get('payload',{})
            finding=p.get('meditation_id') or p.get('meditation_rejection_id')
            result=rows.get(finding,{}).get('payload',{})
            require(origin.get('category')=='retrospective_ingestion' and
                origin.get('meditation_rejection_id') and origin.get('source_episode')==p.get('source_episode') and
                result.get('source_episode')==p.get('source_episode') and
                result.get('category') in ('preserved_meditation','preserved_meditation_rejection') and
                p.get('ingestion_id') in d['sources'] and finding in d['sources'],
                'finding continuation lacks retained ingestion and validated result lineage')
        elif op=='developmental_progress':
            work=p['work_id'];prior=latest.get(work)
            require(p.get('previous')==(prior[0] if prior else None),'developmental progress lineage reset')
            # Experiment completion binds an independent resolution, whereas
            # meditation continuation must start at its last computed cursor.
            if prior and work in {c['context_id'] for c in nc.values()}:
                require(p['before']==prior[1]['after'],'meditation restarted from another checkpoint')
            if work in {c['context_id'] for c in oc.values()} and not prior:
                require(p['before']==fingerprint(oc,work),'first resumed turn lost its checkpoint')
            completed=p['outcome']=='completed'
            if completed:
                require(any(r['payload'].get('category')=='normal_meditation_result' and r['payload']['context_id']==work and r['payload']['status']=='completed'
                    or r['kind']=='resolution' and r['payload']['prediction_id'] in d['sources'] for r in rows.values()),'completion lacks durable result or evaluation')
            actual=p['before']!=p['after'] or completed
            require(p['progress_occurred']==actual,'activity incorrectly claimed as progress')
            require(p['status'] in ('advancing','yielded','blocked','completed'),'unknown retained work state')
            if actual:require(p['nonprogress_turns']==0,'progress counted as a stall')
            if p['status']=='blocked':
                known_dependency=False
                if p['outcome']=='blocked':
                    for request in rows.values():
                        rp=request['payload'];specs=rp.get('required_evidence',[])
                        if rp.get('category')!='learning_evidence_request' or rp.get('work_id')!=work or len(specs)!=1:continue
                        spec=specs[0]
                        if not isinstance(spec,dict) or spec.get('type')!='preserved_tracks_artifact':continue
                        origin=rows.get(work,{}).get('payload',{})
                        commission=rows.get(spec.get('commission_id'),{}).get('payload',{})
                        known_dependency=(spec.get('context_id')==work and
                            spec.get('source_episode')==origin.get('source_episode') and
                            commission.get('category')=='reflection_commission' and commission.get('context_id')==work and
                            (not any(c['context_id']==work for c in nc.values()) or
                             any(c['context_id']==work and c['document']['source_sha256']==spec.get('sha256') for c in nc.values())))
                        if known_dependency:break
                require(p.get('resumption_condition') and (p['nonprogress_turns']>=3 or known_dependency),
                    'blocked work lacks durable resumption condition')
            latest[work]=(identifier,p)
            if actual:substantive.append(identifier)
        elif category=='acquisition_search_result':
            request=rows.get(p.get('request_id'),{}).get('payload',{})
            require(request.get('category')=='learning_evidence_request' and
                p.get('work_id')==request.get('work_id') and
                p.get('required_evidence')==request.get('required_evidence') and
                p.get('request_id') in d['sources'] and
                p.get('new_independent_experience') is False and
                p.get('status') in ('delivered','unsatisfied'), 'search changed original dependency or experience identity')
            if p['status']=='delivered':
                delivery=rows.get(p.get('delivery_id'),{}).get('payload',{})
                require(delivery.get('category')=='acquisition_dependency_satisfied' and
                    delivery.get('request_id')==p['request_id'],'search delivery not bound to original request')
        elif op=='evidence_search_received':
            search=rows.get(p.get('search_id'),{}).get('payload',{})
            require(search.get('category')=='acquisition_search_result' and
                p.get('work_id')==search.get('work_id') and p.get('status')==search.get('status') and
                p.get('request_id')==search.get('request_id') and
                p.get('unresolved_dependency')==search.get('next_requirement') and
                p.get('hypothesis_result')=='unchanged' and p.get('evidence_qualified') is False,
                'Executive receipt promoted or changed acquisition evidence')
        elif category=='acquisition_dependency_satisfied':
            request=rows.get(p.get('request_id'),{}).get('payload',{})
            requirements=request.get('required_evidence',[])
            require(len(requirements)==1 and isinstance(requirements[0],dict),'delivery lacks exact retained dependency')
            spec=requirements[0]
            example=rows.get(p.get('example_id'),{}).get('payload',{})
            location_bound=(p.get('example_id') in d['sources'] and p.get('path')==example.get('pixel_path') or any(
                rows[s]['payload'].get('category')=='experience_artifact_location' and
                rows[s]['payload'].get('example')==p.get('example_id') and
                rows[s]['payload'].get('path')==p.get('path') and rows[s]['payload'].get('sha256')==p.get('sha256')
                for s in d['sources']))
            if spec.get('type')=='valid_preserved_prediction_finding':
                finding=rows.get(p.get('finding_id'),{}).get('payload',{})
                require(finding.get('category')=='preserved_meditation' and
                    finding.get('source_episode')==spec.get('source_episode') and
                    finding.get('prior_use')==spec.get('prior_use') and
                    finding.get('artifact_sha256')!=spec.get('rejected_sha256') and
                    p.get('finding_id') in d['sources'] and p.get('request_id') in d['sources'] and
                    p.get('work_id')==request.get('work_id')=='preserved-meditation:'+spec['source_episode'] and
                    p.get('new_independent_experience') is False,
                    'replacement finding does not satisfy exact rejected dependency')
                substantive.append(identifier)
                continue
            require(spec.get('type')=='preserved_pixel_artifact' and
                spec.get('example_id')==p.get('example_id') and spec.get('sha256')==p.get('sha256') and
                example.get('category')=='experience_example' and example.get('pixel_sha256')==p.get('sha256') and location_bound and
                request.get('work_id')==p.get('work_id') and p.get('request_id') in d['sources'] and
                p.get('new_independent_experience') is False,'delivery does not qualify original requested bytes')
            substantive.append(identifier)
        elif d['kind']=='resolution' or category=='normal_meditation_result' and p['status']=='completed' or category in ('offline_model_evaluation','acquisition_delivery','offline_operational_outcome'):
            substantive.append(identifier)
    for context in set(advanced):
        require(context in latest and latest[context][1]['after']==fingerprint(nc,context),'checkpoint advancement lacks matching Executive accounting')
        yields=[d['payload'] for d in rows.values() if d['payload'].get('category')=='normal_meditation_yield' and d['payload']['context_id']==context]
        result=any(d['payload'].get('category')=='normal_meditation_result' and d['payload']['context_id']==context for d in rows.values())
        if latest[context][1]['outcome']!='completed':
            require(yields and any(c['sha256']==yields[-1]['checkpoint_sha256'] for c in nc.values() if c['context_id']==context),'yield does not bind current durable checkpoint')
        else:require(result,'completed meditation has no machine-consumable result')
    projected={work:dict(p,record_id=i) for work,(i,p) in latest.items()}
    require(after['work']==projected,'reported work disagrees with durable Executive records')
    status=after['status'];runnable=[k for k,p in projected.items() if p['status'] in ('advancing','yielded')]
    blocked=[k for k,p in projected.items() if p['status']=='blocked']
    waiting=status.get('last_activity')=='waiting for evidence'
    require(not waiting or not runnable,'waiting state hides runnable retained work')
    require(not waiting or not (status.get('turn_outcome') or {}).get('runnable_work_remaining'),
        'waiting state hides eligible uncommissioned work')
    require(not (status.get('turn_outcome') or {}).get('progress_occurred') or bool(substantive),
        'status claims progress without a durable stage')
    return dict(schema='developmental-restart-acceptance-v1',continuity_passed=True,
        original_records_preserved=len(old),appended_records=len(new_ids),new_record_categories=counts,
        substantive_progress=bool(substantive),progress_records=substantive,
        advanced_meditations=sorted(set(advanced)),runnable_work=runnable,blocked_work=blocked,
        completed_work=[k for k,p in projected.items() if p['status']=='completed'],
        classification='continued' if substantive else 'waiting' if waiting else 'yielded_without_progress',
        steady_state_reached=waiting and not runnable,restart_exact=not new_ids,
        physical_authorization=False,physical_score_improvement='UNKNOWN')
