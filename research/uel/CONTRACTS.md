# Contracts

Profiles declare ordered channels, units, finite calibrated numerical bounds, neutral position, scope, source, revision and maximum trial duration. The profile accepts simulation scope only. Python adapters receive fixed-order tuples and return ordered scalar readings timestamped using the process monotonic clock. The session checks telemetry before and after invocation. Adapter authors must make their simulated steps bounded and must return when interrupted.

SQLite schema 1 has session identity and append-only application events keyed by session, trial and phase. Each payload carries a SHA-256 digest. JSONL export includes trial ID, phase and payload. A fresh session ID is required after a terminal stop. Replay reads captured result events without acquiring a camera or serial device.
