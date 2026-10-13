# Charlie Vision Lab 0.1

A local browser workbench for read-only observation discovery, human bounding-box
review, frozen datasets, **actual YOLOv8n training**, assisted review, independent
evaluation and ONNX preparation. This feature branch does not deploy, activate a
policy, open a camera or command a controller. Read `ALA_LEARNING_CHARTER.md` and
`ALA2_ACCEPTANCE_STANDARD.md`: none of these engineering checks establishes
Executive E1, PPAL P1, guarded integration I1 or ALA-2 completion.

## Install on Linux Mint

Use an independent development checkout, outside original archives/notebooks.
Python 3.10+ with `venv`, SSH keys/agent and a browser are needed; the tested host
used Python 3.12.14. Check actual Mint memory, CPU and available GPU in Sources →
Preflight before selecting training parameters. Installation needs internet;
operation uses local files and configured SSH sources, without cloud accounts.

```bash
git clone --branch feature/charlie-vision-lab https://github.com/mrgarmise/charlie.git charlie-vision-lab
cd charlie-vision-lab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-vision-lab.txt
# CPU wheels; torch/torchvision must be a matching pair.
python -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-vision-lab-training.txt
python -m pip check
```

If those wheel versions are unavailable for your Python/platform, choose a
supported matching pair from PyTorch's official installation instructions and
rerun the optional ML tests below. CUDA is optional: install matching CUDA wheels
instead, and select an index actually reported by Preflight. CUDA training was
not tested here. CPU training at 640px can be slow; begin with batch 1–4 and two
threads, and measure memory locally. Dependencies are separate from Charlie's
runtime requirements; no change to the authoritative release environment is
required. Ultralytics 8.3.203 is an AGPL-3.0 dependency; retain its licensing terms.

**Start, from the activated checkout environment:**

```bash
python -m vision_lab
```

Open **http://127.0.0.1:8768**. The server only binds to loopback; `--port` changes
the local port, not the network interface. `--state /absolute/separate/lab-state`
selects another lab directory. Default:
`~/.local/share/charlie/vision-lab`, separate from the Executive's original
`/home/five/.local/share/charlie/development`. Do not use that notebook or any
source directory as lab state. A notebook-directory guard and process locks
prevent common mistakes. Ctrl+C cancels/reaps the local worker, retains completed
epoch checkpoints and closes the application. Restart interrupted jobs explicitly.

## Add observations without changing Charlie

Sources → Add read-only source supports copied folders, mounted SFTP folders, or
direct SFTP. Existing SSH identity files/agent and verified known-hosts entries
are used. No passwords/private keys are stored in lab state or the repository.
First verify the established host identity through your usual SSH setup. A
missing or changed host key fails closed. No remote shell command is executed.
Direct SFTP does not execute ProxyJump/ProxyCommand; use your existing SFTP mount
for those configurations. Prefer a Pi account/permission arrangement with
read-only access to the intended archive.

Example direct source fields:

| Field | Value |
|---|---|
| Type | Direct SFTP |
| Host | `charlie.local` |
| User | `five` |
| Root | `/home/five/Projects/charlie/robotron-runs` |
| Group depth | Inspect directory hierarchy; start with `1` |
| Authenticity | Unknown until provenance is confirmed |

Register other archive roots separately; similarly named Pi worktrees need not
contain duplicate observations. Mint's existing mounted SFTP path or a copied
folder can instead be a Local source. Do not register the original notebook.
Recursive indexing has configurable exclusion globs. Group depth counts path
components beneath each configured root; inspect the displayed source/session
provenance before freezing. A session ID combines source identity and those
components; grouping is not proof that two sessions are independent.

PNG/JPEG/WebP/BMP/TIFF are decoded with size/pixel limits. Multi-page TIFF is
bounded to 16 pages. Local ZIP/TAR/TAR.GZ image members are read without extracting
paths. Local videos are detected and sampled every 30 frames, at most 64 samples
per file, when OpenCV can decode them; this is an inventory aid, not exhaustive
video labeling. JSON/JSONL frame metadata is detected and reported, but arbitrary
metadata schemas are not imported. Remote videos/containers are reported for
selective local copy or an existing mount, not automatically downloaded whole.
Corrupt, oversized and inaccessible inputs produce warnings.

Direct SFTP indexing reads metadata only. Clicking a frame selectively transfers
it and creates a normalized pixel cache/thumbnail; hashes and duplicate detection
become available then. Indexing a local source decodes supported images to derive
hashes/thumbnails; full pixel caching is selective. Original bytes are never
written. Incremental indexing uses size/mtime; reindex and check provenance if an
archive changes. Cached observations are retained snapshots, not proof a remote
file is still unchanged. File mtime and sampled-video relative time are explicitly
source metadata; they are not verified exposure timestamps.

## Complete workflow

1. **Sources:** add/configure roots, classes and grouping. Inspect warnings and
   preflight. Configure player, grunt, hulk, tank, human and observed hazards;
   unknown is reserved for unresolved objects. Default labels are editable.
2. **Annotate:** select a frame; wait until verified pixels decode. Enter a
   reviewer identity. Drag empty space to draw, click a box to move it, and drag
   corner handles to resize. Shift+drag overlaps an existing box. B selects
   drawing; Delete removes; 1–9 choose classes; wheel/+/− zoom; Space+drag pans;
   Ctrl+Z/Shift+Ctrl+Z undo/redo; Ctrl+S saves draft. Multiple boxes, confidence,
   uncertainty and notes persist. History retains every revision. A stale-tab
   save is rejected. Save must be acknowledged before continuing.
3. **Verify:** Accept/correct all & verify explicitly accepts reviewed boxes.
   Unknown/uncertain objects cannot be verified. Explicitly check Reviewed empty
   frame for a negative example. Exclude unsuitable frames. Draft/review frames
   are not training ground truth. Preserve uncertain examples for later review.
4. **Datasets:** inclusion checkboxes select exactly the intended frames. Check
   quality/class balance, inspect duplicate groups and sessions. Freeze a named
   version with at least three groups (train, validation, test). Default seeded
   assignment uses one group test, one validation, others training; override
   session→role assignments with the displayed session IDs when appropriate.
   Exact duplicate pixels connect groups and are deduplicated; conflicting labels
   fail. Near-duplicate images are not automatically detected—group entire
   recording sessions together and independently inspect boundary cases.
5. Download the reproducible YOLO export if desired. Frozen manifests include
   pixel/file hashes, reviewed annotation revisions/digests, source provenance,
   class list, split and exclusions. Later edits require a new dataset version.
   Partition ownership persists across versions; test pixels cannot migrate to
   training. Test images are not passed to the training worker at all.
6. **Train & evaluate:** choose frozen data, epochs, input resolution (64–640,
   multiple of 32), batch, threads and CPU/CUDA. Select an existing model baseline
   *before* training a challenger; its checkpoint hash is frozen. The architecture
   is YOLOv8n from scratch, not silently downloaded pretrained weights. Actual
   optimizer updates, initial/final weight hashes, environment, dataset digest,
   epoch checkpoints and model version are recorded. Jobs provides progress,
   bounded deadlines (default 24h), logs, cancellation and explicit checkpoint
   restart. Resume copies checkpoint state into a new job output directory.
7. Run validation metrics for development. Once model selection is finished,
   perform the final held-out test comparison. Candidate/baseline use identical
   frozen observations and fixed thresholds. Precision, recall, AP50, per-class
   TP/FP/FN, geometric class confusion, misses/false positives, mean latency and
   visual error examples are retained separately from training metrics. Error
   pictures show green ground truth and red predictions. These are offline
   descriptive measurements, not gameplay reward or Pi throughput.
8. Held-out outcomes are one-use and remain auditable. After exposure, the app
   rejects further training using those test pixels; collect fresh independent
   test sessions for a new selection cycle. Do not manually change state to reuse
   a consulted test set. An interrupted final evaluation conservatively marks its
   test pixels consulted. Baseline-free bootstrap evaluation is clearly reported
   as having no comparison. No gain is inferred from changed weights alone.
9. For assisted labeling, include additional unverified frames and use Suggest.
   The queue prioritizes uncertainty and classes underrepresented in verified
   labels. Load proposals, correct/review, then explicitly verify. Proposals never
   become ground truth automatically. Frozen test frames are excluded from this
   pathway. Predictions are not agency/SELF evidence.
10. Export ONNX + Hailo preparation. Download the checkpoint, model provenance,
    checked fixed-shape ONNX, deployment contract and training-only calibration
    images. Follow [Hailo preparation](hailo-8l.md); this is not a compiled HEF.

## Validation and recovery

```bash
python -m pip install pytest
python -m pytest tests/vision_lab -q
# Real optimizer, frozen-baseline evaluation, ONNX, cancellation/resume tests:
VISION_LAB_ML_TESTS=1 python -m pytest tests/vision_lab -q
# Generates clearly SYNTHETIC images and does real CPU training/evaluation/export:
python -m vision_lab.demo --output /tmp/vision-lab-SYNTHETIC-new --train --export
```

The demo output path must not already exist. These shape fixtures are engineering
checks, never authentic Robotron labels. Optional rendered browser regression:
install PySide6 and run `PYTHONPATH=. python tests/vision_lab/browser_smoke.py`.
Use `QT_QPA_PLATFORM=offscreen` only for a headless test host; an ordinary browser
needs none of these Qt dependencies. See [verification report](verification.md).

To back up lab state: stop the app, verify no lab worker remains, copy the entire
lab state directory (SQLite plus pixel cache/manifests/jobs/models), and hash the
backup. Restore into a new separate directory and start with `--state` to verify
integrity before using it. Keep originals and the previous backup. State migration
into Charlie's Executive notebook is not implemented or authorized.

## Architecture and current limits

| Module | Responsibility |
|---|---|
| `sources.py` | scoped readers, inventory, hashes, selective normalization/cache |
| `store.py` | local SQLite, append-only annotation history, optimistic revisions |
| `datasets.py` | quality, session/duplicate splits, immutable manifests/exports |
| `jobs.py`, `worker.py` | durable sequential subprocess jobs, cancellation/resume |
| `evaluation.py` | independent detection/confusion/error/latency measurements |
| `adapter.py` | model registry integrity and action-free Charlie observation contract |
| `exporting.py` | checked fixed-shape ONNX export, numerical Torch/ORT comparison |
| `server.py`, `static/` | loopback HTTP/session/CSRF guards and canvas workspace |

Metadata and caches are local untrusted-input boundaries, not a multi-user hosted
service. Source reads are root-scoped, symlinks/traversal denied, no archive
extraction or arbitrary checkpoint uploads are provided. Model `.pt` files are
only this lab's own generated checkpoints and are hash-checked before loading;
keep lab state owned by your user and do not import untrusted pickle checkpoints.
Do not expose this loopback service through a public tunnel. Inventory responses
currently include all metadata; the UI pages 100 frames, but very large archives
should be divided into narrower source roots. SFTP reads rely on SSH integrity
and server permissions; simultaneous malicious server-side path changes are not
provably preventable from an SFTP client. Source archives should be immutable.

No access to Mint/Pi, authentic new archives or Hailo tooling was available. GPU,
real SSH connectivity, authentic accuracy, near-duplicate independence, native
resource costs, Hailo parsing/quantization/compilation and hardware inference
remain operator validation. Existing authentic score-review records are neither
recovered nor modified by this new application.
