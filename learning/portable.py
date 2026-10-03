"""Export the existing evaluated classifier for NumPy-only inference.

No training, new labels, game control, or deployment authority is supplied here.
The portable journal becomes the local authority; source rollbacks must also be
transferred before another episode. A copied snapshot is not a revocation feed.
"""
import json
import math
import os
from pathlib import Path
import sqlite3
import time
import numpy as np
from PIL import Image
from memory.evidence import digest
from .datasets import sha
from .foundry import atomic_json, validate_spec

VERSION = 'numpy-small-cnn-v1'
TOLERANCE = 1e-5


class NumpyClassifier:
    def __init__(self, candidate, contract, path, fingerprint):
        validate_spec(candidate['spec'])
        if (candidate['spec']['objective'] != 'classification' or
                candidate['classes'] != contract['classes'] or
                set(contract['classes']) != {'human', 'threat'} or
                not contract.get('eligible') or contract.get('target') != 'ppal-semantics' or
                contract.get('input') != 'RGB-candidate-crop'):
            raise ValueError('validated semantic contract required; SELF labels prohibited')
        if sha(path) != fingerprint:
            raise ValueError('portable weights changed')
        self.candidate = candidate
        self.contract = contract
        expected = {}
        before = 3
        spec = candidate['spec']
        for i, channel in enumerate(spec['channels']):
            expected[f'0.{2*i}.weight'] = (channel, before, spec['kernel'], spec['kernel'])
            expected[f'0.{2*i}.bias'] = (channel,)
            before = channel
        expected.update({'3.weight': (2, before), '3.bias': (2,)})
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != set(expected):
                raise ValueError('portable tensor vocabulary changed')
            self.weights = {k: archive[k].copy() for k in expected}
        for key, shape in expected.items():
            value = self.weights[key]
            if value.dtype != np.float32 or value.shape != shape or not np.isfinite(value).all():
                raise ValueError('invalid portable tensor')

    def probabilities(self, image):
        spec = self.candidate['spec']
        x = np.array(image.convert('RGB').resize((spec['size'],)*2,
                     Image.Resampling.BILINEAR), dtype=np.float32).transpose(2, 0, 1) / 255.
        for i, _ in enumerate(spec['channels']):
            kernel = spec['kernel']
            x = np.pad(x, ((0, 0), (kernel//2, kernel//2), (kernel//2, kernel//2)))
            windows = np.lib.stride_tricks.sliding_window_view(x, (kernel, kernel), axis=(1, 2))[:, ::2, ::2]
            x = np.einsum('chwkl,ockl->ohw', windows, self.weights[f'0.{2*i}.weight'], optimize=False)
            x += self.weights[f'0.{2*i}.bias'][:, None, None]
            if spec['activation'] == 'relu':
                x = np.maximum(x, 0)
            else:
                # Match nn.GELU's default exact erf, not its tanh approximation.
                erf = np.frompyfunc(math.erf, 1, 1)(x / math.sqrt(2)).astype(np.float32)
                x = .5*x*(1+erf)
        logits = self.weights['3.weight'] @ x.mean((1, 2)) + self.weights['3.bias']
        if not np.isfinite(logits).all():raise ValueError('nonfinite portable inference')
        probabilities = np.exp(logits-logits.max())
        return probabilities / probabilities.sum()

    def infer(self, image):
        began = time.perf_counter()
        probabilities = self.probabilities(image)
        confidence = float(probabilities.max())
        # Numerical equivalence is finite. Abstain near admission/tie boundaries.
        accepted = (confidence >= self.contract['threshold'] + TOLERANCE and
                    abs(float(probabilities[0]-probabilities[1])) > 2*TOLERANCE)
        return dict(label=self.candidate['classes'][int(probabilities.argmax())] if accepted else None,
                    confidence=confidence, status='tentative_semantic_prediction' if accepted else 'UNKNOWN',
                    physical_identity='unaffected', candidate_id=self.candidate['identifier'],
                    seconds=time.perf_counter()-began, runtime=VERSION)


def export(manifest, output):
    """Frozen authorized model; parity uses generated probes, never held-out data."""
    from .cycle import gameplay_active
    from .operational import load_manifest
    from .foundry import checked_load
    from memory.evidence import EvidenceJournal
    if gameplay_active():
        raise RuntimeError('offline export unavailable during gameplay')
    manifest = Path(manifest)
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    active, reference = load_manifest(manifest)
    candidate = active['candidate']
    weights = checked_load(candidate['checkpoint'])['weights']
    path = root/'weights.npz'
    with path.open('xb') as stream:
        np.savez(stream, **{k: v.detach().cpu().numpy() for k, v in weights.items()})
        stream.flush(); os.fsync(stream.fileno())
    fingerprint = sha(path)
    model = NumpyClassifier(candidate, active['contract'], path, fingerprint)
    import torch
    errors = []
    rng = np.random.default_rng(0)
    for n in range(12):
        pixels = rng.integers(0, 256, (19+n, 23+n, 3), dtype=np.uint8)
        image = Image.fromarray(pixels)
        size = candidate['spec']['size']
        x = np.array(image.resize((size,)*2, Image.Resampling.BILINEAR), dtype=np.float32)/255.
        with torch.no_grad():
            expected = reference.model(torch.from_numpy(x.transpose(2, 0, 1)).unsqueeze(0)).softmax(1)[0].numpy()
        errors.append(float(np.max(np.abs(model.probabilities(image)-expected))))
    if not all(math.isfinite(e) for e in errors) or max(errors) > TOLERANCE:
        raise ValueError('portable runtime failed frozen-model parity')
    source = Path(active['journal'])
    if not source.is_absolute():
        source = manifest.resolve().parent/source
    journal = EvidenceJournal(source)
    try:
        # Record this transport implementation, not another independent test.
        from .deployment import CapabilityDeployment
        current = CapabilityDeployment(journal).active('ppal-semantics')
        if dict(current, journal=active['journal']) != active:
            raise ValueError('activation changed during export')
        activation = next(r for r in reversed(journal.records('event'))
                          if r.data['payload'].get('activation_key') == active['activation_key'])
        record = journal.append('event', dict(category='portable_semantic_artifact',
            runtime=VERSION, activation_key=active['activation_key'],
            checkpoint_sha256=candidate['checkpoint_sha256'], sha256=fingerprint,
            parity=dict(probes=12, max_probability_error=max(errors), tolerance=TOLERANCE,
                        evidence='generated transport probes; no generalization or readiness credit')),
            episode=activation.data['episode'], sources=[activation.id],
            producer='verified-semantic-transport', version=VERSION)
        destination = sqlite3.connect(root/'learning-evidence.sqlite3')
        try: journal.conn.backup(destination)
        finally: destination.close()
        payload = dict(active, journal='learning-evidence.sqlite3')
        runtime = dict(version=VERSION, path='weights.npz', sha256=fingerprint, evidence_id=record.id)
        atomic_json(root/'semantic-activation.json', dict(payload=payload, sha256=digest(payload), runtime=runtime))
    finally:
        journal.close()
    return root/'semantic-activation.json'


def load_runtime(value, journal, active, manifest):
    runtime = value['runtime']
    record = journal.get(runtime['evidence_id'])
    p = record.data['payload']
    if (runtime.get('version') != VERSION or record.data['producer'] != 'verified-semantic-transport' or
            p.get('category') != 'portable_semantic_artifact' or p.get('runtime') != VERSION or
            p.get('activation_key') != active['activation_key'] or
            p.get('checkpoint_sha256') != active['candidate']['checkpoint_sha256'] or
            p.get('sha256') != runtime.get('sha256') or
            p.get('parity', {}).get('tolerance') != TOLERANCE or
            not 0 <= p['parity'].get('max_probability_error', float('inf')) <= TOLERANCE):
        raise ValueError('verified portable activation linkage required')
    path = Path(runtime['path'])
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('portable weights must stay within bundle')
    return NumpyClassifier(active['candidate'], active['contract'], Path(manifest).parent/path, runtime['sha256'])


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(export(args.manifest, args.output))


if __name__ == '__main__':
    main()
