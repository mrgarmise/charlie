"""Entry point for the pinned shared-recognition release controller."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if __name__ == '__main__':
    from tools.runtime_adoption.shared_release import main
    main()
elif __name__ == '__mp_main__':
    sys.path.insert(0, '/home/five/charlie-shared-candidate')
    from tools.runtime_adoption.shared_profile import SESSION
    from tools.runtime_adoption.stationary_boundary import install
    install(recognition_connect=str(SESSION / 'recognition.sock'))
