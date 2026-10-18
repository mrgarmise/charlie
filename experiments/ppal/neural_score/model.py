"""Fixed Conv/Relu only inference graph; CTC/string processing stays on CPU."""
import torch
from torch import nn
from .contract import INPUT,OUTPUT


class ScoreNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.layers=nn.Sequential(nn.Conv2d(3,16,3,stride=2,padding=1),nn.ReLU(),
            nn.Conv2d(16,32,3,stride=2,padding=1),nn.ReLU(),
            nn.Conv2d(32,32,3,padding=1),nn.ReLU(),nn.Conv2d(32,11,(8,1)))

    def forward(self,x):return self.layers(x)


def load(path):
    checkpoint=torch.load(path,map_location='cpu',weights_only=True)
    if checkpoint['architecture']!='score-conv-ctc-v1':raise ValueError('checkpoint architecture mismatch')
    model=ScoreNet();model.load_state_dict(checkpoint['state_dict']);model.eval()
    return model,checkpoint


def export(path,output):
    import onnx
    import onnxruntime as ort
    import numpy as np
    model,record=load(path);sample=torch.linspace(0,1,int(np.prod(INPUT))).reshape(INPUT)
    torch.onnx.export(model,sample,str(output),input_names=['images'],output_names=['logits'],
        opset_version=11,do_constant_folding=True,dynamic_axes=None)
    graph=onnx.load(output);onnx.checker.check_model(graph)
    operators=sorted({n.op_type for n in graph.graph.node})
    if set(operators)-{'Conv','Relu'}:raise ValueError('unexpected compiler operators')
    session=ort.InferenceSession(str(output),providers=['CPUExecutionProvider'])
    with torch.no_grad():reference=model(sample).numpy()
    actual=session.run(['logits'],{'images':sample.numpy()})[0]
    assert actual.shape==OUTPUT and np.allclose(actual,reference,atol=1e-5,rtol=1e-4)
    return dict(operators=operators,input_shape=list(INPUT),output_shape=list(OUTPUT),
        input_node='images',output_node='logits',onnx_nodes=[n.name for n in graph.graph.node],
        maximum_absolute_error=float(abs(actual-reference).max()),onnxruntime_checked=True,
        hailo_compilation='UNVERIFIED',qualification=record['qualification'])
