"""Operator-run fixed graph feasibility/HEF compiler. No Pi deployment/install."""
import argparse
import importlib.metadata
import json
import platform
from pathlib import Path
import numpy as np
from PIL import Image
from .contract import INPUT,OUTPUT,PREPROCESS,PREPROCESS_PROFILES,preprocess,sha
from .corpus import image_path,verify


def validate_graph(path):
    import onnx
    graph=onnx.load(path);onnx.checker.check_model(graph)
    if [(x.domain,x.version) for x in graph.opset_import] not in ([('',11)],[('ai.onnx',11)]):
        raise ValueError('verified compiler contract requires actual ONNX opset 11')
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
    p.add_argument('--model-record',type=Path,help='required for nonlegacy preprocessing; matching training.json')
    a=p.parse_args()
    model_record=json.loads(a.model_record.read_text()) if a.model_record else {}
    if model_record and model_record['onnx_sha256']!=sha(a.onnx):raise ValueError('model record/ONNX mismatch')
    profile=model_record.get('preprocessing',PREPROCESS)
    if profile not in PREPROCESS_PROFILES:raise ValueError('unknown compilation preprocessing')
    if platform.system()!='Linux' or platform.machine()!='x86_64':raise RuntimeError('DFC requires supported Linux x86_64')
    corpus=verify(a.manifest);rows=[r for r in corpus['rows'] if r['role']=='train']
    if model_record and model_record['dataset_digest']!=corpus['digest']:raise ValueError('model-record/calibration corpus digest mismatch')
    if not rows or len(rows)>2048:raise ValueError('1..2048 training-only calibration images required')
    if 'SYNTHETIC' in corpus['authenticity'] and not a.engineering_feasibility:raise ValueError('synthetic calibration requires explicit feasibility flag')
    version=importlib.metadata.version('hailo-dataflow-compiler')
    if version!='3.33.0':raise RuntimeError('compiler procedure pins DFC 3.33.0; revalidate other releases')
    graph=validate_graph(a.onnx)
    metadata={p.key:p.value for p in graph.metadata_props}
    embedded=metadata.get('charlie.preprocessing',PREPROCESS)
    if embedded not in PREPROCESS_PROFILES:raise ValueError('unknown ONNX preprocessing metadata')
    if model_record and profile!=embedded:raise ValueError('ONNX/model-record preprocessing mismatch')
    profile=embedded
    if metadata.get('charlie.dataset_digest',corpus['digest'])!=corpus['digest']:raise ValueError('ONNX/calibration corpus digest mismatch')
    from hailo_sdk_client import ClientRunner
    a.output.mkdir(exist_ok=False,parents=True)
    runner=ClientRunner(hw_arch='hailo8l')
    end=graph.graph.node[-1].name
    runner.translate_onnx_model(str(a.onnx),'charlie_score',start_node_names=['images'],end_node_names=[end],net_input_shapes={'images':list(INPUT)})
    runner.save_har(str(a.output/'parsed.har'))
    calibration=[]
    for row in rows:
        with Image.open(image_path(a.manifest,row)) as image:x,_=preprocess(image,profile=profile)
        calibration.append(x[0].transpose(1,2,0))
    runner.optimize(np.stack(calibration))
    runner.save_har(str(a.output/'quantized.har'))
    hef=runner.compile();path=a.output/'score.hef';path.write_bytes(hef)
    record=dict(architecture='hailo8l',hef_sha256=sha(path),onnx_sha256=sha(a.onnx),dfc=version,
        normalization='host /255; no embedded normalization',input_shape=list(INPUT),output_shape=list(OUTPUT),
        input_layout='NHWC virtual streams, NCHW CPU',
        input_name='charlie_score/input_layer1',output_name='charlie_score/conv4',
        hef_input_order='NHWC',hef_output_order='FCR',
        hef_input_dimensions=[32,256,3],hef_output_dimensions=[1,64,11],
        vstream_output_shape=[1,1,64,11],vstream_dtype='float32',
        output_layout='Python FLOAT32 [batch,height,width,classes]; transpose(0,3,1,2) to decoder NCHW; HEF metadata FCR is separate',
        decoder='ctc-greedy-abstain-v1',calibration_manifest_sha256=sha(a.manifest),
        calibration_images=[r['sha256'] for r in rows],calibration_count=len(rows),
        qualification=corpus['authenticity'],native_validated=False,end_node=end,preprocessing=profile,
        model_record_sha256=sha(a.model_record) if a.model_record else None)
    (a.output/'hef.json').write_text(json.dumps(record,indent=2))
    print(json.dumps(record,indent=2))

if __name__=='__main__':main()
