# Camera demonstration and offline verification

Use a new database for the demonstration. The command prints an exported simulation-only JSON skill candidate.

```sh
DB=$(mktemp)
OPENBLAS_NUM_THREADS=1 python -m research.uel.camera_demo "$DB" --revision "$(git rev-parse HEAD)"
python -m research.uel.camera_demo "$DB" --revision "$(git rev-parse HEAD)" --replay
OPENBLAS_NUM_THREADS=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m research.uel.verify_offline
```

The fitted horizontal response was -19.32 pixels per unit of amber command, with +1.87 pixels per unit of jade command. A previously unseen +0.55 amber command challenged the direction on three held-out seeds. The opposite sign prediction failed a 2 px tolerance. The nominal control demonstration finished at the requested pixel in all three seeds. The independent unit tests compare the learned controller to a naive controller and stop on occlusion. The export references the model, training trials, holdout trials and control trajectories in the database. Scope is limited to the nominal twin manifest.

The verification script denies Python socket audit events. Host policy denied creation of a network namespace, so process-level network isolation was unavailable. Replay uses the UEL database only. Physical pan/tilt source logs were not used.
