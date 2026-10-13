"""Fixed-shape YOLOv8 ONNX adapter, independent of Torch's changing exporter default."""
import copy
import json
from pathlib import Path


def export_onnx(model,path,size,classes):
    import torch
    import numpy as np
    import onnx
    from ultralytics.nn.modules import Detect
    network=copy.deepcopy(model.model).cpu().float().eval()
    network.fuse()
    for layer in network.modules():
        if isinstance(layer,Detect):
            layer.dynamic=False;layer.export=True;layer.format='onnx'
    sample=torch.zeros(1,3,size,size)
    with torch.no_grad():
        reference=network(sample)
        network(sample) # Freeze anchors for this explicit input shape.
    torch.onnx.export(network,sample,str(path),opset_version=11,dynamo=False,do_constant_folding=True,
                      input_names=['images'],output_names=['output0'])
    graph=onnx.load(path)
    for key,value in dict(stride='32',task='detect',names=repr(dict(enumerate(classes))),imgsz=repr([size,size]),description='Charlie Vision Lab unqualified local candidate').items():
        entry=graph.metadata_props.add();entry.key=key;entry.value=value
    onnx.checker.check_model(graph);onnx.save(graph,path)
    result=dict(checked=True,input_shape=[1,3,size,size],opset=11)
    try:
        import onnxruntime as ort
        output=ort.InferenceSession(str(path),providers=['CPUExecutionProvider']).run(None,{'images':sample.numpy()})[0]
        expected=reference.detach().numpy();error=float(np.max(np.abs(output-expected)))
        if output.shape!=expected.shape or not np.allclose(output,expected,rtol=.001,atol=.001):raise ValueError('ONNX output differs from frozen Torch model')
        result.update(onnxruntime_checked=True,maximum_absolute_error=error,output_shape=list(output.shape),control='zero tensor engineering equivalence; not authentic recognition evidence')
    except ImportError:result['onnxruntime_checked']=False
    return result
