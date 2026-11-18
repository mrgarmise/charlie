# Synthetic benchmark results

Run `OPENBLAS_NUM_THREADS=1 python -m research.uel.benchmark` from the Charlie checkout root. The frozen plan precedes the benchmark in local development history. All rows are in benchmark_results.json.

| Setting | Active MAE | Random MAE | Zero-response MAE | Active RMSE | Active interval coverage | Active regressions |
|---|---:|---:|---:|---:|---:|---:|
| Coupled | 0.02379 | 0.02524 | 0.61729 | 0.02941 | 91.35% | 6/20 |
| Scalar | 0.02457 | 0.02484 | 0.40481 | 0.02971 | 87.50% | 9/20 |

Paired MAE gain intervals were [0.000168, 0.002717] and [-0.000751, 0.001306], respectively. Both settings passed the zero-response improvement gate. The scalar gain over random probing was inconclusive. Prediction intervals undercovered relative to their nominal 95% level. The benchmark used equal budgets and did not establish a reduction in trials to a fixed accuracy. Local x86-64 benchmark measured 0.16 seconds elapsed, 0.32 seconds process CPU including startup, and peak RSS of 24,504 KiB. No Pi measurements were made.
