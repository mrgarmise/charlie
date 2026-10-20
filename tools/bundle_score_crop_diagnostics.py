"""Copy existing TRAINING artifacts/originals into a new portable diagnostics bundle.

No review database writer, training, camera or device. Original corpus bytes and
relative crop paths are preserved. Reserved evaluation images are not copied.
"""
import argparse
import json
from pathlib import Path
import shutil
import tarfile
from experiments.ppal.neural_score.contract import sha
from experiments.ppal.neural_score.corpus import verify,image_path
from experiments.ppal.neural_score.diagnose import _original
from experiments.ppal.eyes.calibration import Calibration
from memory.evidence import digest


def bundle(manifest,model_directory,calibration,review_export,output):
    manifest=Path(manifest);model_directory=Path(model_directory);output=Path(output)
    record=verify(manifest)
    if not record['rows'] or any(r['role']!='train' for r in record['rows']):
        raise ValueError('only a frozen training-only corpus may be bundled')
    cal=Calibration.load(Path(calibration))
    geometry=digest(dict(corners=cal.corners,output_size=cal.output_size))
    training=json.loads((model_directory/'training.json').read_text())
    if training['dataset_digest']!=record['digest']:raise ValueError('model/corpus mismatch')
    for name,key in (('score.pt','checkpoint_sha256'),('score.onnx','onnx_sha256')):
        if sha(model_directory/name)!=training[key]:raise ValueError('model artifact hash mismatch')
    originals={}
    for row in record['rows']:
        name=Path(row['image'])
        if name.is_absolute() or '..' in name.parts:raise ValueError('portable crop paths must remain inside corpus directory')
        context=(row.get('source_proposal') or {}).get('context',{})
        if context.get('calibration_geometry_digest')!=geometry:raise ValueError('exact original calibration required')
        originals[row['source_image_sha256']]=_original(row,review_export)
    archive=output.with_suffix('.tar.gz')
    if output.exists() or archive.exists():raise FileExistsError('bundle destination must be new')
    output.mkdir(parents=True)
    corpus_out=output/'corpus';corpus_out.mkdir()
    shutil.copyfile(manifest,corpus_out/'manifest.json')
    ledger=manifest.parent/'score-corpus-ledger.jsonl'
    if ledger.is_file():shutil.copyfile(ledger,corpus_out/ledger.name)
    for row in record['rows']:
        target=corpus_out/row['image'];target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(image_path(manifest,row),target)
    model_out=output/'model';model_out.mkdir()
    for name in ('score.pt','score.onnx','training.json'):shutil.copyfile(model_directory/name,model_out/name)
    shutil.copyfile(calibration,output/'calibration.json')
    raw_out=output/'originals';images=raw_out/'images';images.mkdir(parents=True)
    mapping={}
    for key,path in originals.items():
        target=images/(key+path.suffix.lower());shutil.copyfile(path,target)
        if sha(target)!=key:raise ValueError('copied original hash mismatch')
        mapping[key]=str(target.relative_to(raw_out))
    (raw_out/'image-locations.json').write_text(json.dumps(mapping,indent=2)+'\n')
    receipts=dict(scope='existing training artifacts and originals only; no new labels',
        manifest_digest=record['digest'],manifest_sha256=sha(manifest),training_images=len(record['rows']),
        originals=len(originals),reserved_evaluation_included=False,originals_modified=False,
        file_sha256={str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    (output/'bundle.json').write_text(json.dumps(receipts,indent=2)+'\n')
    with tarfile.open(archive,'x:gz') as stream:stream.add(output,arcname=output.name)
    return dict(archive=str(archive),archive_sha256=sha(archive),**receipts)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--model-directory',type=Path,required=True)
    p.add_argument('--calibration',type=Path,required=True);p.add_argument('--review-export',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(bundle(a.manifest,a.model_directory,a.calibration,a.review_export,a.output),indent=2))


if __name__=='__main__':main()
