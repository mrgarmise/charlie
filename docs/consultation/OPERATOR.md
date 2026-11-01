# Native acceptance — PENDING NATIVE

No installation or device experiment occurred in this mission session. ARM64
Debian 13 Pi 5 advertises 8 GB; read-only sample found about 5 GB available, zero
swap used, 802 GB free, about 50 C and fan about 3188 RPM. This is one idle sample,
not a cooling-under-load qualification. Systemd, TCP/UDP socket creation,
/dev/vcio_gencmd and camera/Hailo/serial access are denied/absent; DNS downloads
fail. Installed/live revision, active service/workload and throttling are UNKNOWN.
Full private preflight: `/home/five/charlie-consultation-evidence-20261101/native-preflight/preflight.json`.

Preserve all source/native/merge holds from PRs #23/#24/#26. Leave #25 separate.
Never start `main.py --hardware`, movement, firmware sync, training or promotion
for this experiment. Native integration transport remains held in code; the
normal `--llm-consultation` switch creates a **shadow queue only**.

## Operator installation, separate from existing Charlie services

1. In an unrestricted native terminal identify installed/live checkout, dirty
   state, exact command/unit, acquisition owners and active workloads. Record
   `uname -a`, `cat /etc/os-release`, `free -m`, `df -h`, `uptime`,
   `vcgencmd get_throttled`, thermal-zone temperatures and hwmon fan RPM. Capture
   60 seconds of ordinary dashboard/telemetry/frame and Executive latency before
   inference. Unknown baseline or throttling means stop, do not infer headroom.
2. Obtain a pinned official Ollama Linux ARM64 release and its published checksum
   from https://github.com/ollama/ollama/releases . Record version, URL, archive
   SHA256 and checksum verification; inspect archive members before extracting
   into a new private directory such as `$HOME/ollama-consultation/VERSION`.
   Follow https://docs.ollama.com/linux for the current ARM64 archive format and
   library layout. Do not run a privileged curl-to-shell installer or replace an
   existing installation. On this session download/install is **PENDING NATIVE**.
3. With operator authorization start a dedicated transient user unit; keep all
   existing Charlie units unchanged. Example after setting an absolute verified
   `OLLAMA_BIN` and new private `OLLAMA_MODELS` directory:

   ```sh
   systemd-run --user --unit=charlie-consultant --collect \
     -p MemoryMax=2500M -p MemorySwapMax=0 -p CPUQuota=100% -p Nice=15 \
     -p NoNewPrivileges=yes -p PrivateDevices=yes -p ProtectSystem=strict \
     -p ProtectHome=tmpfs -p "BindPaths=$OLLAMA_MODELS" \
     --setenv=OLLAMA_HOST=127.0.0.1:11434 \
     --setenv="OLLAMA_MODELS=$OLLAMA_MODELS" \
     --setenv=OLLAMA_NUM_PARALLEL=1 --setenv=OLLAMA_MAX_LOADED_MODELS=1 \
     --setenv=OLLAMA_MAX_QUEUE=1 --setenv=OLLAMA_KEEP_ALIVE=0 \
     "$OLLAMA_BIN" serve
   ```

   The binary/library directory also needs explicit read-only binding if under
   the hidden home directory (`-p BindReadOnlyPaths=ABSOLUTE_RELEASE_DIRECTORY`).
   Verify actual unit sandbox/cgroup properties and `ss -ltnp`: **only loopback**.
   No camera/device, robot credentials, private notebooks or executable tools
   belong in this unit. If sandbox properties fail, stop and resolve them rather
   than dropping bounds. CPU threads in HTTP options alone do not bound service
   RSS; cgroup limits and system headroom checks are both required.
4. With about 3 GB available system headroom and zero swap pressure, explicitly
   pull `qwen3:1.7b` through this dedicated loopback service; record `/api/version`,
   `/api/tags` (immutable model digest) and `/api/show` (quantization/parameters).
   Model pull is a network download, never a billed OpenAI request. If cgroup
   OOM, poor latency or interference occurs, stop/unload and compare only
   `qwen3:0.6b`, with a separate report. No automatic 4B/8B selection.

## Finite acceptance checklist

- [ ] Verify installed/live identity, existing service ownership and source holds.
- [ ] Verify dedicated service release/archive checksum, local-only listener,
  device/filesystem restrictions and effective CPU/memory/swap bounds.
- [ ] Record real 1.7B model digest/quantization and cooling/throttling under load.
- [ ] Run `python -m tools.consultation_probe --output NEW_IDLE_COLD --benchmark`
  then the same command with `--warm` in a new directory. Both run the same 18
  questions, 2048 context, 160 answer tokens, one thread and 30-second wall bound.
  Warm mode has at most five seconds keep-alive and explicit final unload.
  Keep every failed request and OOM; inspect `load_duration` rather than assume
  warm residency. The report records nonstreaming latency (TTFT unmeasured),
  tokens/sec, sampled system memory/load/thermal data and model metadata.
  Independently measure server peak RSS/cgroup memory. Grade each answer useful,
  incorrect, misleading or abstaining; preserve the exact response and rationale.
- [ ] Independently compare preflight baseline with a **separately authorized
  stationary normal sensing** run: existing camera/Hailo/dashboard/telemetry and
  same Executive, motors unavailable. Use `--phase stationary` only as a report
  label; the probe never starts sensing. Record frame gaps, drops, freshness,
  watchdog delays, dashboard p50/p95 and Executive response. Stop on a missed
  existing watchdog deadline, >10% degradation of established baseline, any
  thermal throttling, temperature >=70 C, MemAvailable <3 GiB, swap use, or
  load average >2. Existing stricter bounds take precedence. Verify fan cooling
  throughout load and recovery. No native pass without these actual traces.
- [ ] If 1.7B is unsuitable repeat 0.6B explicitly; publish measured comparison.
  No Mint/Pi speed ratio is claimed. No Mint test is authorized/configured here.
- [ ] Review records as **unverified hypotheses** and demonstrate independent
  rejection, offline operation and missing-provider recovery. Separately review
  native qualification before any enabling code change; normal transport stays
  shadow-only in this PR regardless of CLI options.

## Remote and rollback

Remote provider construction is explicit Python configuration only, unavailable
from normal startup. It requires exact private literal-IP HTTPS allowlist,
verified TLS certificate and a token supplied through the named environment
variable; use an authenticated TLS reverse proxy/VPN with access control at the
remote host. Never expose unauthenticated Ollama on LAN/internet. Only a general
text observation question is transmitted; no raw frames, labels, notes or journal
content. Remote is attempted only after local failure, never on cancellation or
resource refusal. No OpenAI API adapter, authentication, billing or charged calls
exist. Consultations use neither personal ChatGPT credentials nor Work allowance.

Rollback: omit `--llm-consultation` (default); existing behavior remains. Stop the
new dedicated unit with `systemctl --user stop charlie-consultant`; confirm model
RSS and listener disappear. Remove only the new version/model directories after
retaining reports. Preserve append-only consultation records and original journals.
Do not reset existing worktrees, alter active PRs or roll back unrelated services.

API design references: https://docs.ollama.com/api/chat ,
https://docs.ollama.com/api/show , https://docs.ollama.com/api/generate ,
https://ollama.com/library/qwen3 . Native numbers remain unavailable until measured.

## Example version-pinned archive staging (operator only)

After choosing an exact upstream `VERSION` and obtaining its authenticated
published checksum, stage into a new directory. These commands were **not run**:

```sh
RELEASE_DIR="$HOME/ollama-consultation/$VERSION"
mkdir -p "$RELEASE_DIR"
curl -fL --proto '=https' --tlsv1.2 \
  "https://github.com/ollama/ollama/releases/download/$VERSION/ollama-linux-arm64.tar.zst" \
  -o "$RELEASE_DIR/ollama-linux-arm64.tar.zst"
sha256sum "$RELEASE_DIR/ollama-linux-arm64.tar.zst"
# Stop until the digest matches the authenticated upstream checksum.
tar --zstd -tf "$RELEASE_DIR/ollama-linux-arm64.tar.zst"
# Stop on absolute paths, .. escapes or unsafe link targets in the member list.
tar --zstd --no-same-owner -xf "$RELEASE_DIR/ollama-linux-arm64.tar.zst" -C "$RELEASE_DIR"
OLLAMA_BIN="$RELEASE_DIR/bin/ollama"
"$OLLAMA_BIN" --version
```

Current official ARM64 documentation uses `.tar.zst`; verify asset name/layout for
the pinned release. Set a **new** private `OLLAMA_MODELS` directory and bind both
that writable directory and the release directory read-only as described above.
For model pull/identity/unload against the verified loopback-only service:

```sh
OLLAMA_HOST=127.0.0.1:11434 "$OLLAMA_BIN" pull qwen3:1.7b
curl --fail --max-time 5 http://127.0.0.1:11434/api/version
curl --fail --max-time 5 http://127.0.0.1:11434/api/tags
curl --fail --max-time 5 http://127.0.0.1:11434/api/show \
  -H 'Content-Type: application/json' -d '{"model":"qwen3:1.7b"}'
curl --fail --max-time 5 http://127.0.0.1:11434/api/generate \
  -H 'Content-Type: application/json' -d '{"model":"qwen3:1.7b","keep_alive":0}'
```
