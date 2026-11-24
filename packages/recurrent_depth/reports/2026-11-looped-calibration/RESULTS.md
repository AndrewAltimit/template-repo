# Calibration Results

Results against [PREDICTIONS.md](PREDICTIONS.md), added tier by tier. Tier 1 (GPU) and tier 3 (GLM-5.x) have not run yet.

## Tier 0: config and weight inspection (2026-11-23, local CPU, $0)

Campaign `campaigns/calibration/tier0-local.json`, run id `tier0-20261123`. All 16 stages completed in 5.5 minutes: 10 downloads of pinned revisions, 5 config inspections, 2 weight inspections. No model code ran.

### C1. Config inspection: holds

| Model | Model type | Declares looping | Stored layers | Logical depth | Outcome |
|---|---|---|---|---|---|
| Huginn-0125 | `huginn_raven` | yes | 8 | 132 (2 + 4 x 32 + 2) | 1.0 |
| Ouro-1.4B | `ouro` | yes | 24 | 96 (24 x 4) | 1.0 |
| Ouro-2.6B | `ouro` | yes | 48 | 192 (48 x 4) | 1.0 |
| SmolLM2-1.7B | `llama` | no | 24 | 24 | 0.0 |
| Qwen3-1.7B-Base | `qwen3` | no | 28 | 28 | 0.0 |

**A toolkit bug found along the way.** The first pass flagged both Ouro models as having adaptive exit. Their `early_exit_threshold` of 1.0 actually disables it: every step always runs. `inspect-config` now treats exit thresholds of 1.0 or above as disabled and says so in its notes. This table is from the corrected parser.

### C2. Weight inspection: holds (the blind spot is real)

| Model | Loops | Layers compared | Shared layers | Weight reuse ratio | Adjacent-layer relative distance |
|---|---|---|---|---|---|
| Ouro-1.4B | yes, 4 steps | 24 | 0 | 1.0 | 1.32 to 1.41 |
| SmolLM2-1.7B | no | 24 | 0 | 1.0 | 1.28 to 1.41 |

A model that runs its 24 layers four times stores them once. Its weights look the same as a fixed-depth model's on every statistic `inspect-weights` computes. That is why the decision rule never lets unshared weights decide on their own. The calibration now confirms the rule on a real looped checkpoint, not only on synthetic ones.

Huginn and Ouro-2.6B weights are inspected in tier 1, where downloads are fast inside AWS.
