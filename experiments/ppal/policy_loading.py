"""Startup-only qualified policy discovery; never called by the tactical loop."""
import os
from pathlib import Path
import sqlite3


def load_startup_policy(path=None, *, physical=False):
    if path is None:
        state=os.environ.get('CHARLIE_LEARNING_STATE')
        if state:
            candidate=Path(state)/'ppal-policy.json'
            if candidate.is_file():path=candidate
    if path is None:return None,None
    try:
        from .qualified_policy import load_policy
        return load_policy(path,physical=physical),None
    except (OSError,ValueError,KeyError,TypeError,RuntimeError,sqlite3.Error) as exc:
        error=f'{type(exc).__name__}: {exc}'
        print('LEARNED POLICY UNAVAILABLE: '+error+'; baseline retained')
        return None,error
