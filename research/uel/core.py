"""Offline simulation boundary and transactional trial journal."""

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import sqlite3
import time
from typing import Protocol


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class Channel:
    name: str
    unit: str
    low: float
    high: float

    def __post_init__(self):
        if not self.name or not self.unit or not all(map(math.isfinite, (self.low, self.high))):
            raise ValueError("invalid channel")
        if self.low >= self.high:
            raise ValueError("invalid channel bounds")

    def check(self, value):
        if type(value) not in (float, int) or not self.low <= value <= self.high:
            raise ValueError(f"invalid value for {self.name}")


@dataclass(frozen=True)
class Profile:
    name: str
    revision: str
    actuators: tuple[Channel, ...]
    sensors: tuple[Channel, ...]
    neutral: tuple[float, ...]
    source: str = "bundled simulation"
    version: int = 1
    transport: str = "simulation"
    max_duration: float = 0.25
    stale_after: float = 1.0

    def __post_init__(self):
        if self.transport != "simulation":
            raise PermissionError("DENIED_PHYSICAL_AUTHORITY")
        if self.version != 1 or not all((self.name, self.revision, self.source)):
            raise ValueError("invalid profile identity")
        for channels in (self.actuators, self.sensors):
            if not channels or len({c.name for c in channels}) != len(channels):
                raise ValueError("empty or duplicate channels")
        for limit in (self.max_duration, self.stale_after):
            if not math.isfinite(limit) or limit <= 0:
                raise ValueError("invalid timing limit")
        self.command(self.neutral, self.max_duration)

    def command(self, values, duration):
        if type(duration) not in (int, float) or not 0 < duration <= self.max_duration:
            raise ValueError("invalid duration")
        if len(values) != len(self.actuators):
            raise ValueError("invalid action length")
        for channel, value in zip(self.actuators, values, strict=True):
            channel.check(value)


@dataclass(frozen=True)
class Observation:
    values: tuple[float, ...]
    timestamp: float


class Simulator(Protocol):
    profile: Profile

    def reset(self, seed: int) -> Observation: ...
    def step(self, action: tuple[float, ...], duration: float) -> Observation: ...
    def stop(self, reason: str) -> None: ...


class Journal:
    def __init__(self, path, session, profile, revision, quota_bytes=250_000_000):
        self.db = sqlite3.connect(path)
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.db.close()
            raise ValueError("unsupported journal schema")
        page_size = self.db.execute("PRAGMA page_size").fetchone()[0]
        self.db.execute(f"PRAGMA max_page_count={max(1, quota_bytes // page_size)}")
        self.session = session
        identity = encode({"profile": asdict(profile), "software": revision})
        with self.db:
            self.db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, identity TEXT)")
            self.db.execute("""CREATE TABLE IF NOT EXISTS events (
                session TEXT, trial INTEGER, phase TEXT, payload TEXT, digest TEXT,
                PRIMARY KEY (session, trial, phase))""")
            self.db.execute("PRAGMA user_version=1")
            self.db.execute("INSERT OR IGNORE INTO sessions VALUES (?, ?)", (session, identity))
            saved = self.db.execute("SELECT identity FROM sessions WHERE id=?", (session,)).fetchone()[0]
            if identity != saved:
                raise ValueError("session provenance mismatch")

    def append(self, trial, phase, value):
        payload = encode(value)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        with self.db:
            self.db.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?)",
                            (self.session, trial, phase, payload, digest))

    def read(self):
        for trial, phase, payload, digest in self.db.execute(
            "SELECT trial, phase, payload, digest FROM events WHERE session=? ORDER BY rowid",
            (self.session,),
        ):
            if hashlib.sha256(payload.encode()).hexdigest() != digest:
                raise ValueError("corrupt trial evidence")
            yield trial, phase, json.loads(payload)


class Session:
    def __init__(self, simulator: Simulator, journal: Journal, *, trials: int, seconds: float):
        if type(trials) is not int or trials <= 0 or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("invalid session budget")
        if simulator.profile.transport != "simulation":
            raise PermissionError("DENIED_PHYSICAL_AUTHORITY")
        self.simulator = simulator
        self.journal = journal
        self.limit = trials
        self.deadline = time.monotonic() + seconds
        self.closed = False
        started = set()
        finished = set()
        for trial, phase, _ in journal.read():
            if phase == "planned":
                started.add(trial)
            elif phase in ("result", "interrupted"):
                finished.add(trial)
            elif phase == "stopped":
                self.closed = True
        self.next_trial = max(started, default=-1) + 1
        if started - finished:
            simulator.stop("interrupted")
            for trial in sorted(started - finished):
                journal.append(trial, "interrupted", {})
            self.cancel("interrupted session")

    def cancel(self, reason="operator cancellation"):
        if not self.closed:
            self.closed = True
            try:
                self.simulator.stop(reason)
            finally:
                self.journal.append(-1, "stopped", {"reason": reason})

    def check_lease(self):
        if self.closed or time.monotonic() >= self.deadline:
            self.cancel("lease ended")
            raise PermissionError("session closed")

    def check_observation(self, observation):
        profile = self.simulator.profile
        age = time.monotonic() - observation.timestamp
        if not 0 <= age <= profile.stale_after or len(observation.values) != len(profile.sensors):
            raise ValueError("stale or incomplete observation")
        for channel, value in zip(profile.sensors, observation.values, strict=True):
            channel.check(value)

    def run(self, action, duration, seed):
        self.check_lease()
        if self.next_trial >= self.limit:
            self.cancel("trial budget exhausted")
            raise PermissionError("trial budget exhausted")
        self.simulator.profile.command(action, duration)
        trial = self.next_trial
        self.next_trial += 1
        try:
            self.journal.append(trial, "planned", {"action": action, "duration": duration, "seed": seed})
            before = self.simulator.reset(seed)
            self.check_observation(before)
            self.check_lease()
            after = self.simulator.step(tuple(action), duration)
            self.check_lease()
            self.check_observation(after)
            self.journal.append(trial, "result", {"before": asdict(before), "after": asdict(after)})
            return before, after
        except BaseException:
            self.cancel("trial failed")
            raise
