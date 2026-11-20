"""Stable operator entry point, also safe to re-import in multiprocessing spawn."""
from pathlib import Path
import sys

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.runtime_adoption.stationary import main
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as error:
        sys.exit('Stationary transaction refused: ' + str(error))

elif __name__ == '__mp_main__':
    # The spawned Executive receives no camera, serial link or network grant.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.runtime_adoption.stationary_boundary import install
    sys.path.pop(0)
    install()
