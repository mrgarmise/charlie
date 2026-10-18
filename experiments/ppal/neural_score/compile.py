"""Operator-run fixed graph feasibility/HEF compiler. No Pi deployment/install."""
import argparse
import importlib.metadata
import json
import platform
from pathlib import Path
import numpy as np
from PIL import Image
from .contract import INPUT,OUTPUT,preprocess,sha
from .corpus import image_path,verify


def validate_graph(path):
    import onnx
    graph=onnx.load(path);onnx.checker.check_model(graph)
    shape=lambda value:tuple(d.dim_value for d in value.type.tensor_type.shape.dim)
    if len(graph.graph.input)!=1 or len(graph.graph.output)!=1 or shape(graph.graph.input[0])!=INPUT or shape(graph.graph.output[0])!=OUTPUT:
        raise ValueError('fixed score graph shape mismatch')
    if graph.graph.input[0].name!='images' or graph.graph.output[0].name!='logits':
        raise ValueError('fixed score graph node mismatch')
    if not graph.graph.node or {n.op_type for n in graph.graph.node}-{'Conv','Relu'}:
        raise ValueError('unexpected graph operators')
    return graph


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('onnx',type=Path)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--engineering-feasibility',action='store_true')
    a=p.parse_args()
    if platform.system()!='Linux' or platform.machine()!='x86_64':raise RuntimeError('DFC requires supported Linux x86_64')
    corpus=verify(a.manifest);rows=[r for r in corpus['rows'] if r['role']=='train']
    if not rows or len(rows)>2048:raise ValueError('1..2048 training-only calibration images required')
    if 'SYNTHETIC' in corpus['authenticity'] and not a.engineering_feasibility:raise ValueError('synthetic calibration requires explicit feasibility flag')
    version=importlib.metadata.version('hailo-dataflow-compiler')
    if version!='3.33.0':raise RuntimeError('compiler procedure pins DFC 3.33.0; revalidate other releases')
    graph=validate_graph(a.onnx)
    from hailo_sdk_client import ClientRunner
    a.output.mkdir(exist_ok=False,parents=True)
    runner=ClientRunner(hw_arch='hailo8l')
    end=graph.graph.node[-1].name
    runner.translate_onnx_model(str(a.onnx),'charlie_score',start_node_names=['images'],end_node_names=[end],net_input_shapes={'images':list(INPUT)})
    runner.save_har(str(a.output/'parsed.har'))
    calibration=[]
    for row in rows:
        with Image.open(image_path(a.manifest,row)) as image:x,_=preprocess(image)
        calibration.append(x[0].transpose(1,2,0))
    runner.optimize(np.stack(calibration))
    runner.save_har(str(a.output/'quantized.har'))
    hef=runner.compile();path=a.output/'score.hef';path.write_bytes(hef)
    record=dict(architecture='hailo8l',hef_sha256=sha(path),onnx_sha256=sha(a.onnx),dfc=version,
        normalization='host /255; no embedded normalization',input_shape=list(INPUT),output_shape=list(OUTPUT),
        input_layout='NHWC virtual streams, NCHW CPU',output_layout='NHWC [1,1,64,11] virtual streams',
        decoder='ctc-greedy-abstain-v1',calibration_manifest_sha256=sha(a.manifest),
        calibration_images=[r['sha256'] for r in rows],calibration_count=len(rows),
        qualification=corpus['authenticity'],native_validated=False,end_node=end)
    (a.output/'hef.json').write_text(json.dumps(record,indent=2))
    print(json.dumps(record,indent=2))

if __name__=='__main__':main()
