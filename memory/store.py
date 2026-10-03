"""Storage boundary for Charlie's selected memories."""

import json
from pathlib import Path
from typing import Protocol

from .former import CandidateMemory


class MemoryStore(Protocol):
    def save(self, memory: CandidateMemory) -> None: ...


class JsonlStore:
    """Local durable staging store; one selected memory per line."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, memory: CandidateMemory) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(memory.to_dict(), ensure_ascii=False) + "\n")
