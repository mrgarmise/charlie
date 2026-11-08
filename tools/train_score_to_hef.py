"""Operator-run reviewed-scores -> genuine checkpoint/ONNX -> Hailo-8L HEF.

Unlike train.py alone, this workflow REQUIRES a real compiler and refuses to
report success unless an actual nonempty HEF and binding record are produced.
No Pi deployment, physical gameplay, final-test consultation or model activation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
from pathlib import Path
import subprocess
import sys

from experiments.ppal.neural_score.corpus import assert_trainable


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def compiler_preflight():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError("actual score.hef requires Hailo DFC on supported Linux x86_64, not the Pi")
    try:
        version=importlib.metadata.version("hailo-dataflow-compiler")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError("Hailo Dataflow Compiler 3.33.0 is not installed. Obtain supported vendor compiler access on the x86_64 host; no HEF can be generated in this environment.") from exc
    if version != "3.33.0":
        raise RuntimeError("compiler version mismatch: expected validated DFC 3.33.0, got " + version)
    if importlib.util.find_spec("hailo_sdk_client") is None:
        raise RuntimeError("Hailo SDK ClientRunner missing; no HEF can be generated")
    return version


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,required=True,
                   help="frozen human-reviewed corpus, with train/val/test roles")
    p.add_argument("--output",type=Path,required=True,
                   help="brand-new directory for checkpoint/ONNX/compiled HEF/logs")
    p.add_argument("--steps",type=int,default=1850)
    p.add_argument("--train-seconds",type=int,default=7200)
    p.add_argument("--engineering-feasibility",action="store_true",
                   help="compile synthetic ONLY to prove graph feasibility; not a usable game reader")
    p.add_argument("--preflight",action="store_true",
                   help="check compiler and manifest without training or writing")
    a=p.parse_args()
    record=assert_trainable(a.manifest)
    roles=Counter(row["role"] for row in record["rows"])
    if roles["train"] < 1:
        p.error("no independently human-reviewed training frames available")
    if "SYNTHETIC" in record["authenticity"] and not a.engineering_feasibility:
        p.error("synthetic-only model is not an authentic score HEF; explicitly choose engineering feasibility")
    version=compiler_preflight()
    result=dict(manifest_digest=record["digest"],roles=dict(roles),compiler=version,
                model_training="PENDING",hef="PENDING",native_inference="NOT EXECUTED",
                independent_authentic_accuracy="NOT YET DEMONSTRATED")
    if a.preflight:
        print(json.dumps(dict(result,preflight="PASS",hef_generated=False),indent=2))
        return

    target=a.output.expanduser().resolve()
    if target.exists():
        p.error("output must be a new directory; existing training/model history is immutable")
    if not 1<=a.steps<=100000 or not 1<=a.train_seconds<=86400:
        p.error("steps/train-seconds outside bounded ranges")
    target.mkdir(parents=True)
    python=sys.executable

    def run(stage,args):
        log=target/(stage+".log")
        with log.open("x") as out:
            status=subprocess.run([python,*args],stdout=out,stderr=subprocess.STDOUT,
                                  text=True,check=False)
        if status.returncode!=0:
            (target/"state.json").write_text(json.dumps(dict(result,
                failed_stage=stage,exit_code=status.returncode,log=str(log),hef="NOT GENERATED"),indent=2)+"\n")
            raise SystemExit("Failed "+stage+"; inspect "+str(log)+"; no HEF accepted")
        return str(log)

    run("train",["-m","experiments.ppal.neural_score.train",
                 "--manifest",str(a.manifest),"--output",str(target/"model"),
                 "--steps",str(a.steps),"--seconds",str(a.train_seconds)])
    checkpoint=target/"model"/"score.pt"
    onnx=target/"model"/"score.onnx"
    training=target/"model"/"training.json"
    if not all(f.is_file() and f.stat().st_size>0 for f in (checkpoint,onnx,training)):
        raise RuntimeError("training did not persist nonempty PT/ONNX/training provenance")
    result.update(model_training="SAVED",pt_sha256=file_sha(checkpoint),
                  onnx_sha256=file_sha(onnx),training_json_sha256=file_sha(training))

    compile_command=["-m","experiments.ppal.neural_score.compile",str(onnx),
                     "--manifest",str(a.manifest),"--output",str(target/"hef"),"--model-record",str(training)]
    if a.engineering_feasibility:
        compile_command.append("--engineering-feasibility")
    run("compile",compile_command)
    hef=target/"hef"/"score.hef"
    contract=target/"hef"/"hef.json"
    if not hef.is_file() or hef.stat().st_size==0 or not contract.is_file():
        raise RuntimeError("compiler returned without an actual nonempty score.hef and binding contract")
    compiled=json.loads(contract.read_text())
    if compiled["hef_sha256"]!=file_sha(hef) or compiled["onnx_sha256"]!=file_sha(onnx):
        raise RuntimeError("HEF/ONNX provenance mismatch")
    result.update(hef="COMPILED",hef_sha256=file_sha(hef),
                  hef_path=str(hef),hef_contract_sha256=file_sha(contract),
                  intended_target="Hailo-8L 13 TOPS",physical_authorization=False,
                  qualification="SYNTHETIC GRAPH FEASIBILITY ONLY" if a.engineering_feasibility
                                else "AUTHENTICALLY TRAINED ARTIFACT; accuracy, Hailo parity and Pi activation still unqualified")
    (target/"state.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
