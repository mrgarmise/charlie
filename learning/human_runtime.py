"""Opt-in information review on the existing Executive's acquisition thread."""


def review_information(lifecycle):
    executive, service = lifecycle.executive, lifecycle.human_questions
    before = len(lifecycle.journal.records())
    # Answers stay attributed, fallible and pending independent review. Intake
    # does not train a model, change score truth or grant an actuator authority.
    for owner in ('pet_observe', 'robotron'):
        executive.receive_human_answers(service, owner)
    rows = lifecycle.journal.category_records('observation', 'mobile_perception')
    rows += lifecycle.journal.category_records('observation', 'score_review_proposal')
    # Bound work per turn; the gateway independently checks original UTC commit
    # freshness, source track age, uncertainty, cooldown and queue/day limits.
    for row in sorted(rows, key=lambda r: r.sequence)[-32:]:
        lifecycle.yield_for_primary()
        payload = row.data['payload']
        if payload['category'] == 'mobile_perception':
            observation = payload['observation']
            if not observation['frame'].get('authentic'):
                continue
            target = payload['tracking'].get('target') or {}
            # Prefer further observation for an unstable or ambiguous track.
            # Recheck each turn independently of per-track opportunity dedup.
            alternatives = target.get('lifecycle') != 'confirmed' or target.get('ambiguous', True)
        else:
            # Score proposals already represent a deferred interpretation; an
            # answer cannot bypass the separate score qualification pipeline.
            alternatives = False
        executive.consider_human_question(service, row.id,
            reason='Review conflicting retained interpretation before later learning; defer physical action',
            consequence=1., priority=1, alternative_available=alternatives)
    return len(lifecycle.journal.records()) != before
