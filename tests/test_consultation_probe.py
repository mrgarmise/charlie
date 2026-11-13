"""Benchmark receipts and cleanup with fixtures; no native qualification."""
import json
import sys

import pytest

from tools import consultation_probe as probe


@pytest.mark.parametrize('failure', [False, True])
def test_benchmark_preserves_optional_metrics_and_unloads(monkeypatch, tmp_path, failure):
    output = tmp_path / 'report'
    monkeypatch.setattr(sys, 'argv', ['probe', '--output', str(output), '--benchmark', '--warm'])
    monkeypatch.setattr(probe, 'snapshot', lambda: {'fixture': True})
    monkeypatch.setattr(probe, 'consultation_resources', lambda check: None)
    monkeypatch.setattr(probe, 'QUESTIONS', ('fixture question',))

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, bound): return b'{}'

    monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: Response())

    class Provider:
        def __init__(self, config): pass
        def consult(self, question, check):
            if failure:
                raise InterruptedError('fixture resource refusal')
            return {'answer': 'Unverified fixture answer', 'metrics': {
                'prompt_eval_duration': 1000, 'eval_duration': 1000000000, 'eval_count': 0}}

    monkeypatch.setattr(probe, 'OllamaProvider', Provider)
    unload = []
    monkeypatch.setattr(probe, '_http', lambda *args: unload.append(args))
    if failure:
        with pytest.raises(InterruptedError):
            probe.main()
    else:
        probe.main()
    records = [json.loads(line) for line in (output / 'answers.jsonl').read_text().splitlines()]
    assert len(records) == 1
    if failure:
        assert records[0]['error'] == 'InterruptedError'
    else:
        result = records[0]['result']
        assert result['answer'] == 'Unverified fixture answer'
        assert result['metrics']['prompt_eval_count_per_second'] is None
        assert result['metrics']['eval_count_per_second'] == 0
        assert records[0]['usefulness'] == 'PENDING HUMAN REVIEW'
    assert len(unload) == 1
    assert unload[0][1:] == ({'model': 'qwen3:1.7b', 'keep_alive': 0}, '/api/generate')
    assert json.loads((output / 'postflight.json').read_text()) == {'fixture': True}
    assert (output / 'samples.json').exists()
