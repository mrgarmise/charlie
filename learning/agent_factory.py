"""Opt-in, development-only organization execution for LearningExecutive.

Proposals name registered algorithms. They carry no executable objects, paths,
or tool grants. The registry is supplied by trusted development code.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
import sqlite3
from time import time


_lease_check = ContextVar("sandbox_lease_check", default=lambda: True)


def check_worker_lease():
    if not _lease_check.get()():
        raise InterruptedError("sandbox worker lease ended")


def encode(value):
    payload = json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))
    if len(payload.encode()) > 65_536:
        raise ValueError("organization record exceeds size limit")
    return payload


def identifier(value):
    if type(value) is not str or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value):
        raise ValueError("invalid organization identifier")
    return value


@dataclass(frozen=True)
class Assignment:
    name: str
    capability: str
    depends_on: tuple[str, ...] = ()
    supervisor: str | None = None


def parse_assignments(data):
    """Convert a size-bounded JSON proposal into inert assignment records."""
    if type(data) is not str or len(data.encode()) > 65_536:
        raise ValueError("invalid proposal size")
    def unique_fields(pairs):
        obj = {}
        for name, value in pairs:
            if name in obj:
                raise ValueError("duplicate proposal field")
            obj[name] = value
        return obj

    try:
        proposal = json.loads(data, object_pairs_hook=unique_fields)
    except RecursionError as exc:
        raise ValueError("proposal nesting exceeds parser limit") from exc
    if type(proposal) is not dict or set(proposal) != {"schema", "assignments"}:
        raise ValueError("unknown proposal fields")
    if type(proposal["schema"]) is not int or proposal["schema"] != 1:
        raise ValueError("unsupported organization proposal schema")
    rows = proposal["assignments"]
    if type(rows) is not list or not 1 <= len(rows) <= 12:
        raise ValueError("organization requires 1–12 assignments")
    assignments = []
    for row in rows:
        if (type(row) is not dict or not {"name", "capability"} <= row.keys()
                or row.keys() - {"name", "capability", "depends_on", "supervisor"}):
            raise ValueError("unknown or missing assignment fields")
        dependencies = row.get("depends_on", [])
        supervisor = row.get("supervisor")
        if type(dependencies) is not list or len(dependencies) > 11:
            raise ValueError("invalid dependencies")
        assignments.append(Assignment(identifier(row["name"]), identifier(row["capability"]),
                                      tuple(map(identifier, dependencies)),
                                      identifier(supervisor) if supervisor is not None else None))
    return tuple(assignments)


@dataclass(frozen=True)
class Capability:
    name: str
    version: str
    role: str
    run: object
    children: tuple[str, ...] = ()
    work_units: int = 1


class Factory:
    """Durable sandbox task ledger with precharged, fenced attempts."""

    def __init__(self, path, capabilities, *, clock=time):
        self.path = path
        self.clock = clock
        self.capabilities = {}
        for capability in capabilities:
            name = identifier(capability.name)
            identifier(capability.version)
            if (name in self.capabilities or capability.role not in {"supervisor", "worker", "evaluator"}
                    or not callable(capability.run)
                    or type(capability.work_units) is not int or not 1 <= capability.work_units <= 512):
                raise ValueError("invalid capability registration")
            self.capabilities[name] = capability
        for capability in self.capabilities.values():
            if (capability.children and capability.role != "supervisor"
                    or any(child not in self.capabilities for child in capability.children)):
                raise ValueError("invalid supervisor delegation allowlist")
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sandbox_organization (
                    id TEXT PRIMARY KEY, specification TEXT NOT NULL,
                    deadline REAL NOT NULL, state TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sandbox_assignment (
                    mission TEXT NOT NULL, name TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0, lease REAL,
                    evidence TEXT, PRIMARY KEY (mission, name)
                );
                CREATE TABLE IF NOT EXISTS sandbox_factory_control (
                    id INTEGER PRIMARY KEY CHECK (id = 1), stopped INTEGER NOT NULL
                );
                INSERT OR IGNORE INTO sandbox_factory_control VALUES (1, 0);
                CREATE TABLE IF NOT EXISTS sandbox_event (
                    sequence INTEGER PRIMARY KEY, mission TEXT NOT NULL,
                    kind TEXT NOT NULL, task TEXT, attempt INTEGER, state TEXT,
                    evidence_digest TEXT, recorded_at REAL DEFAULT ((julianday('now') - 2440587.5) * 86400)
                );
                CREATE TRIGGER IF NOT EXISTS sandbox_commission_event
                AFTER INSERT ON sandbox_organization BEGIN
                    INSERT INTO sandbox_event(mission,kind,state) VALUES(new.id,'mission',new.state);
                END;
                CREATE TRIGGER IF NOT EXISTS sandbox_state_event
                AFTER UPDATE OF state ON sandbox_organization WHEN old.state<>new.state BEGIN
                    INSERT INTO sandbox_event(mission,kind,state) VALUES(new.id,'mission',new.state);
                END;
                CREATE TRIGGER IF NOT EXISTS sandbox_assignment_event
                AFTER INSERT ON sandbox_assignment BEGIN
                    INSERT INTO sandbox_event(mission,kind,task) VALUES(new.mission,'assignment',new.name);
                END;
                CREATE TRIGGER IF NOT EXISTS sandbox_attempt_event
                AFTER UPDATE OF attempts,lease,evidence ON sandbox_assignment BEGIN
                    INSERT INTO sandbox_event(mission,kind,task,attempt,evidence_digest)
                    VALUES(new.mission,CASE WHEN new.attempts<>old.attempts THEN 'claim'
                        WHEN new.evidence IS NULL THEN 'attempt-failed' ELSE 'result' END,
                        new.name,new.attempts,json_extract(new.evidence,'$.digest'));
                END;
            """)

            db.execute("BEGIN IMMEDIATE")
            if "revoked" not in {row[1] for row in db.execute("PRAGMA table_info(sandbox_assignment)")}:
                db.execute("ALTER TABLE sandbox_assignment ADD COLUMN revoked INTEGER NOT NULL DEFAULT 0")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def validate(self, assignments):
        if not 1 <= len(assignments) <= 12:
            raise ValueError("organization requires 1–12 assignments")
        by_name = {identifier(node.name): node for node in assignments}
        if len(by_name) != len(assignments):
            raise ValueError("duplicate assignment")
        for node in assignments:
            if identifier(node.capability) not in self.capabilities:
                raise ValueError("unavailable capability")
            if (type(node.depends_on) is not tuple or len(node.depends_on) > 11
                    or any(identifier(dep) not in by_name for dep in node.depends_on)):
                raise ValueError("invalid dependencies")
            parent, seen = node.supervisor, {node.name}
            while parent is not None:
                identifier(parent)
                if parent in seen or len(seen) > 3:
                    raise ValueError("supervisor cycle or depth exceeded")
                supervisor = by_name.get(identifier(parent))
                if (supervisor is None or supervisor.capability not in self.capabilities
                        or self.capabilities[supervisor.capability].role != "supervisor"):
                    raise ValueError("unknown supervisor")
                seen.add(parent)
                parent = supervisor.supervisor
        ordered = []
        done = set()
        while len(ordered) < len(assignments):
            ready = [node for node in assignments
                     if node.name not in done and done.issuperset(node.depends_on)]
            if not ready:
                raise ValueError("cyclic assignment dependencies")
            ordered.extend(ready)
            done.update(node.name for node in ready)
        return ordered

    def rank(self, context, templates, *, frozen=False):
        """Rank validated alternatives using completed, independently scored runs."""
        identifier(context)
        with self.connect() as db:
            rows = [] if frozen else db.execute("""
                SELECT specification, evidence FROM sandbox_organization
                JOIN sandbox_assignment ON sandbox_assignment.mission=sandbox_organization.id
                WHERE state='completed' AND evidence IS NOT NULL
            """).fetchall()
        ranked = []
        for template, assignments in templates.items():
            identifier(template)
            ordered = self.validate(assignments)
            nodes = self.describe(ordered)
            evaluators = {node.name for node in ordered
                          if self.capabilities[node.capability].role == "evaluator"}
            if len(evaluators) != 1:
                raise ValueError("template requires one evaluator")
            samples = {}
            for spec, evidence in rows:
                plan = json.loads(spec)
                item = json.loads(evidence)
                payload = item["payload"]
                if (plan.get("context") != context or plan.get("template") != template
                        or plan.get("initial_nodes", plan.get("nodes")) != nodes or payload["task"] not in evaluators
                        or item["digest"] != sha256(encode(payload).encode()).hexdigest()):
                    continue
                result = payload["result"]
                score = result.get("organization_score")
                case = result.get("evaluation_case")
                if (type(score) in {int, float} and 0 <= score <= 1
                        and type(case) is str and case):
                    # Replaying identical controlled evidence contributes one sample.
                    samples.setdefault(case, []).append(score)
            means = [sum(scores) / len(scores) for scores in samples.values()]
            # Two neutral prior observations limit the impact of the first result.
            value = (1 + sum(means)) / (2 + len(means))
            ranked.append(dict(template=template, value=value, samples=len(means),
                               workers=len(ordered)))
        return sorted(ranked, key=lambda item: (-item["value"], item["workers"], item["template"]))

    def describe(self, nodes):
        result = []
        for node in nodes:
            capability = self.capabilities[node.capability]
            row = dict(asdict(node), depends_on=list(node.depends_on), version=capability.version)
            if capability.work_units != 1:
                row["work_units"] = capability.work_units
            result.append(row)
        return result

    def commission(self, mission, goal, assignments, *, seconds=120, context=None, template=None, decision=None, work_budget=None):
        identifier(mission)
        if type(goal) is not str or not goal.strip() or len(goal) > 1000:
            raise ValueError("invalid goal")
        if type(seconds) is not int or not 1 <= seconds <= 3600:
            raise ValueError("invalid deadline")
        nodes = self.validate(assignments)
        if context is not None or template is not None:
            identifier(context)
            identifier(template)
        plan = dict(schema=1, goal=goal, seconds=seconds, nodes=self.describe(nodes))
        if work_budget is not None:
            if type(work_budget) is not int or not 1 <= work_budget <= 4096:
                raise ValueError("invalid work budget")
            plan["work_budget"] = work_budget
        if context is not None:
            plan.update(context=context, template=template, decision=decision)
        specification = encode(plan)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.expire(db)
            existing = db.execute("SELECT specification FROM sandbox_organization WHERE id=?", (mission,)).fetchone()
            if existing:
                previous = json.loads(existing[0])
                previous["nodes"] = previous.pop("initial_nodes", previous["nodes"])
                if encode(previous) != specification:
                    raise ValueError("mission identity already bound to another specification")
                return mission
            active = db.execute("SELECT count(*) FROM sandbox_organization WHERE state IN ('queued','running','paused')").fetchone()[0]
            if self.stopped(db) or active >= 2:
                raise RuntimeError("factory stopped or mission capacity exhausted")
            db.execute("INSERT INTO sandbox_organization VALUES (?,?,?,'queued')",
                       (mission, specification, self.clock() + seconds))
            db.executemany("INSERT INTO sandbox_assignment(mission,name) VALUES (?,?)",
                           [(mission, node.name) for node in nodes])
        return mission

    def stopped(self, db):
        return db.execute("SELECT stopped FROM sandbox_factory_control WHERE id=1").fetchone()[0]

    def expire(self, db):
        db.execute("UPDATE sandbox_organization SET state='expired' WHERE deadline<=? AND state IN ('queued','running','paused')",
                   (self.clock(),))

    def cancel(self, mission):
        with self.connect() as db:
            db.execute("UPDATE sandbox_organization SET state='cancelled' WHERE id=? AND state IN ('queued','running','paused')",
                       (mission,))

    def pause(self, mission):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            transitioned = db.execute(
                "UPDATE sandbox_organization SET state='paused' WHERE id=? AND state IN ('queued','running')",
                (mission,)).rowcount
            if transitioned:
                db.execute("UPDATE sandbox_assignment SET revoked=1 WHERE mission=? AND lease IS NOT NULL",
                           (mission,))

    def resume(self, mission):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.expire(db)
            if not self.stopped(db):
                db.execute("UPDATE sandbox_organization SET state='queued' WHERE id=? AND state='paused'",
                           (mission,))

    def stop(self):
        with self.connect() as db:
            db.execute("UPDATE sandbox_factory_control SET stopped=1 WHERE id=1")
            db.execute("UPDATE sandbox_organization SET state='cancelled' WHERE state IN ('queued','running','paused')")

    def inspect(self, mission):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.expire(db)
            record = db.execute("SELECT specification,state,deadline FROM sandbox_organization WHERE id=?",
                                (mission,)).fetchone()
            if record is None:
                raise KeyError(mission)
            tasks = db.execute("SELECT name,attempts,evidence FROM sandbox_assignment WHERE mission=? ORDER BY name",
                               (mission,)).fetchall()
        specification, state, deadline = record
        plan = json.loads(specification)
        costs = {node["name"]: node.get("work_units", 1) for node in plan["nodes"]}
        return dict(plan, state=state, deadline=deadline,
                    consumed_work_units=sum(count * costs[name] for name, count, _ in tasks),
                    tasks={name: dict(attempts=count, evidence=json.loads(evidence) if evidence else None)
                           for name, count, evidence in tasks})

    def claim(self, mission):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.expire(db)
            record = db.execute("SELECT specification,state,deadline FROM sandbox_organization WHERE id=?",
                                (mission,)).fetchone()
            if record is None:
                raise KeyError(mission)
            specification, state, deadline = record
            if self.stopped(db) or state not in {"queued", "running"}:
                return None
            now = self.clock()
            running = db.execute("SELECT count(*) FROM sandbox_assignment WHERE lease>?", (now,)).fetchone()[0]
            if running >= 2:
                return None
            rows = db.execute("SELECT name,attempts,lease,evidence FROM sandbox_assignment WHERE mission=?",
                              (mission,)).fetchall()
            tasks = {name: (attempts, lease, evidence) for name, attempts, lease, evidence in rows}
            plan = json.loads(specification)
            consumed = sum(tasks[node["name"]][0] * node.get("work_units", 1) for node in plan["nodes"])
            for node in plan["nodes"]:
                name = node["name"]
                attempts, lease, evidence = tasks[name]
                if evidence or (lease is not None and lease > now):
                    continue
                capability = self.capabilities.get(node["capability"])
                if attempts >= 3 or capability is None or capability.version != node["version"]:
                    db.execute("UPDATE sandbox_organization SET state='failed' WHERE id=?", (mission,))
                    return None
                inputs = {dep: tasks[dep][2] for dep in node["depends_on"]}
                if not all(inputs.values()):
                    continue
                if consumed + node.get("work_units", 1) > plan.get("work_budget", 4096):
                    db.execute("UPDATE sandbox_organization SET state='failed' WHERE id=?", (mission,))
                    db.execute("INSERT INTO sandbox_event(mission,kind,task) VALUES(?,'budget-exhausted',?)",
                               (mission, name))
                    return None
                db.execute("UPDATE sandbox_assignment SET attempts=?,lease=?,revoked=0 WHERE mission=? AND name=?",
                           (attempts + 1, min(deadline, now + 30), mission, name))
                db.execute("UPDATE sandbox_organization SET state='running' WHERE id=?", (mission,))
                return capability, name, attempts + 1, plan["goal"], {k: json.loads(v) for k, v in inputs.items()}
            return None

    def lease_is_active(self, mission, name, attempt):
        with self.connect() as db:
            return db.execute("""
                SELECT 1 FROM sandbox_assignment AS task
                JOIN sandbox_organization AS org ON org.id=task.mission
                WHERE org.id=? AND task.name=? AND task.attempts=? AND task.lease>?
                    AND task.revoked=0 AND org.state='running' AND org.deadline>?
            """, (mission, name, attempt, self.clock(), self.clock())).fetchone() is not None

    def step(self, mission):
        """Run one registered synchronous development algorithm, if ready."""
        claim = self.claim(mission)
        if claim is None:
            return False
        capability, name, attempt, goal, inputs = claim
        token = _lease_check.set(lambda: self.lease_is_active(mission, name, attempt))
        try:
            result = capability.run(goal, inputs)
            if type(result) is not dict:
                raise ValueError("worker result must be an object")
            payload = encode(dict(
                mission=mission, task=name, attempt=attempt, mode="simulation_or_synthetic",
                capability=capability.name, version=capability.version,
                inputs={dep: item["digest"] for dep, item in inputs.items()}, result=result))
            evidence = encode(dict(payload=json.loads(payload), digest=sha256(payload.encode()).hexdigest()))
        except Exception:
            self._finish(mission, name, attempt, None)
            raise
        finally:
            _lease_check.reset(token)
        try:
            self._finish(mission, name, attempt, evidence, result.get("organization_proposal"),
                         allowlist=capability.children)
        except ValueError:
            self._finish(mission, name, attempt, None)
            raise
        return True

    def events(self, mission, *, after=0):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT * FROM sandbox_event WHERE mission=? AND sequence>? ORDER BY sequence LIMIT 64",
                (mission, after)).fetchall()
        return [dict(row) for row in rows]

    def _expand(self, db, mission, parent, proposal, allowlist):
        children = parse_assignments(proposal)
        if any(child.supervisor is not None or child.capability not in allowlist
               for child in children):
            raise ValueError("delegation exceeds the parent capability allowlist")
        spec = json.loads(db.execute("SELECT specification FROM sandbox_organization WHERE id=?",
                                     (mission,)).fetchone()[0])
        nodes = spec["nodes"]
        spec.setdefault("initial_nodes", list(nodes))
        existing = [Assignment(n["name"], n["capability"], tuple(n["depends_on"]),
                               n["supervisor"]) for n in nodes]
        delegated = [Assignment(n.name, n.capability, tuple(dict.fromkeys((parent, *n.depends_on))),
                                parent) for n in children]
        # A child can see its parent and siblings in its own proposal only.
        local = {parent, *(n.name for n in children)}
        if any(not local.issuperset(n.depends_on) for n in delegated):
            raise ValueError("delegated dependencies exceed the parent scope")
        if any(n["capability"] not in self.capabilities
               or self.capabilities[n["capability"]].version != n["version"] for n in nodes):
            raise ValueError("registered capability version changed during delegation")
        ordered = self.validate(existing + delegated)
        spec["nodes"] = self.describe(ordered)
        db.execute("UPDATE sandbox_organization SET specification=? WHERE id=?", (encode(spec), mission))
        db.executemany("INSERT INTO sandbox_assignment(mission,name) VALUES (?,?)",
                       [(mission, node.name) for node in delegated])

    def _finish(self, mission, name, attempt, evidence, proposal=None, *, allowlist=()):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.expire(db)
            db.execute("""UPDATE sandbox_assignment SET lease=NULL
                WHERE mission=? AND name=? AND attempts=? AND revoked=1 AND lease IS NOT NULL""",
                       (mission, name, attempt))
            changed = db.execute("""UPDATE sandbox_assignment SET lease=NULL,evidence=?
                WHERE mission=? AND name=? AND attempts=? AND lease>? AND revoked=0
                AND EXISTS (SELECT 1 FROM sandbox_organization WHERE id=? AND state='running')""",
                       (evidence, mission, name, attempt, self.clock(), mission)).rowcount
            if changed and proposal is not None:
                self._expand(db, mission, name, proposal, allowlist)
            db.execute("""UPDATE sandbox_organization SET state='completed'
                WHERE id=? AND state='running' AND NOT EXISTS
                (SELECT 1 FROM sandbox_assignment WHERE mission=? AND evidence IS NULL)""",
                       (mission, mission))
