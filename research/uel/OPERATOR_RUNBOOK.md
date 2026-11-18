# Operator runbook

Run from the Charlie research checkout root with Python 3.12.

```sh
REV=$(git rev-parse HEAD)
python -m research.uel /tmp/uel.sqlite --session demo --revision "$REV" --trials 10
python -m research.uel /tmp/uel.sqlite --session demo --revision "$REV" --export
OPENBLAS_NUM_THREADS=1 python -m research.uel.benchmark
OPENBLAS_NUM_THREADS=1 python -m pytest -q research/uel
```

For another simulated system, construct a Profile with its ordered channels and implement reset, step and stop as in synthetic.py. Pass that adapter to Journal and Session in a research-only driver. Establish the neutral baseline and collect repeated opposing probes. Fit Model to command and response matrices. Challenge with disjoint seeds or amplitudes and use inquiry.investigate to record competing predictions and evidence references. To replay stored camera trials, call camera.replay with the SQLite path and session ID. Use a fresh database or session ID for a new run. For candidate export, see CAMERA_DEMONSTRATION.md.

For the camera example, the renamed amber channel produces a negative horizontal response. Opposite-sign probes and held-out closed-loop centering challenge that interpretation. Occlusion produces missing telemetry and stops the session. Neither replay nor the digital twin can establish wiring, power integrity or mechanical clearance.
