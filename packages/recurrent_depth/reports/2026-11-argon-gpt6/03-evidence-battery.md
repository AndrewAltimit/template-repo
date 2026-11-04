# Recurrent-Depth Evidence Battery: Gemini 4 Argon and the GPT-6 Family

**Date:** 2026-11-03
**Branch:** `feat/recurrent-depth-budget-sweep`
**Predictions:** [PREDICTIONS.md](PREDICTIONS.md), written before data collection. P7 was added after R1 to R4 had started but before any results were examined. One deviation: P3 was replaced (see Deviations).
**Follows:** [01-timing-probe.md](01-timing-probe.md) (timing probe) and [02-budget-sweep.md](02-budget-sweep.md) (budget sweep)
**Spend:** about $11.60 for this battery, about $15 for the whole investigation

## Bottom line

**Gemini 4 Argon: still inconclusive on architecture, but Argon now has the strongest no-reasoning serial capability of every model we can measure, on every probe.** By the pre-registered decision rule it is not "consistent with looping": Argon does not solve long chains efficiently when it does reason (P3 replacement), and the timing replication (P5) shows no adaptive compute. Only P5 gives its "against" outcome, and it rules out adaptive looping only, so the rule's threshold for "against" (two probes) is not met.

The primary sources pull in different directions:
- Google describes Argon as "a large scale sparse mixture-of-experts (MoE) transformer-based model" and "not a modification or a fine-tune of a prior model". It attributes Argon's gain to about 5.5 serial arithmetic steps per forward pass, up from 4.2 for Gemini 3.8 Flash, to better pretraining.
- A looped MoE transformer would still fit that description, so the model card neither confirms nor rules out looping.

**GPT-6 family: the evidence splits by tier.**
- **Terra tier:** GPT-6.1 Terra differs from GPT-5.6 Terra on four separate probes, each in the direction looping predicts:
  - serial arithmetic steps without reasoning: 11.6 vs 5.4, non-overlapping intervals;
  - two-hop composition: 0.88 vs 0.77;
  - long-chain horizon: 4 vs none;
  - decode time per token: 10.9 vs 8.1 ms.
- **Luna tier:** GPT-6 Luna differs from GPT-5.6 Luna only on two-hop composition (0.85 vs 0.61). Serial arithmetic (4.0 vs 4.3), the long-chain horizon (both at floor) and decode time per token (7.3 vs 7.6 ms) are unchanged.

So the data fit a change in the GPT-6.1 Terra tier (and GPT-6.1 Sol, see P6) more than in GPT-6 Luna, which argues against "the whole family shares the architectural change". OpenAI's addenda say GPT-6.1 Sol and Terra use "the same types of data and training as GPT-6 Astra", which is consistent with this but is not an architecture statement.

## Results against the predictions

### P1. Long-chain horizon, reasoning off (R1: 3 long tasks x 8 depths from 4 to 128 x 8 reps per model)

| Model | Corrected accuracy at depth 4 / 8 / 16 / 32 | Horizon (accuracy at least 0.5) | Log-depth slope |
|---|---|---|---|
| **Gemini 4 Argon** | **1.00 / 0.67 / 0.22 / 0.24** | **8** | -0.21 +/- 0.03 |
| GPT-6.1 Terra | 0.71 / 0.29 / -0.15 / 0.05 | 4 | -0.11 +/- 0.03 |
| GPT-5.6 Sol | 0.48 / 0.02 / -0.12 / 0.13 | none | -0.04 +/- 0.03 |
| GPT-5.6 Terra | 0.12 / 0.08 / -0.15 / 0.07 | none | -0.01 +/- 0.03 |
| GPT-6 Luna | 0.10 / 0.10 / 0.07 / 0.08 | none | -0.02 +/- 0.03 |
| GPT-5.6 Luna | 0.07 / -0.06 / -0.17 / 0.19 | none | 0.01 +/- 0.03 |
| Kimi K2.6 | 0.29 / 0.27 / 0.16 / 0.00 | none | -0.09 +/- 0.03 |
| DeepSeek V4 Pro | -0.09 / 0.27 / -0.19 / 0.00 | none | 0.01 +/- 0.03 |

- **The long chains were too hard.** Every model is at chance by depth 16 to 32, so depths 32 to 128 carry no information. The ladder should have started at 1. The usable range is depths 4 and 8.
- **Terra pair:** consistent with the looped prediction (horizon 4 vs none).
- **Luna pair:** uninformative (both at floor).
- **Argon:** consistent with its prediction (horizon 8, at least one step beyond GPT-5.6 Sol). It is the only model that solves 8-step permutation tracking (1.00) and 16-step reachability (0.75) without reasoning.

### P7. Serial arithmetic steps at 50% (R6: 1 to 12 dependent steps, 10 reps per depth, logistic fit)

| Model | Steps at 50%, reasoning off (95% CI) | With 128 filler tokens | Filler compliance |
|---|---|---|---|
| **Gemini 4 Argon** | **15.3 (11.9 to 22.3)**, beyond the measured range: still 0.7 accurate at 12 steps | not estimable (no decline) | 1.00 |
| GPT-6.1 Terra | 11.6 (9.8 to 14.1) | 12.1 (10.7 to 14.4) | 1.00 |
| GPT-5.6 Sol | 6.3 (5.5 to 7.3) | **10.4 (9.1 to 12.5)** | 0.99 |
| GPT-5.6 Terra | 5.4 (4.6 to 6.2) | 4.5 (3.6 to 5.4) | 0.70 |
| DeepSeek V4 Pro | 4.6 (3.9 to 5.4) | 6.0 (5.2 to 6.7) | 0.99 |
| GPT-5.6 Luna | 4.3 (3.7 to 5.0) | n/a | 0.00 |
| GPT-6 Luna | 4.0 (3.4 to 4.6) | n/a | 0.00 |
| Kimi K2.6 | 3.6 (3.1 to 4.1) | n/a | 0.00 |

- **Our task is easier per step than Google's**, so the absolute numbers are not comparable to Google's 5.5 for Argon. The ranking is what transfers, and Argon tops it.
- **Terra pair:** consistent with the looped prediction (+6.2 steps, non-overlapping intervals).
- **Luna pair:** against it (-0.3 steps).
- **No hidden scaling.** Billed tokens are constant across depth on every closed model (about 4 to 5 tokens of overhead, against 1 to 2 for DeepSeek). Argon's time to first token is flat at about 3 s from 1 to 12 steps, so the extra serial capability is not coming from extra hidden tokens on harder items.

### P4. Latent two-hop composition (R4: 150 TwoHopFact facts, reasoning off)

| Model | Hop 1 / hop 2 / two-hop accuracy | Composition rate (95% CI) | Two-hop when a hop is unknown |
|---|---|---|---|
| **Gemini 4 Argon** | 0.69 / 0.79 / 0.62 | **0.89 (0.80 to 0.94)** | 0.24 |
| GPT-6.1 Terra | 0.62 / 0.73 / 0.57 | 0.88 (0.78 to 0.93) | 0.27 |
| GPT-6 Luna | 0.57 / 0.67 / 0.51 | 0.85 (0.74 to 0.91) | 0.26 |
| GPT-5.6 Sol | 0.64 / 0.75 / 0.56 | 0.84 (0.74 to 0.91) | 0.27 |
| GPT-5.6 Terra | 0.56 / 0.69 / 0.44 | 0.77 (0.66 to 0.86) | 0.21 |
| DeepSeek V4 Pro | 0.59 / 0.73 / 0.51 | 0.73 (0.62 to 0.82) | 0.32 |
| Kimi K2.6 | 0.62 / 0.73 / 0.45 | 0.71 (0.60 to 0.80) | 0.21 |
| GPT-5.6 Luna | 0.53 / 0.65 / 0.43 | 0.61 (0.49 to 0.72) | 0.30 |

- **Luna pair:** +0.24, z = 3.1, non-overlapping intervals.
- **Terra pair:** +0.10, z = 1.6.
- Both pairs meet the pre-registered "consistent with looping" criterion. Argon ties GPT-6.1 Terra at the top.
- About 25% of two-hop questions are answered correctly even when a single hop is missed. That baseline (guessing, or shortcuts from the first entity) is similar across models.

### P2. Filler tokens (R3: long tasks at depths 8 and 16; R6: arithmetic)

- **No model meets the pre-registered "finding of interest" on the long tasks** (a gain of at least 0.10 with at least 70% compliance at z of at least 2). GPT-6.1 Terra at f512 comes closest (+0.21, z = 1.7, 88% compliant).
- **On arithmetic (R6), GPT-5.6 Sol gains 4 steps from 128 filler tokens** (6.3 to 10.4, non-overlapping intervals), and DeepSeek V4 Pro gains 1.4. That is hidden computation without legible content, consistent with Greenblatt's finding that recent models can use filler tokens.
- **Argon gains nothing measurable**, matching Google's report of a small filler uplift (2 NCRI points). GPT-6.1 Terra also gains nothing (11.6 to 12.1).
- **Compliance is itself a finding.** Both Luna models and Kimi K2.6 could not stop emitting periods at 128 or 512 (0% compliance). GPT-5.6 Sol could not at 512.

### P3 (replaced). Reasoning on long chains at medium effort (R2)

| Model | Accuracy at depth 8 / 32 / 64 / 128 | Tokens per step | Decode ms per token (P6) |
|---|---|---|---|
| GPT-6 Astra | 1.00 / 1.00 / 0.92 / 1.00 | 8.5 +/- 1.9 | 21.6 +/- 1.0 |
| GPT-6.1 Sol | 1.00 / 1.00 / 1.00 / 1.00 | 5.9 +/- 1.1 | 11.5 +/- 0.6 |
| GPT-5.6 Sol | 1.00 / 1.00 / 1.00 / 0.92 | 9.4 +/- 2.1 | 6.7 +/- 0.2 |
| GPT-6.1 Terra | 1.00 / 1.00 / 1.00 / 1.00 | 5.6 +/- 1.2 | 10.9 +/- 0.2 |
| GPT-5.6 Terra | 1.00 / 1.00 / 1.00 / 0.83 | 6.5 +/- 1.0 | 8.1 +/- 0.3 |
| GPT-6 Luna | 1.00 / 1.00 / 0.92 / 0.92 | 12.1 +/- 6.0 | 7.3 +/- 0.2 |
| GPT-5.6 Luna | 1.00 / 1.00 / 1.00 / 0.83 | 10.3 +/- 3.3 | 7.6 +/- 0.2 |
| **Gemini 4 Argon** | **0.75 / 0.50 / 0.25 / 0.42** | 2.8 +/- 1.4 | 10.9 +/- 0.3 |

- **Argon under-reasons at medium effort.** It spends only 90 to 400 tokens on chains up to 128 steps and falls to near chance. It is not efficient, it just stops early. The looped prediction (high accuracy at no more than about 5 tokens per step) is not met. The pre-registered "against" outcome (at least 8 tokens per step) is not met either, because Argon never spends enough tokens to solve these chains. Result: uninformative, and it does not support looping.
- **P6 (decode time per token).**
  - GPT-6.1 Sol decodes 1.7x slower per token than GPT-5.6 Sol, and GPT-6.1 Terra 1.35x slower than GPT-5.6 Terra. GPT-6 Luna matches GPT-5.6 Luna. Astra is slowest of all (21.6 ms).
  - This matches the per-tier split above. Model size and serving hardware are unknown, though, and GPT-6.1 Sol is listed at half GPT-5.6 Sol's price, which makes "more compute per token" harder to reconcile. This is weak evidence.

### P5. Timing replication

Three load windows about 90 minutes apart. Argon at minimal effort, depth 1 versus 12, 20 reps per cell (160 requests per window), with Llama 3.3 70B (fixed depth) run in parallel in each window. Positive z means TTFT rises with depth.

| Window (UTC) | Argon TTFT slope z | Llama 3.3 70B TTFT slope z |
|---|---|---|
| W1 (22:59 to 23:10) | -0.73 | -1.05 |
| W2 (00:40 to 00:50) | +1.61 | +2.38 |
| W3 (02:20 to 02:29) | +0.94 | -0.56 |
| Pooled (480 requests) | +1.34 | +0.41 |

- **Result: no adaptive looping, by both pre-registered criteria.** The adaptive outcome needed z of at least 2 in every window and a pooled z of at least 3. No window reaches 2, and W1 is negative. The pooled |z| of 1.34 is below 2, and the window signs disagree.
- **W2 is load-confounded.** The fixed-depth reference reached |z| of at least 2 there, so Argon's +1.61 in that window is more likely server load than depth.
- **The weak positive tilt is not evidence of looping.** Argon's pooled slope is positive but well under the threshold, and most of it comes from W2, the load-confounded window. Requests that reported reasoning tokens (3 or 4 per window) are excluded from the slope.
- This replicates round 1, where a z of +2.37 in run 1 did not hold in run 2 (-1.50).

## Published evidence (checked against the sources)

| Source | Statement |
|---|---|
| Gemini 4 Argon model card | "Gemini 4 Argon is a large scale sparse mixture-of-experts (MoE) transformer-based model"; "is not a modification or a fine-tune of a prior model." No mention of recurrence or looping. |
| Gemini 4 Argon Safety & Security Report, sec. 3.4.5.3 (pp. 116 to 118) | "We estimate that with 50% probability it can do 5.5 steps of arithmetic in a single forward pass, compared to 4.2 for Gemini 3.8 Flash and 3.6 for Gemini 3.1 Pro." NCRI 150.3 (152.1 with filler). Gains are framed as coming from improved "pretraining quality." Argon "seems to benefit much less from filler tokens than other models." |
| GPT-6 Astra system card, sec. 9 | "We are also quite confident that changes in CoT controllability are not differentially due to any architectural changes." |
| GPT-6 Astra system card, sec. 9.3 (UK AISI) | "a greatly increased ability to reason within a single forward-pass"; no-CoT time horizon "30.9 minutes compared to 3.6 minutes for GPT 5.6 Sol." |
| GPT-6.1 Sol and Terra addenda (via the compilation) | Each "uses the same types of data and training as GPT-6 Astra." |
| Pachocki (X, 2026-09-02, via secondary sources; the post itself was not retrievable) | Depth "within a factor of two of GPT-4." |

The full compilation, with units kept separate per lab, is in [published-evals.md](published-evals.md). Two caveats:
- **The Tunçgenç post's "smoking gun" reading of serial depth** (depth beyond the layer count implies reuse) does not hold. 5.5 arithmetic steps per pass is far below the roughly 100 layers the post itself cites for frontier models.
- **Neel Nanda's estimate of 7.2 steps per pass for Astra**, and his view that looping is "highly likely", are secondary.

## Assessment

**Gemini 4 Argon.**
- **For looping:**
  - Argon leads every no-reasoning probe: long-chain horizon, arithmetic steps, two-hop composition (tied) and the earlier in-pass share (0.79).
  - Google's own numbers show a large jump in serial depth per pass over Gemini 3.8 Flash.
  - Argon gains little from filler, which fits computation that already happens internally rather than being unlocked by extra positions.
- **Against, or not supporting:**
  - Google describes a sparse MoE transformer and credits pretraining.
  - Argon's reasoning-on behavior is token-hungry or under-reasoned rather than efficient.
  - Its timing slope did not replicate in round 1, and P5 found no consistent slope across load windows.
  - Every no-reasoning advantage is confounded with Argon being a new flagship model compared mostly against smaller tiers.
- **Verdict:** inconclusive. If Argon is looped, the loops are not adaptive in any way visible through latency or tokens.

**GPT-6 family.**
- The pre-registered family-wide criterion (P1 and P4 favoring GPT-6 in both pairs) is met for P4 but not P1, where the Luna pair sits at floor.
- The strongest pattern: GPT-6.1 Terra (and GPT-6.1 Sol on decode time) differs from its predecessor on every probe, while GPT-6 Luna differs only on two-hop composition.
- That fits a looped or otherwise deeper design in the larger GPT-6 models, with Luna either not looped or too small to show it. It does not fit the claim that the whole family shares Astra's architecture.

## Deviations and limitations

- **P3 could not run as written.** OpenRouter did not enforce `reasoning.max_tokens` for these models in the pilot, so it was replaced by the medium-effort run on long chains (R2), documented in PREDICTIONS.md before analysis.
- **The R1 depth ladder was too hard** (floor from depth 16 for all models). A ladder from 1 to 16 would have separated the models better.
- **The closed models' "reasoning off" still bills about 4 to 5 hidden tokens.** These are constant across depth but could add a few fixed forward passes. Comparisons among closed models are like-for-like; comparisons with the open models are not.
- **Sample sizes are modest** (10 reps per arithmetic depth, 8 per long-chain cell, 150 two-hop facts per model), and each model was run once.
- **Astra and GPT-6.1 Sol** cannot disable reasoning, so P1, P4 and P7 have no data for them; UK AISI's no-CoT finding is the only no-reasoning evidence for Astra.

## What would settle it

Only inside evidence: weights, configs, per-iteration activations, or a lab statement. From outside, the next most informative steps are:

1. A shorter-depth long-chain ladder (1 to 16) with 20 reps.
2. A no-reasoning arithmetic task matched to Google's difficulty, so our Argon number can be checked against the reported 5.5.
3. A fixed-depth model of Argon's capability with reasoning fully off, as a reference.

## Toolkit changes on this branch (since the budget report)

- **New tasks:**
  - long-chain generators (`pointer_chase_long`, `permutation_long`, `reachability_long`, up to depth 128);
  - an `arithmetic_chain` generator modelled on the labs' steps-per-forward-pass measure.
- **Budget plans:**
  - filler-token conditions using space-separated periods, with compliance tracking. Contiguous periods compress to a handful of tokens, which the pilot caught;
  - a TwoHopFact suite (`twohop_csv`), with alias matching in `check_answer`.
- **New measures:**
  - `twohop-features` (latent composition rate with Wilson intervals);
  - `steps_at_50` (logistic fit with bootstrap);
  - `latency_per_token`.
- **Tests and checks:** about 140 tests pass, including a code-like alias field that must not execute. Ruff, bandit and ty are clean on the changed files; ty still reports two errors that predate this branch, in `hf_capture.py` and `safetensors_io.py`.

## Artifacts

Raw plans, per-request records, and analysis scripts are kept outside the repository (local `outputs/rds/battery/`, gitignored):

- `PREDICTIONS.md`: the pre-registered predictions
- `plans/`, `records/`, `logs/`: 38 plans and the per-request records for R1 to R6
- `analyze_battery.py` / `analysis.json`: every number in this report
- `run_battery.py`, `run_timing.sh`, `make_plans.py`: the runners and plan generator
- `data/twohopfact/`: the dataset copy (CC BY 4.0)
- `../safety_evals/COMPILATION.md`: published-evals compilation (copied here as [published-evals.md](published-evals.md)); the Google report PDF is not redistributed
