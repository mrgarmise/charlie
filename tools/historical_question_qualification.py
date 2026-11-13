"""One-shot, historical Charlie question -> existing qualified OperationalProvider.

No sensing, question generation, autostart or weakened native admission. The
original evidence journal is read-only. The response goes to a NEW notebook.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from learning.consultation_activation import OperationalProvider
from memory.evidence import EvidenceJournal

DEFAULT_QUESTION = '5524edc23f1affbda1d8a65253b7bd1000e52df6c66661f6d86bf4609a745643'
DEFAULT_SOURCE = Path.home() / '.local/share/charlie/development/recovered-history/e6c8ab596f071eae7da5ba09a2151f7ffb5b92bdef3855fda6f6f0520dff3d79/learning-evidence.sqlite3'
VERSION = 'historical-question-qualification-v1'


def load_question(journal_path, question_id):
    """Read and verify the *original*, immutable historical evidence."""
    with_source = EvidenceJournal(journal_path, read_only=True)
    try:
        row = with_source.get(question_id)
        p = row.data.get('payload', {})
        if row.data['kind'] != 'event' or p.get('category') != 'learning_project_proposal' or row.data.get('producer') != 'Reflection':
            raise ValueError('not the reviewed historical Reflection proposal')
        proposal = p.get('proposal', {})
        question = proposal.get('goal')
        if not isinstance(question, str) or not question.strip() or '?' not in question or len(question.encode()) > 500:
            raise ValueError('bounded original question not found')
        refs = row.data.get('sources', [])
        if len(refs) != 1:
            raise ValueError('expected one original proposal source')
        source = with_source.get(refs[0])
        if source.data['payload'].get('category') != 'perceptual_experiment_proposal':
            raise ValueError('question has unexpected source type')
        if source.data['payload'].get('proposal', {}).get('question') != question:
            raise ValueError('original question and referenced proposal disagree')
        return dict(question=question, id=row.id, committed_at=row.committed_at,
                    episode=row.data['episode'], original_sources=refs,
                    source_committed_at=source.committed_at,
                    motivation=str(proposal.get('motivation', ''))[:240],
                    alternatives=[str(x)[:120] for x in proposal.get('open_questions', [])][:4],
                    source_db=str(Path(journal_path).resolve()),
                    source_sha256=hashlib.sha256(Path(journal_path).read_bytes()).hexdigest())
    finally:
        with_source.close()


def prompt_for(item):
    """Only literal historical context; no sensor claims or fabricated current data."""
    lines = [
        'Historical investigation, not a live observation. Do not assume current sensor data.',
        'Charlie previously asked: ' + item['question'],
        'Recorded motivation: ' + item['motivation'],
        'Recorded alternatives: ' + '; '.join(item['alternatives']),
        'Suggest one safe, independently testable offline experiment and state uncertainty.',
    ]
    prompt = '\n'.join(lines)
    if len(prompt.encode('utf-8')) > 1024:
        raise ValueError('historical consultation prompt exceeds provider limit')
    return prompt


def run_once(source, question_id, notebook, approval, *, provider_factory=OperationalProvider):
    """Fail closed; one request maximum; never clear unknown-completion marker."""
    item = load_question(source, question_id)
    prompt = prompt_for(item)
    notebook = Path(notebook)
    if notebook.exists():
        raise ValueError('qualification notebook exists; refusing duplicate or retry')
    if not Path(approval).is_file():
        raise ValueError('native safe-idle approval file required')
    old_umask = os.umask(0o077)
    try:
        notebook.mkdir(mode=0o700, parents=False)
        journal_path = notebook / 'learning-evidence.sqlite3'
        journal = EvidenceJournal(journal_path)
    finally:
        os.umask(old_umask)
    provider = None
    try:
        episode = 'historical-consultation-' + item['id'][:16]
        basis = journal.append('event', dict(category='historical_consultation', op='selected',
            original=item, prompt=prompt, trust='unverified_hypothesis',
            physical_authorization=False, model_update=False), episode=episode,
            producer='HistoricalQuestionQualification', version=VERSION)
        submitted = journal.append('event', dict(category='historical_consultation', op='submitted',
            original_question_id=item['id'], model='qwen3:1.7b',
            physical_authorization=False), episode=episode, sources=[basis.id],
            producer='HistoricalQuestionQualification', version=VERSION)
        provider = provider_factory(str(approval))
        try:
            result = provider.consult(prompt)
            if not isinstance(result.get('answer'), str) or not result['answer'].strip():
                raise ValueError('empty answer')
            if not isinstance(result.get('identity'), dict) or not result['identity'].get('model_digest'):
                raise ValueError('qualified provider identity missing')
            answered = journal.append('event', dict(category='historical_consultation', op='answered',
                original_question_id=item['id'], question=item['question'], result=result,
                trust='unverified_hypothesis', physical_authorization=False,
                model_update=False), episode=episode, sources=[submitted.id],
                producer='HistoricalQuestionQualification', version=VERSION)
            # Only after the durable journal receipt may the provider clear its latch.
            provider.retained()
            state = provider.status()['state']
            return dict(answer=result['answer'], evidence_id=answered.id,
                        provider_state=state, cleanup_confirmed=(state == 'completed-unload-confirmed'),
                        notebook=str(journal_path),
                        identity=result['identity'])
        except BaseException as exc:
            journal.append('event', dict(category='historical_consultation', op='deferred',
                reason=type(exc).__name__, original_question_id=item['id'],
                no_automatic_retry=True, physical_authorization=False), episode=episode,
                sources=[submitted.id], producer='HistoricalQuestionQualification', version=VERSION)
            raise
    finally:
        if provider is not None:
            provider.close()
        journal.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'consult'))
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--question-id', default=DEFAULT_QUESTION)
    parser.add_argument('--notebook', type=Path)
    parser.add_argument('--approval', type=Path)
    args = parser.parse_args()
    if args.action == 'inspect':
        item = load_question(args.source, args.question_id)
        print(json.dumps(dict(item, prompt=prompt_for(item)), indent=2))
        return
    if not args.notebook or not args.approval:
        parser.error('consult requires --notebook and --approval')
    print(json.dumps(run_once(args.source, args.question_id, args.notebook, args.approval), indent=2))


if __name__ == '__main__':
    main()
