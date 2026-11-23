"""Offline acceptance benchmark for isolated development data; does not start a service."""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import datetime as dt
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import socket
import sys
import tempfile
import time


# Expectations are independently authored. Matching a topic is a weak proxy for
# relevance, never an adjudication of a scientific claim.
CASES = (
    ("B3-01", "life_sciences", "How does photosynthesis convert light into stored chemical energy?",
     ("light", "chemical"), "Discuss light and chemical energy with a local reference."),
    ("B3-02", "life_sciences", "What limits plant growth besides sunlight?",
     ("water", "nutrient"), "Consider water or nutrients and limit conclusions to the evidence."),
    ("T1-03", "civilization", "Why does reliable food storage change settlement and population?",
     ("storage", "season"), "Consider seasonal variation and the limits of annual totals."),
    ("T2-05", "civilization", "How do standardized measures and interchangeable parts change repair?",
     ("repair", "interchange"), "Explain repeatability or interchangeability without assuming every part fits."),
    ("EVAL-FORMAL", "cross_track", "Convert 2 kg to g.", (), "Verify exactly 2000 g by dimensional conversion."),
    ("EVAL-MISSING", "cross_track", "What was the exact mass of the unmeasured sample tagged NRQ847?",
     (), "Require local measurements. No exact mass can be inferred."),
    ("EVAL-CONFLICT", "cross_track", "What was the length of the single test rod marked PVQ619 at noon?",
     (), "Two synthetic observers disagree under matched conditions. Retain disagreement or abstain."),
)
FIXTURE_DOCS = (
    ("PL1", "Photosynthesis in plants transfers energy from light into chemical stores."),
    ("PL2", "Water availability and nutrient supply can constrain plant growth."),
    ("CV1", "Food storage can buffer a community during a seasonal shortage."),
    ("CV2", "Standardized measures help make repair parts interchangeable."),
    ("CF1", "The length of rod PVQ619 at noon is 20 mm."),
    ("CF2", "The length of rod PVQ619 at noon is 30 mm."),
)


def disable_network():
    """Kernel-enforced offline worker. Reject inherited sockets, including Unix sockets."""
    for fd in Path("/proc/self/fd").iterdir():
        try:
            if os.readlink(fd).startswith("socket:"):
                raise RuntimeError("inherited socket in evaluation worker")
        except FileNotFoundError:
            continue
    lib = ctypes.CDLL(ctypes.util.find_library("seccomp") or "libseccomp.so.2", use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    ctx = lib.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not ctx:
        raise RuntimeError("seccomp allocation failed")
    try:
        for name in (b"socket", b"socketpair", b"connect", b"socketcall", b"io_uring_setup"):
            nr = lib.seccomp_syscall_resolve_name(name)
            if nr >= 0 and lib.seccomp_rule_add(ctx, 0x00050000 | errno.EPERM, nr, 0):
                raise RuntimeError("seccomp rule rejected")
        if lib.seccomp_load(ctx):
            raise RuntimeError("seccomp_load failed")
    finally:
        lib.seccomp_release(ctx)
    for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
        try:
            with socket.socket(family):
                pass
        except OSError as exc:
            if exc.errno == errno.EPERM:
                continue
            raise
        raise RuntimeError("offline canary unexpectedly opened a socket")


def fixture(destination):
    from learning.discovery.archive import build_fixture_archive
    docs = [dict(id=identifier, text=text, source="independently authored benchmark", kind="reference")
            for identifier, text in FIXTURE_DOCS]
    questions = [dict(id=key, track=track, question=q) for key, track, q, _, _ in CASES]
    return build_fixture_archive(destination, docs, questions)


def disk_bytes(path):
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def score(record, archive, key, terms):
    citations = record["citations"]
    cited_ids = [c["id"] if isinstance(c, dict) else c for c in citations]
    resolved = {key: archive.get(key) for key in cited_ids}
    content = " ".join(doc["text"].lower() for doc in resolved.values() if doc)
    status = record["status"]
    return {
        "citations_total": len(cited_ids),
        "citations_resolved": sum(resolved[c] is not None for c in cited_ids),
        "topic_terms_in_cited_text": [term for term in terms if term in content],
        "abstained": status in {"unknown", "blocked", "requires_observation", "contradicted"},
        "unsupported_definitive_status": (
            status == "supported_empirical" and (not cited_ids or None in resolved.values())
            or status == "verified_formal" and not record["checks"]
            or key in {"EVAL-MISSING", "EVAL-CONFLICT"} and status in {"supported_empirical", "verified_formal"}
        ),
    }


def benchmark_record(archive, state, case, *, now):
    from learning.discovery.inquiry import Inquiry
    from learning.discovery.journal import Journal
    from learning.discovery.conversation import respond

    key, track, question, terms, expected = case
    state.mkdir(parents=True)
    notebook = state / "journal.sqlite"
    journal = Journal(notebook)
    # Each independent case starts with its named question eligible. This benchmark
    # isolates answering from graph selection. The longitudinal run below tests the graph.
    row = next((q for q in archive.questions() if q["id"] == key),
               dict(id=key, track=track, question=question))
    journal.add_questions([dict(row, prerequisites=[])], now=now)
    started = time.monotonic()
    record = Inquiry(archive, journal).run_slot(
        "development-case-" + key, check=lambda: None, client_deadline=started + 90, now=now)
    if record is None or record["question_id"] != key:
        raise ValueError("inquiry did not commit the selected benchmark question")
    elapsed = time.monotonic() - started
    journal.close()
    persisted = Journal(notebook)
    digest = respond(persisted, "What have you been thinking about lately?", now=now)
    result = {
        "question_id": key, "question": question, "expected": expected, "status": record["status"],
        "findings": record["findings"], "citations": record["citations"],
        "checks": record["checks"], "uncertainty": record["uncertainty"], "followups": record["followups"],
        "digest_text": digest["text"], "metrics": score(record, archive, key, terms),
        "wall_seconds": elapsed,
    }
    next_row = persisted.select(now=now + 86400)
    result["next_question"] = None if next_row is None else next_row["id"]
    if next_row:
        next_record = Inquiry(archive, persisted).run_slot(
            "development-followup-" + key, check=lambda: None,
            client_deadline=time.monotonic() + 90, now=now + 86400)
        if next_record:
            with Journal(notebook, read_only=True) as reader:
                next_digest = respond(reader, "What have you been thinking about lately?", now=now + 86400)["text"]
            result["followup_session"] = {
                "id": next_record["question_id"], "question": next_record["question"],
                "status": next_record["status"],
                "digest": next_digest,
            }
    persisted.close()
    return result


def deterministic_projection(row):
    return {key: row[key] for key in ("question_id", "status", "citations", "findings", "checks",
                                      "uncertainty", "followups", "next_question")}


def evaluate(archive_path, state, *, synthetic):
    from learning.discovery.archive import Archive
    initial_cpu = time.process_time()
    start = time.monotonic()
    now = dt.datetime(2026, 1, 15, 12, tzinfo=dt.timezone.utc).timestamp()
    state.mkdir(parents=True)
    conflict_archive = state / "conflict-fixture"
    if not synthetic:
        fixture(conflict_archive)
    rows = []
    with Archive(archive_path) as archive:
        version = archive.version
        for case in CASES:
            key = case[0]
            path = conflict_archive if key == "EVAL-CONFLICT" and not synthetic else archive_path
            with Archive(path) as corpus:
                first = benchmark_record(corpus, state / "first" / key, case, now=now)
                second = benchmark_record(corpus, state / "replay" / key, case, now=now)
            first["corpus"] = "synthetic" if synthetic or path == conflict_archive else version
            first["deterministic"] = deterministic_projection(first) == deterministic_projection(second)
            rows.append(first)
    integrity = all(row["metrics"]["citations_total"] == row["metrics"]["citations_resolved"]
                    and not row["metrics"]["unsupported_definitive_status"] and row["deterministic"]
                    for row in rows)
    return {
        "schema_version": 1, "archive_version": version, "synthetic": synthetic,
        "offline_enforcement": "Linux seccomp; new sockets, socketpair and io_uring_setup denied; inherited sockets rejected; three socket-family canaries returned EPERM.",
        "mode": "Development source-first; one selected curriculum case per journal, prerequisite admission isolated for controlled comparison; no model or native hardware",
        "fixed_case_time_utc": dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
        "host": {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version()},
        "resources": {"cpu_seconds": time.process_time() - initial_cpu, "wall_seconds": time.monotonic() - start,
                      "worker_peak_rss_kib_linux": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      "archive_regular_file_bytes": disk_bytes(archive_path),
                      "journal_regular_file_bytes_first_run": disk_bytes(state / "first"),
                      "energy_joules": None, "energy_measurement": "No instrumented power measurement."},
        "qwen_comparison": {"direct": "not run", "augmented": "not run",
                            "reason": "This benchmark takes no model instance. Same-model comparison requires a separately available pinned local model."},
        "interpretation": "Resolved references establish traceability only. Topic-word coverage is a retrieval proxy. Unsupported definitive status is a structural screen, not an estimated scientific hallucination rate.",
        "structural_checks_passed": integrity, "cases": rows,
    }


def verified_model(model_store):
    from learning.discovery.inquiry import MODEL_DIGEST

    manifest = model_store / "manifests/registry.ollama.ai/library/qwen3/1.7b"
    if not manifest.is_file() or manifest.stat().st_size > 65536:
        raise ValueError("bounded local qwen3:1.7b manifest required")
    raw = manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MODEL_DIGEST:
        raise ValueError("model manifest differs from the candidate pin")
    layers = [x for x in json.loads(raw)["layers"] if x["mediaType"] == "application/vnd.ollama.image.model"]
    if len(layers) != 1 or not re.fullmatch(r"sha256:[a-f0-9]{64}", layers[0]["digest"]):
        raise ValueError("one content-addressed model layer required")
    layer = layers[0]
    file = model_store / "blobs" / layer["digest"].replace(":", "-")
    if not file.is_file() or file.stat().st_size != layer["size"] or not 0 < layer["size"] < 3 * 2**30:
        raise ValueError("model layer length mismatch")
    with file.open("rb") as stream:
        if stream.read(4) != b"GGUF":
            raise ValueError("expected local GGUF")
        stream.seek(0)
        if hashlib.file_digest(stream, "sha256").hexdigest() != layer["digest"][7:]:
            raise ValueError("model layer checksum mismatch")
    return file, layer["digest"]


def model_worker(pipe, path, prompt):
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_AS, (4 * 2**30, 4 * 2**30))
        resource.setrlimit(resource.RLIMIT_CPU, (60, 62))
        for env in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
            os.environ[env] = "1"
        from llama_cpp import Llama
        # The same binary, GGUF, chat template, seed, context and output ceiling
        # serve both arms. No daemon and no download or remote inference path.
        with Llama(model_path=str(path), n_ctx=1024, n_threads=1, n_gpu_layers=0,
                   seed=7, verbose=False) as llm:
            response = llm.create_chat_completion(
                messages=[{"role": "user", "content": prompt + "\n/no_think"}],
                temperature=0, max_tokens=128)
        answer = response["choices"][0]["message"]["content"]
        if not isinstance(answer, str) or len(answer.encode()) > 8192:
            raise ValueError("unbounded model reply")
        pipe.send({"answer": answer, "usage": response.get("usage", {})})
    except Exception as exc:
        pipe.send({"error": type(exc).__name__})
    finally:
        pipe.close()


def local_inference(path, prompt, check):
    import multiprocessing
    ctx = multiprocessing.get_context("fork")
    read, write = ctx.Pipe(duplex=False)
    child = ctx.Process(target=model_worker, args=(write, path, prompt))
    child.start()
    write.close()
    start = time.monotonic()
    try:
        while time.monotonic() - start < 60:
            check()
            if read.poll(.1):
                try:
                    result = read.recv()
                except EOFError:
                    return {"error": "worker exited without result"}
                return dict(result, wall_seconds=time.monotonic() - start)
        return {"error": "TimeoutError"}
    finally:
        if child.is_alive():
            child.kill()
        child.join()
        read.close()
        child.close()


def paired_evaluation(model_store, archive_path, state):
    from learning.discovery.archive import Archive
    from learning.discovery.inquiry import Inquiry, MODEL_DIGEST
    from learning.discovery.journal import Journal
    from importlib.metadata import version

    path, digest = verified_model(model_store)
    backend_version = version("llama-cpp-python")
    state.mkdir(parents=True)
    fixture_path = state / "paired-conflict"
    fixture(fixture_path)
    rows = []
    for key, track, question, terms, _ in CASES:
        if key == "EVAL-FORMAL":
            continue  # deterministic arithmetic never invokes the model
        with Archive(fixture_path if key == "EVAL-CONFLICT" else archive_path) as archive:
            direct_prompt = ("Answer the question in at most two sentences. Say what evidence is missing. "
                             "Do not invent measurements or references. Question: " + question)
            direct = local_inference(path, direct_prompt, lambda: None)
            calls = []
            def consult(prompt, guard):
                result = local_inference(path, prompt, guard)
                calls.append(result)
                if "error" in result:
                    raise ValueError("unavailable model result")
                usage = result["usage"]
                return {"answer": result["answer"], "identity": {"model_digest": MODEL_DIGEST},
                        "metrics": {"prompt_eval_count": usage.get("prompt_tokens"),
                                    "eval_count": usage.get("completion_tokens")}}
            with Journal(state / (key + ".sqlite")) as journal:
                row = next((q for q in archive.questions() if q["id"] == key),
                           dict(id=key, track=track, question=question))
                journal.add_questions([dict(row, prerequisites=[])])
                record = Inquiry(archive, journal).run_slot(
                    "paired-" + key, check=lambda: None, client_deadline=time.monotonic() + 90, consult=consult)
            rows.append({"question_id": key, "question": question, "direct_prompt": direct_prompt,
                         "direct_result": direct, "augmented_results": calls,
                         "inquiry_status": record["status"], "findings": record["findings"],
                         "citations": record["citations"], "metrics": score(record, archive, key, terms)})
    return {"model_manifest_sha256": MODEL_DIGEST, "gguf": digest, "backend": "llama-cpp-python " + backend_version,
            "sampling": {"temperature": 0, "seed": 7, "context": 1024, "max_output_tokens": 128},
            "cases": rows, "paired_outputs": sum("answer" in r["direct_result"] and
                   len(r["augmented_results"]) == 1 and "answer" in r["augmented_results"][0] for r in rows),
            "assessment": "Inspect the actual paired outputs against case expectations. Local development host performance only."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Audited archive directory; omit to test synthetic fixture.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-store", type=Path, help="Optional local Ollama models directory; requires llama-cpp-python for both development-only comparison arms.")
    args = parser.parse_args()
    disable_network()
    with tempfile.TemporaryDirectory(prefix="discovery-eval-") as tmp:
        root = Path(tmp)
        archive_path = args.archive
        if archive_path is None:
            archive_path = root / "fixture"
            fixture(archive_path)
        report = evaluate(archive_path, root / "journals", synthetic=args.archive is None)
        if args.model_store:
            report["qwen_comparison"] = paired_evaluation(args.model_store, archive_path, root / "paired")
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if report["structural_checks_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
