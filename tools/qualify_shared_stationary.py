"""Foreground candidate qualification with a copy of the Batch A notebook."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def qualify():
    import argparse
    import os
    import shutil
    import tempfile
    from tools.runtime_adoption import stationary as s
    from tools.runtime_adoption.shared_profile import run
    from tools.runtime_adoption.supervised_release import confirm_isolation, foreground

    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('revision')
    parser.add_argument('--display', action='store_true')
    args = parser.parse_args()
    ctl = s.Stationary(Path.home())
    s.require(sys.flags.isolated and sys.dont_write_bytecode and
              set(os.environ) <= {'HOME', 'PATH', 'LC_CTYPE'} and
              os.environ.get('PATH') == '/usr/bin:/bin' and
              Path(sys.prefix) == Path('/home/five/Projects/charlie/.venv'),
              'use the isolated, sanitized Pi interpreter')
    foreground()
    with s.locked(ctl.ops):
        s.require(s.git(ROOT, 'rev-parse', 'HEAD') == args.revision and
                  not s.git(ROOT, 'status', '--porcelain', '--untracked-files=all'),
                  'candidate revision or checkout differs')
        confirm_isolation()
        s.qualification_preflight(ctl, s.selection(ctl.normal))
        models = s.load(ctl.models)
        # Match the existing release controller's relative HEF path resolution.
        os.chdir(ctl.new)
        source = ctl.ops / 'batch-a-state'
        s.require(not any(path.is_symlink() for path in source.rglob('*')),
                  'qualification state contains a redirected path')
        trial = Path(tempfile.mkdtemp(prefix='shared-', dir=ctl.ops / 'promotion-backups'))
        state = trial / 'state'
        shutil.copytree(source, state)
        print('Isolated qualification state:', state, flush=True)
        with s.session_guard(ctl, set(), owner_approval='shared-qualification-' + args.revision):
            run(state, ctl.models, models.get('stream_url') or 'http://192.168.4.1:81/stream',
                display=args.display, summary=trial / 'owner-summary.json')
            s.idle_guard()
            s.device_guard()
            s.require(s.sha(ctl.normal) == s.ORIGINAL, 'canonical launcher changed')


if __name__ == '__main__':
    qualify()
elif __name__ == '__mp_main__':
    from tools.runtime_adoption.shared_profile import SESSION
    from tools.runtime_adoption.stationary_boundary import install
    install(recognition_connect=str(SESSION / 'recognition.sock'))
