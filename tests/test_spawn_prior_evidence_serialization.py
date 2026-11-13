from experiments.ppal.robotron_agency import VisualAgency
from experiments.ppal.eyes.detectors import Detection
from memory.evidence import EvidenceJournal, digest


def test_spawn_prior_survives_durable_evidence_commit(tmp_path):
    agency = VisualAgency()
    pairs = []

    for i in range(12):
        x = 10 + (i % 4) * 20
        y = 10 + (i // 4) * 25
        detection = Detection(
            "unknown",
            (float(x), float(y)),
            (x * 4, y * 4, x * 4 + 5, y * 4 + 5),
            25,
        )
        pairs.append((detection, {}))

    snapshot = agency.observe(pairs, observed_at=1.0)
    weights = snapshot["spawn_prior"]["weights"]

    assert len(weights) == 12
    assert all(isinstance(key, str) for key in weights)

    prepared = EvidenceJournal.prepare_observation(
        {"agency": snapshot},
        episode="spawn-prior-regression",
        at=1.0,
        producer="test",
        version="1",
    )

    assert prepared.id == digest(prepared.data)

    journal = EvidenceJournal(tmp_path / "test-evidence.sqlite3")
    try:
        committed = journal.commit_prepared(prepared)
        assert committed.id == prepared.id
        assert committed.data["payload"]["agency"] == snapshot
    finally:
        journal.close()
