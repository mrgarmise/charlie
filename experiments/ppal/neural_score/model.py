"""Fixed Conv/Relu only inference graph; CTC/string processing stays on CPU."""
import torch
from torch import nn
from .contract import INPUT,OUTPUT,PREPROCESS


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
    from pathlib import Path
    if Path(output).exists():raise FileExistsError('preserve existing ONNX artifact')
    import onnx
    import onnxruntime as ort
    import numpy as np
    model,record=load(path);sample=torch.linspace(0,1,int(np.prod(INPUT))).reshape(INPUT)
    torch.onnx.export(model,sample,str(output),input_names=['images'],output_names=['logits'],
        opset_version=11,do_constant_folding=True,dynamic_axes=None,dynamo=False)
    from .compile import validate_graph
    graph=validate_graph(output)
    for key,value in (('charlie.preprocessing',record.get('preprocessing',PREPROCESS)),
                      ('charlie.dataset_digest',record['dataset_digest'])):
        item=graph.metadata_props.add();item.key=key;item.value=value
    onnx.save(graph,output);onnx.checker.check_model(graph)
    operators=sorted({n.op_type for n in graph.graph.node})
    if set(operators)-{'Conv','Relu'}:raise ValueError('unexpected compiler operators')
    session=ort.InferenceSession(str(output),providers=['CPUExecutionProvider'])
    with torch.no_grad():reference=model(sample).numpy()
    actual=session.run(['logits'],{'images':sample.numpy()})[0]
    assert actual.shape==OUTPUT and np.allclose(actual,reference,atol=1e-5,rtol=1e-4)
    return dict(operators=operators,input_shape=list(INPUT),output_shape=list(OUTPUT),
        opset_imports={x.domain:x.version for x in graph.opset_import},exporter='torch.onnx legacy; dynamo=False',
        input_node='images',output_node='logits',onnx_nodes=[n.name for n in graph.graph.node],
        maximum_absolute_error=float(abs(actual-reference).max()),onnxruntime_checked=True,
        hailo_compilation='UNVERIFIED',qualification=record['qualification'])


def reexport(checkpoint,training_record,output):
    """Export identical saved weights into a new integrity-tracked directory."""
    import json
    import shutil
    from pathlib import Path
    from .contract import sha
    checkpoint=Path(checkpoint);training_record=Path(training_record);output=Path(output)
    previous=json.loads(training_record.read_text());_,state=load(checkpoint)
    if previous['checkpoint_sha256']!=sha(checkpoint) or previous['dataset_digest']!=state['dataset_digest']:
        raise ValueError('original training record/checkpoint mismatch')
    output.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(checkpoint,output/'score.pt')
    report=export(checkpoint,output/'score.onnx')
    record=dict(previous,onnx_sha256=sha(output/'score.onnx'),export=report,
        source_training_record_sha256=sha(training_record),source_onnx_sha256=previous['onnx_sha256'],
        reexport=True,weights_retrained=False,hef_created=False,hardware_validated=False)
    (output/'training.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser(description='Re-export existing weights as checked static opset-11 ONNX in a new directory')
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--training-record',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(reexport(args.checkpoint,args.training_record,args.output),indent=2))
