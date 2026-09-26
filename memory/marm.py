"""Durable outbox and HTTP writer for MARM's public log-entry API.

Capture is local. Run the sync command separately from a control loop.
Delivery is at-least-once: an ambiguous network failure can leave a remote
entry written without a local receipt. The stable Charlie ID aids reconciliation.
"""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .former import CandidateMemory

DEFAULT_OUTBOX = Path.home() / ".local/share/charlie/memory-outbox.sqlite3"


class MarmWriteError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class MarmClient:
    def __init__(self, url="http://127.0.0.1:8001", api_key=None, timeout=10):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("MARM URL must be an HTTP(S) server address")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("Use MARM_API_KEY for credentials; URL must have no query or fragment")
        if parts.path.rstrip("/"):
            raise ValueError("Use MARM's server root URL, without /mcp")
        self.url = url.rstrip("/") + "/marm_log_entry"
        self.api_key = api_key if api_key is not None else os.environ.get("MARM_API_KEY")
        self.timeout = timeout
        self.opener = build_opener(_NoRedirect())

    def write(self, payload):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        request = Request(self.url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                result = json.load(response)
        except HTTPError as error:
            raise MarmWriteError(f"MARM returned HTTP {error.code}") from None
        except (URLError, OSError, ValueError) as error:
            # Do not store response bodies, authorization headers, or credentials.
            raise MarmWriteError(f"MARM request failed ({type(error).__name__})") from None
        if not isinstance(result, dict) or result.get("status") != "success" or not result.get("entry_id"):
            raise MarmWriteError("MARM did not confirm a saved log entry")
        return result


class MarmOutbox:
    """Implements MemoryStore.save with restart-safe local enqueueing."""

    def __init__(self, path=DEFAULT_OUTBOX, project="charlie", session="charlie-experiences"):
        self.path = Path(path).expanduser()
        if not project.strip() or len(project) > 255 or not session.strip():
            raise ValueError("A project (1–255 characters) and session are required")
        self.project, self.session = project, session
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS outbox (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL, receipt TEXT,
                attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT)""")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def save(self, memory: CandidateMemory):
        record = memory.to_dict()
        serialized = json.dumps(record, sort_keys=True, ensure_ascii=False)
        identifier = hashlib.sha256((self.project + '\n' + self.session + '\n' + serialized).encode()).hexdigest()
        payload = {
            "project": self.project, "session_name": self.session,
            "entry": f"Charlie memory {identifier}\n{memory.text}\nMetadata: {serialized}",
        }
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO outbox(id, payload) VALUES (?, ?)",
                         (identifier, json.dumps(payload, ensure_ascii=False)))

    def pending(self):
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM outbox WHERE receipt IS NULL").fetchone()[0]

    def flush(self, client: MarmClient, limit=100):
        if limit < 1:
            raise ValueError("limit must be positive")
        report = {"delivered": 0, "log_only": 0, "pending": 0, "error": None}
        # Multiple sync processes must not send the same pending batch concurrently.
        with Path(str(self.path) + ".lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                report.update(error="Another memory sync is running", pending=self.pending())
                return report
            with self._connect() as conn:
                rows = conn.execute("SELECT id, payload FROM outbox WHERE receipt IS NULL ORDER BY rowid LIMIT ?",
                                    (limit,)).fetchall()
            for identifier, payload in rows:
                try:
                    result = client.write(json.loads(payload))
                except MarmWriteError as error:
                    with self._connect() as conn:
                        conn.execute("UPDATE outbox SET attempts=attempts+1, last_error=? WHERE id=?",
                                     (str(error), identifier))
                    report["error"] = str(error)
                    break
                with self._connect() as conn:
                    conn.execute("UPDATE outbox SET receipt=?, attempts=attempts+1, last_error=NULL WHERE id=?",
                                 (json.dumps(result), identifier))
                report["delivered"] += 1
                if not result.get("memory_id"):
                    # MARM saved the log but its semantic write failed. Retrying the
                    # whole request would create another log entry, so retain receipt.
                    report["log_only"] += 1
            report["pending"] = self.pending()
        return report
