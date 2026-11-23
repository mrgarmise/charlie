"""Candidate-only connection to the existing native broker and durable answer journal."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import re
import time

from .inquiry import Inquiry, MODEL_DIGEST

PREFIX = 'Discovery pass D. '


def catalog_from_policy(settings):
    """Only root reads this operator-pinned artifact. The Executive cannot extend it."""
    from learning.native_meditation.security import root_read
    if settings.get('model_enabled') is not True:
        return {}
    raw = root_read(settings['prompt_catalog'], 32768)
    if hashlib.sha256(raw).hexdigest() != settings['prompt_catalog_sha256']:
        raise PermissionError('discovery prompt catalog changed')
    document = json.loads(raw)
    if document['archive_version'] != settings['archive_version']:
        raise PermissionError('discovery prompt catalog version mismatch')
    prompts = document['prompts']
    if not isinstance(prompts, dict) or not 1 <= len(prompts) <= 256:
        raise ValueError('bounded discovery prompt catalog required')
    if any(not re.fullmatch('[a-f0-9]{64}', k) or not isinstance(v, str) or
           not re.fullmatch('[A-Za-z0-9_.:-]{1,100}', v) for k,v in prompts.items()):
        raise ValueError('invalid pinned discovery prompt identity')
    return prompts


def public_settings(policy):
    settings = policy.get('discovery')
    if not isinstance(settings, dict) or settings.get('enabled') is not True:
        return None
    settings = {key: settings[key] for key in ('archive_dir', 'archive_version', 'archive_manifest_sha256', 'journal_path')}
    if any(not re.fullmatch('[0-9a-f]{64}', settings[k]) for k in ('archive_version','archive_manifest_sha256')):
        raise ValueError('pinned archive version required')
    if any(not Path(settings[k]).is_absolute() for k in ('archive_dir', 'journal_path')):
        raise ValueError('absolute discovery storage paths required')
    settings['prompts'] = catalog_from_policy(policy['discovery'])
    settings['revision'] = policy['code_revision']
    return settings


class NativeInquiry:
    """Only the canonical native coordinator calls this adapter inside its exclusive window."""
    def __init__(self, settings, consultation, sources, answer_journal):
        from .archive import Archive, audit_archive
        from .journal import Journal
        self.settings, self.consultation = settings, consultation
        area = Path(settings['archive_dir']).resolve(strict=True)
        path = Path(settings['journal_path']).resolve()
        if area == path or area in path.parents:
            raise ValueError('research journal overlaps immutable archive')
        for source in [answer_journal, *sources]:
            other = Path(source).resolve()
            if other == path or (other.exists() and path.exists() and other.samefile(path)):
                raise ValueError('research journal aliases operational data')
        self.stack = ExitStack()
        try:
            audit = audit_archive(area, expected_manifest_sha256=settings['archive_manifest_sha256'])
            if audit['type'] != 'owner-seed':
                raise ValueError('native inquiry requires a verified owner archive')
            archive = self.stack.enter_context(Archive(area))
            if archive.version != settings['archive_version']:
                raise ValueError('discovery archive differs from policy pin')
            journal = self.stack.enter_context(Journal(path))
            journal.add_questions(archive.questions())
            self.inquiry = Inquiry(archive, journal, revision=settings['revision'])
        except BaseException:
            self.stack.close()
            raise

    def close(self):
        self.stack.close()

    def on_reserved_window(self, commission_id, lease, guard, deadline):
        # Rate/replay is charged even for source-only work, before any research write.
        lease.reserve_budget(commission_id, self.consultation.daily_limit, self.consultation.cooldown)
        def consult(prompt, check):
            digest = hashlib.sha256(prompt.encode()).hexdigest()
            if digest not in self.settings['prompts']:
                raise PermissionError('source-first: no reviewed exact prompt')
            check()
            if lease.ends_at-time.time() < 40 or time.monotonic()+40 >= deadline:
                raise TimeoutError('insufficient prewarm headroom')
            approval = lease.prepare(model='qwen3:1.7b', digest=MODEL_DIGEST, ends_at=lease.ends_at)
            check()
            if time.monotonic()+35 >= deadline:
                raise TimeoutError('insufficient post-prewarm headroom')
            provider = self.consultation.provider_factory(approval)
            try:
                result = provider.consult(prompt, check)
                check()
                # The existing root verifier separately checks this durable receipt and unload.
                self.consultation.queue.journal.append('event', dict(category='discovery_consultation',
                    state='answer-durable', trust='unverified_hypothesis', result=result,
                    question_id=self.settings['prompts'][digest], prompt_sha256=digest, slot_id=lease.id),
                    episode='discovery', producer='LearningExecutive:meditation', version='discovery-v1')
                provider.retained()
                if provider.status()['state'] != 'completed-unload-confirmed':
                    raise InterruptedError('consultation cleanup unconfirmed')
                return result
            finally:
                provider.close()
        return self.inquiry.run_slot(commission_id, check=guard,
            client_deadline=min(deadline-2, time.monotonic()+lease.ends_at-time.time()-5),
            consult=consult if self.settings['prompts'] else None)
