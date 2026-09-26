"""Shared task-level memory API. Producers need not know MARM's wire format."""

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request

from .former import Experience, MemoryFormer
from .marm import MarmClient, MarmOutbox, MarmWriteError


@dataclass(frozen=True)
class RecalledMemory:
    content: str
    id: str | None = None
    score: float | None = None


class MemoryGateway:
    def __init__(self, store=None, client=None, former=None,
                 project="charlie", session="charlie-experiences"):
        self.store = store if store is not None else MarmOutbox(project=project, session=session)
        self.client = client if client is not None else MarmClient(
            os.environ.get("CHARLIE_MARM_URL", "http://127.0.0.1:8001"), timeout=1)
        self.former = former if former is not None else MemoryFormer()
        self.project, self.session = project, session

    def remember(self, experience: Experience) -> bool:
        candidate = self.former.consider(experience)
        if candidate is None:
            return False
        self.store.save(candidate)
        return True

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
        return [RecalledMemory(content=item["content"], id=item.get("id"),
                               score=item.get("similarity"))
                for item in results[:limit] if isinstance(item, dict) and isinstance(item.get("content"), str)]
