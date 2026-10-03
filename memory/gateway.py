"""Shared task-level memory API. Producers need not know MARM's wire format."""

import json
import os
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request

from .former import Experience
from .evaluator import MemoryEvaluator
from .marm import MarmClient, MarmOutbox, MarmWriteError


@dataclass(frozen=True)
class RecalledMemory:
    content: str
    id: str | None = None
    score: float | None = None
    evaluation_id: str | None = None


class MemoryGateway:
    def __init__(self, store=None, client=None,
                 project="charlie", session="charlie-experiences", evaluator=None):
        self.store = store if store is not None else MarmOutbox(project=project, session=session)
        self.client = client if client is not None else MarmClient(
            os.environ.get("CHARLIE_MARM_URL", "http://127.0.0.1:8001"), timeout=1)
        self.evaluator = evaluator if evaluator is not None else MemoryEvaluator()
        self.project, self.session = project, session

    def remember(self, experience: Experience) -> bool:
        assessment = self.evaluator.consider(experience)
        if assessment is None or not assessment.promote:
            return False
        self.store.save(assessment.candidate)
        if hasattr(self.store, "identity"):
            self.evaluator.link_remote(assessment.id, self.store.identity(assessment.candidate))
        self.evaluator.mark_promoted(assessment.id)
        return True

    def feedback(self, identifier, verdict, evidence_id, rationale, weight=1.0):
        changed = self.evaluator.feedback(identifier, verdict, evidence_id, rationale, weight)
        if changed:
            for assessment in self.evaluator.review_pending():
                self.store.save(assessment.candidate)
                if hasattr(self.store, "identity"):
                    self.evaluator.link_remote(assessment.id, self.store.identity(assessment.candidate))
                self.evaluator.mark_promoted(assessment.id)
        return changed

    def record_decision(self, decision_id, task, memory_ids):
        self.evaluator.record_decision(decision_id, task, memory_ids)

    def assess_decision(self, decision_id, verdict, evidence_id, comparison, weight=1.0):
        count = self.evaluator.assess_decision(decision_id, verdict, evidence_id, comparison, weight)
        if count:
            for assessment in self.evaluator.review_pending():
                self.store.save(assessment.candidate)
                if hasattr(self.store, "identity"):
                    self.evaluator.link_remote(assessment.id, self.store.identity(assessment.candidate))
                self.evaluator.mark_promoted(assessment.id)
        return count

    def correct(self, identifier, replacement, rationale, evidence_id):
        self.remember(Experience(kind="fact", summary=replacement, source="user:correction",
                                 subject="corrected memory", significant=True, confidence=1.0,
                                 evidence=evidence_id, tags=("correction",)))
        self.evaluator.correct(identifier, replacement, rationale)

    def recall(self, query: str, limit: int = 5) -> list[RecalledMemory]:
        """Bounded, project-scoped recall; MARM outage means no advice."""
        if not query.strip() or not 1 <= limit <= 20:
            raise ValueError("A query and limit from 1 to 20 are required")
        payload = {"query": query, "session_name": self.session,
                   "project": self.project, "limit": limit, "detail": 3}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.client.api_key:
            headers["Authorization"] = "Bearer " + self.client.api_key
        request = Request(self.client.url.replace("/marm_log_entry", "/marm_smart_recall"),
                          data=json.dumps(payload).encode(), headers=headers, method="POST")
        try:
            with self.client.opener.open(request, timeout=self.client.timeout) as response:
                data = json.load(response)
        except HTTPError as error:
            raise MarmWriteError(f"MARM recall returned HTTP {error.code}") from None
        except (URLError, OSError, ValueError) as error:
            raise MarmWriteError(f"MARM recall failed ({type(error).__name__})") from None
        if not isinstance(data, dict) or data.get("status") not in ("success", "no_results"):
            raise MarmWriteError("MARM recall returned an invalid result")
        results = data.get("results", [])
        if not isinstance(results, list):
            raise MarmWriteError("MARM recall results were malformed")
        recalled = []
        for item in results[:limit]:
            if not isinstance(item, dict) or not isinstance(item.get("content"), str):
                continue
            match = re.search(r"Charlie memory ([0-9a-f]{64})", item["content"])
            local = self.evaluator.resolve_remote(match.group(1)) if match else None
            if local and local[1] != "promoted":
                continue
            recalled.append(RecalledMemory(content=item["content"], id=item.get("id"),
                                            score=item.get("similarity"),
                                            evaluation_id=local[0] if local else None))
        return recalled
