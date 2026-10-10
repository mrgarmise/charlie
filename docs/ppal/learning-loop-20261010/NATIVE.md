# Native continuation gate

No installation, service replacement or physical execution is authorized. Native Pi access from the Work environment fails hostname resolution. These are unarmed validation instructions for the existing Pi, not a deployment command.

Use an isolated worktree at the implementation SHA shown in the final validation report. Preserve the current checkout and notebooks. Do not run the firmware tools or any `--arm` command.

```bash
cd /home/five/charlie-ala2-bae659f60b0e
git fetch origin feature/agency-first-self
# Pinned implementation checkpoint validated on the host:
git worktree add --detach /home/five/charlie-learning-loop-validation 72b3ce5a42f74fa41d8e25a50805636efeca7ea9
cd /home/five/charlie-learning-loop-validation
git rev-parse HEAD
uname -a
python3 --version
vcgencmd measure_temp
nice -n 10 python3 -m pytest -q tests --junitxml=/home/five/charlie-learning-loop-tests.xml
```

Use the existing native Python test environment if system Python lacks dependencies. Record its absolute path and versions. Do not treat Torch skips as proof of Torch-dependent functionality. Allow the Pi to cool and retain output if existing resource limits require interruption.

Before native developmental continuation, preserve a consistent backup of the existing development directory using the established notebook backup process. Do not overwrite originals or a prior backup. The normal offline lifecycle's exclusive lock must be available; if another learning process owns it, defer instead of bypassing the lock. Confirm no authorized physical game is running.

```bash
nice -n 10 python3 main.py --offline \
  --learning-state /home/five/.local/share/charlie/development \
  --episode-root /home/five/Projects/charlie/robotron-runs \
  --learning-turns 3 --learning-budget 2 --learning-interval 0.05
# Repeat the exact command for restart/idempotence validation.
```

Return the test XML/log, exact revision/environment/temperature, original and resulting journal counts/hashes, and `development-status.json`. The status must retain original project identities, source deficiencies and staged permissions. No Guide output, candidate activation, camera acquisition, servo command or firmware write is expected from this offline command. If originals exist, acquisition should inspect them autonomously, and changed or corrupt inputs must be retained as deficiencies rather than converted into qualification.

A proposal is a request, not approval. Native preflight must bind the current revision, baseline hash, camera/calibration and controller configuration before a specific trial is approved. The staged temporal proposal's complete-game baseline collection and listed offline shadows require separate approval; persistent policy activation, movement and flashing remain outside it. The current release has no new experiment-specific physical approval consumer. Do not substitute a general `--arm` invocation for that missing binding.

ALA-2 acceptance remains open until independently measured complete-game Robotron SCORE improves against the frozen baseline through Charlie-originated learning.
