# Environment and baselines

- Clean Charlie source clone at `57e07eb850b139eda6a5f1a930cc0ef7b5bf5f18` (master, PR #39 source integration). The published source tip and the approved Pi runtime are distinct records. This workspace has no access to the runtime checkout or qualification record on the Pi.
- Clean Dog simulator source at `2d6af9192a69868454f260e8cb3851c98727e623` on `research/fnk0050-sim-20261112`. Dog main is `38ca17d8a1799b51c207f0a8cec3a16b28e46931` and lacks that simulator.
- Charlie architecture and conformance docs place acquisition and actuator authority under existing owners. UEL lives under research and imports no Charlie operational modules or transports.
- Dog integration uses `research/fnk0050-sim/mujoco_env.py` and its existing model.
