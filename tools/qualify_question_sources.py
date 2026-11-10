"""Read-only authentic-source selection proof; no model or hardware calls."""
import argparse
import json
from learning.question_selection import discover, fingerprint, context_for


def qualify(paths):
    before={str(p):fingerprint(p) for p in paths}
    report=discover(paths)
    if report['errors'] or report['truncated']:raise ValueError('incomplete source reconciliation')
    contexts=[]
    for item in report['candidates']:
        prompt=context_for(item)
        contexts.append(dict(question_id=item['question_id'],candidate_id=item['id'],
            sources=item['sources'],committed_at=item['committed_at'],method=item['method'],
            scope=item['scope'],eligible=item['eligible'],reasons=item['reasons'],
            prompt_version=prompt['version'],prompt_digest=prompt['digest'],prompt_bytes=len(prompt['text'].encode())))
    after={str(p):fingerprint(p) for p in paths}
    if before!=after:raise ValueError('source changed')
    return dict(schema='question-source-qualification-v1',source_fingerprints=before,
                original_journals_unchanged=True,model_calls=0,candidates=contexts)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',action='append',required=True)
    a=p.parse_args();print(json.dumps(qualify(a.source),indent=2))

if __name__=='__main__':main()
