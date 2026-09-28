import json

from memory.evaluator import MemoryEvaluator
from memory.gateway import MemoryGateway
from memory.store import JsonlStore
from experiments.ppal.reflect_robotron import analyze, reflect


def test_analyze_flags_inactivity():
    summary = {
        "frames": 10, "decision_frames": 8, "self_unknown_frames": 2,
        "self_reacquisitions": 1,
        "actions": [{"move": "STAY", "fire": "NONE", "count": 6}],
    }
    rows = [{"status": "decision", "targets": [], "threats": []} for _ in range(8)]
    obs, findings = analyze(summary, rows, [])
    assert obs["stay_none_pct_of_decisions"] == 75.0
    assert "inaction" in {kind for kind, _ in findings}


def test_reflection_uses_existing_memory_gateway(tmp_path):
    replay = tmp_path / "replay"
    replay.mkdir()
    (replay / "summary.json").write_text(json.dumps({
        "recording": "robotron-runs/example",
        "frames": 10, "decision_frames": 8, "self_unknown_frames": 2,
        "self_reacquisitions": 3,
        "actions": [{"move": "STAY", "fire": "NONE", "count": 6}],
    }))
    (replay / "replay.json").write_text(json.dumps([
        {"status": "decision", "targets": [], "threats": []} for _ in range(8)
    ]))
    (replay / "tracks.json").write_text(json.dumps({"tracks": []}))

    evaluator = MemoryEvaluator(path=tmp_path / "eval.sqlite3", exploration_rate=0)
    gateway = MemoryGateway(
        store=JsonlStore(tmp_path / "memories.jsonl"),
        client=type("Offline", (), {
            "url": "http://127.0.0.1:1/marm_log_entry",
            "api_key": None, "timeout": 0.01, "opener": None
        })(),
        evaluator=evaluator,
    )
    # Avoid network in unit test while retaining the real gateway/evaluator.
    import experiments.ppal.reflect_robotron as module
    old = module._prior_remote
    module._prior_remote = lambda gateway, query: []
    try:
        result = reflect(replay, gateway=gateway, questions_path=tmp_path / "questions.jsonl")
    finally:
        module._prior_remote = old

    assert result["observations"]["stay_none_pct_of_decisions"] == 75.0
    assert (replay / "reflection.json").exists()
    assert (tmp_path / "questions.jsonl").exists()
    assert evaluator.recent()


def test_unreliable_replay_defers_strategy_question(tmp_path):
    replay = tmp_path / "replay"
    replay.mkdir()
    (replay / "summary.json").write_text(json.dumps({
        "recording": "robotron-runs/noisy",
        "frames": 10, "decision_frames": 8, "self_unknown_frames": 2,
        "self_reacquisitions": 4,
        "actions": [{"move": "STAY", "fire": "NONE", "count": 7}],
    }))
    (replay / "replay.json").write_text(json.dumps([
        {"status": "decision", "targets": [], "threats": [{"id": "threat_1"}]}
        for _ in range(8)
    ]))
    (replay / "tracks.json").write_text(json.dumps({
        "tracks": [{"track_id": i} for i in range(40)]
    }))

    evaluator = MemoryEvaluator(path=tmp_path / "eval.sqlite3", exploration_rate=0)
    gateway = MemoryGateway(
        store=JsonlStore(tmp_path / "memories.jsonl"),
        client=type("Offline", (), {
            "url": "http://127.0.0.1:1/marm_log_entry",
            "api_key": None, "timeout": 0.01, "opener": None
        })(),
        evaluator=evaluator,
    )
    import experiments.ppal.reflect_robotron as module
    old = module._prior_remote
    module._prior_remote = lambda gateway, query: []
    try:
        result = reflect(replay, gateway=gateway,
                         questions_path=tmp_path / "questions.jsonl")
    finally:
        module._prior_remote = old

    assert result["observations"]["replay_reliable_for_strategy"] is False
    assert "visual tracking is highly fragmented" in result["observations"]["reliability_reasons"]
    assert not any(q["category"] == "strategy" for q in result["questions"])
