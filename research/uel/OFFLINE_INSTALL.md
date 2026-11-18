# Offline install

The A-stage CLI and journal need only Python 3.12 and its SQLite module. Later stages use NumPy 2.3.5 as tested. On a connected machine matching the target Python ABI and architecture, cache NumPy using `python -m pip download --only-binary=:all: --dest wheelhouse numpy==2.3.5`. Transfer the pinned checkout and wheelhouse, then install in an isolated venv with `python -m pip install --no-index --find-links wheelhouse numpy==2.3.5`. Use an aarch64 wheelhouse for a Pi. Set OPENBLAS_NUM_THREADS=1 to bound this linear algebra backend's parallelism.

The 100-trial synthetic CLI database occupied 73,728 bytes on the development host. Its default SQLite database ceiling is approximately 250 MB. The benchmark used 24,504 KiB peak RSS. These are host measurements. Pi wheel footprint, thermal and power measurements remain open. No model weights are required and the offline knowledge archive is outside the research footprint.
