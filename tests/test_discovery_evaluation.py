from pathlib import Path
import json
import subprocess
import sys

from tools.discovery_evaluation import score


class EmptyArchive:
    def get(self, key):
        return None


def test_scoring_rejects_an_unresolvable_empirical_claim():
    record = dict(citations=["invented"], status="supported_empirical", checks=[])
    metrics = score(record, EmptyArchive(), "B3-01", ("light",))
    assert metrics["unsupported_definitive_status"]
    assert metrics["citations_resolved"] == 0


def test_scoring_rejects_formal_grade_without_independent_check():
    metrics = score(dict(citations=[], status="verified_formal", checks=[]), EmptyArchive(), "formal", ())
    assert metrics["unsupported_definitive_status"]


def test_bounded_offline_worker_with_real_kernel_isolation(tmp_path):
    output = tmp_path / "receipt.json"
    cmd = [sys.executable, "-m", "tools.discovery_evaluation", "--output", str(output)]
    subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1], check=True, timeout=45)
    receipt = json.loads(output.read_text())
    assert receipt["synthetic"] is True
    assert receipt["structural_checks_passed"]
    cases = {case["question_id"]: case for case in receipt["cases"]}
    assert set(cases) == {"B3-01", "B3-02", "T1-03", "T2-05", "EVAL-CONFLICT", "EVAL-MISSING", "EVAL-FORMAL"}
    assert cases["EVAL-CONFLICT"]["status"] == "contradicted"
    assert cases["EVAL-FORMAL"]["status"] == "verified_formal"
    assert "2000 g" in cases["EVAL-FORMAL"]["checks"][0]["detail"]
    assert cases["EVAL-MISSING"]["metrics"]["abstained"]
    assert all(case["digest_text"] and case["deterministic"] for case in cases.values())
    assert cases["B3-01"]["metrics"]["citations_resolved"] >= 1
    assert cases["T1-03"]["metrics"]["citations_resolved"] >= 1
    assert receipt["resources"]["cpu_seconds"] > 0
