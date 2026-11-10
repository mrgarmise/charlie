# Objective evidence ledger

| Item / source | Command or method | Observed result | Uncertainty / next test / pass threshold |
|---|---|---|---|
| Private full flash | read_bytes + SHA256, fixed headers only | 8MiB / c196e907…25c5b; [metadata](stock-parity-evidence/backup-metadata.json) | Current board may differ; operator verifies unchanged hash before maintenance |
| Herrsergio vs backup | tools/audit_elegoo_stock.py with explicit public-image/source and stock-backup paths | 2,960,064 bytes exactly equal at0x10000; [JSON](stock-parity-evidence/stock-image-comparison.json) | No source reproducibility claim; any byte mismatch fails |
| Official ZIP vs mirror | SHA256 and byte equality over channel5 files/image | Same image; all inspected camera files equal except AP-channel line | Official source dates later than binary; future reproducible stock build must match exact image/config or remain source-only |
| UMRT comparison | hashes + CRLF-normalized diff, no credential output | Sketch/pins equal; UI and HTTP additions differ | Follow-on restores UI and keeps HTTP motor routes closed; physical UI acceptance pending |
| Owner ZIP | zipfile.infolist and file_digest | 523 entries, WROVER20210107; no S3 | Not exact stock source; no hardware claim |
| Jocelyn | git full log/show + source review + all-state GitHub issues | Modified UNO115200, OPI config, OTA; no issues returned | README/test harness not independent hardware proof; no control imports |
| Historical stationary operation | /home/five/charlie-ops/QUALIFICATION.md | 2026-11-01: real ELEGOO recognition→RP2040 display; no movement grant | Observed-via-history only; preserve exact runtime pin |
| Historical manual commission / STOP disposition | private /home/five/charlie-mobile-evidence/manual-commissioning/20261102T234826Z-four-direction-floor.json, SHA256916e4ba3c02143fba232264ad9f2392d09d5d8395d7ab2f42d65f27c7ad79394; combined-stop-trial SHA2560d2bef5ad7fd9412e7a9182eb7e238479f3a0c6e5880970467f9df65d74c2497 | Original trial showed a missing STOP ACK/final timeout and was marked NOT QUALIFIED; owner identifies flawed listening-period/test timing, followed by extensive successful STOP testing and real manual-drive out-of-range immediate stop | **HANDLED — DONE / OK** for historical stock STOP behavior, per owner's subsequent field qualification. Preserve original trial as failed harness evidence, not as an unresolved safety defect. No measured stop latency is invented; future replacement-specific physical acceptance is separate |
| PR30 builds | existing local final OPI/QSPI regular files, rehash | [validation report](stock-parity-validation.md) | Native-built only; no new rebuild of unchanged PR30 |
| Follow-on build/tests | focused Python, production C++ ASan/UBSan, OPI/QSPI image checks, separate GitHub runners | [validation report](stock-parity-validation.md) | Stub UART and browser simulation are not device proof |
| Current radio/camera/TCP/security | no acquisition performed | Unknown today; worksheet pending | Existing owners only; security/reset under separate maintenance authorization |

Acquisition records and raw firmware remain private. Public evidence consists of hashes, allowlisted metadata, source comparisons and test/build reports. No NVS/credential contents or raw binaries are included.
