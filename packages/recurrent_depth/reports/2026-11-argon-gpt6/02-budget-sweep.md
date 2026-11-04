# Reasoning-Budget Sweep: How Load-Bearing Is Visible Reasoning?

**Date:** 2026-11-03
**Toolkit:** `packages/recurrent_depth` (new `budget-probe` / `budget-features`), branch `feat/recurrent-depth-budget-sweep`
**Follows:** [01-timing-probe.md](01-timing-probe.md) (timing probe, inconclusive)
**Access level:** Black box via OpenRouter. No raw chain of thought is visible for any closed model.

## Why this probe

The timing probe could not separate the reportedly looped GPT-6 models from fixed-depth references. It only detects *adaptive* recurrence, and a capped, fixed loop count looks like a deeper fixed model from outside. System cards report traits such as CoT controllability (GPT-6 Astra 60.9% versus GPT-5.6 Sol 16.1% in the 750 to 1,250 token bin), but measuring those needs the raw reasoning, which the API never returns.

This probe measures what an API customer can see instead: **how much a model's accuracy on serial tasks depends on its visible reasoning, and how many reasoning tokens it spends per serial step.** If serial work happens inside the forward pass (in loops, for example), accuracy should fall less without reasoning, and fewer tokens should be needed per step.

## Bottom line

1. **Within the OpenAI family, the newer models depend somewhat less on visible reasoning, but the gaps are inside the noise.** With reasoning off, GPT-6.1 Terra keeps 52% of its full-reasoning accuracy against 25% for GPT-5.6 Terra, and GPT-6 Luna keeps 45% against 38% for GPT-5.6 Luna. Both pairs move in the predicted direction, but the 95% intervals overlap.
2. **Token efficiency improved at the top of the GPT-6 family, not across it.** Astra and GPT-6.1 Sol spend about 5 to 6 reasoning tokens per serial step, against about 7 to 8.5 for GPT-5.6 Sol. GPT-6 Luna and GPT-6.1 Terra are no more efficient than their GPT-5.6 counterparts. This does not support the reading that the whole GPT-6 family shares the architectural change, at least as these tasks measure it.
3. **Gemini 4 Argon has the highest no-reasoning serial accuracy of any model measured** (in-pass share 0.79, 95% CI 0.66 to 0.91). This is consistent with substantial in-pass serial compute. But Argon is a flagship and is compared here mostly against smaller tiers, and when it does reason it is the *least* token-efficient closed model (about 10 tokens per step). So the evidence is suggestive in one direction and not in the other.
4. **The open fixed-depth references cannot calibrate this.** DeepSeek V4 Pro and Kimi K2.6 are near chance on every depth with reasoning off (in-pass share 0.04 and 0.09), and they bill 1 to 2 tokens per answer. Every closed model bills 5 tokens for a one-letter answer even with reasoning "off", so the closed models' no-reasoning mode carries about 3 to 4 hidden tokens that the open models lack.

**Effect on the Argon verdict:** this probe moves the picture slightly toward "Argon does more serial work per visible token than the comparison models" without making it decisive. The overall assessment stays **inconclusive**: the strongest Argon signal (no-reasoning accuracy) is the one most confounded by capability and by hidden tokens.

## Method

- **Tasks:** pointer chasing, S5 permutation tracking, prefix parity, graph reachability, at nominal depths 2, 8, 16, and 24, with 3 items per task and depth. The prompt asks for the final answer only, and any reasoning happens in the provider's reasoning channel.
- **Excluded items:** pointer chasing above depth 13 is removed from all results (see Toolkit changes: those items have a shorter backward route), and reachability at depth 24 cannot be generated. Depth 24 therefore contains only permutation and parity.
- **Sweep A (effort levels):** minimal, low, and medium on Astra, GPT-6.1 Sol, GPT-5.6 Sol, GPT-6 Luna, DeepSeek V4 Pro, and Argon. 135 requests each.
- **Sweep B (reasoning off versus medium):** on every model that allows reasoning to be disabled: GPT-6.1 Terra, GPT-5.6 Terra, GPT-6 Luna, GPT-5.6 Luna, GPT-5.6 Sol, DeepSeek V4 Pro, and Kimi K2.6. Argon's minimal and low settings already produce zero reasoning tokens, so its sweep-A data is used. Astra and GPT-6.1 Sol reject reasoning-off ("Reasoning is mandatory"), so they cannot appear here.
- **Metrics** (from `budget-features`, all on billed completion tokens):
  - `in_pass_share`: chance-corrected accuracy with reasoning off divided by that at medium, averaged over depths, with a 2,000-sample bootstrap 95% interval.
  - `tokens_per_step`: OLS slope of billed tokens on depth.
- **Totals:** about 1,600 requests, an estimated $2.00 at list prices, no errors, and no truncated responses.

## Results

### Tokens per serial step (sweep A, medium effort unless noted)

| Model | Tokens per step (slope, +/- se) | Accuracy at depth 24 | Notes |
|---|---|---|---|
| GPT-6 Astra | 5.8 +/- 0.7 (minimal 5.1) | 1.00 | Effort setting barely changes token use |
| GPT-6.1 Sol | 5.6 +/- 0.8 (minimal 5.3) | 0.83 | Same |
| GPT-6.1 Terra | 8.5 +/- 1.5 | 1.00 | Sweep B |
| GPT-5.6 Sol | 8.5 +/- 1.5 (minimal 8.0) | 1.00 | |
| GPT-5.6 Terra | 7.5 +/- 1.2 | 1.00 | Sweep B |
| GPT-6 Luna | 9.2 +/- 1.6 | 0.83 | |
| GPT-5.6 Luna | 9.5 +/- 1.9 | 1.00 | Sweep B |
| **Gemini 4 Argon** | **10.1 +/- 2.0** | **1.00** | Minimal and low use 0 reasoning tokens |
| DeepSeek V4 Pro | 40 +/- 11 | 1.00 | Open, 61 layers, MoE |
| Kimi K2.6 | 130 +/- 20 | 1.00 | Open, MoE |

At medium effort, every model reaches nearly 100% accuracy, so this table compares cost, not capability. Writing one full S5 state per step would take more than 5 tokens. At about 5 tokens per step, Astra and GPT-6.1 Sol are not spelling out each intermediate state, but neither are the other closed models by much.

On the OpenAI models, the effort setting has almost no effect on these tasks: minimal, low, and medium spend nearly the same tokens. The models choose their own reasoning length.

### Accuracy with reasoning off (sweep B)

| Model | In-pass share (95% CI) | Raw accuracy by depth 2 / 8 / 16 / 24, reasoning off | Billed tokens per answer |
|---|---|---|---|
| **Gemini 4 Argon** | **0.79 (0.66 to 0.91)** | 1.00 / 0.83 / 0.78 / 0.67 | 5 |
| GPT-5.6 Sol | 0.63 (0.45 to 0.89) | 1.00 / 0.50 / 0.67 / 0.50 | 5 |
| GPT-6.1 Terra | 0.52 (0.38 to 0.67) | 1.00 / 0.58 / 0.56 / 0.17 | 5 |
| GPT-5.6 Terra | 0.25 (0.06 to 0.51) | 0.58 / 0.50 / 0.56 / 0.17 | 5 |
| GPT-6 Luna | 0.45 (0.34 to 0.66) | 0.83 / 0.33 / 0.44 / 0.83 | 5 to 6 |
| GPT-5.6 Luna | 0.38 (0.25 to 0.59) | 0.75 / 0.25 / 0.56 / 0.83 | 5 |
| Kimi K2.6 | 0.09 (0.06 to 0.25) | 0.42 / 0.25 / 0.33 / 0.50 | 2 |
| DeepSeek V4 Pro | 0.04 (0.00 to 0.17) | 0.25 / 0.08 / 0.33 / 0.50 | 1 to 2 |

Chance is 0.5 for parity and reachability and 0.2 for permutation. Depth-24 cells contain only permutation and parity, which is why some models look better at 24 than at 16.

**Within-family pairs.** Terra: 0.25 to 0.52. Luna: 0.38 to 0.45. Both go up and both intervals overlap, so at 3 items per cell this is a direction, not a result. The GPT-6.1 Terra gain is concentrated at depth 2 (0.58 to 1.00) and at depth 8 on parity. At depth 24 both Terras sit at 0.17, below chance.

## Interpretation

- **What fits a looped architecture:** the newer OpenAI models lean slightly less on visible reasoning, and Astra and GPT-6.1 Sol are the most token-efficient models measured. Argon solves more serial problems with no reasoning than anything else.
- **What doesn't:** if every GPT-6 model shared Astra's loops, GPT-6 Luna and GPT-6.1 Terra should be more token-efficient than their predecessors, and they aren't. Argon, the strongest no-reasoning performer, is the least token-efficient once it reasons.
- **What confounds everything:**
  - *Capability.* Bigger and better-trained fixed-depth models also need less visible reasoning.
  - *Training for concise reasoning.* OpenAI markets GPT-6 as the token-efficient family, and token efficiency can be trained without any architecture change.
  - *The hidden 3 to 4 tokens* in every closed model's "no reasoning" mode.

Pachocki's statement that computation depth stays within a factor of two of GPT-4 also suggests that any loop effect on these tasks would be modest.

A cleaner test would need either a fixed-depth model of Argon's or Astra's capability that can run with zero hidden tokens, or longer serial chains (depth 50 to 100) where the in-pass difference between a looped and a fixed model should widen. The current generators cap out at 24.

## Toolkit changes on this branch

- **New `budget` module** with `budget-probe` and `budget-features` CLI commands:
  - plans with per-condition reasoning parameters and output caps (at most 16,384 tokens);
  - a total completion-token budget, separate from the request budget;
  - skipping of task and depth combinations a generator cannot produce;
  - `in_pass_share` with a bootstrap interval, `tokens_per_step`, `tokens_to_solve`, and truncation rates;
  - an `in_pass_share_valid` flag for when the lowest condition still reasons. The OpenAI models at minimal effort trigger it.
- **Client:** records `finish_reason`, so truncated reasoning is distinguishable from a wrong answer.
- **Task fix:** `pointer_chase` previously allowed depths up to 25 on a 26-letter cycle, and its docstring said there was no shortcut. But k steps forward equal 26 - k steps back, so depth 24 was a 2-step problem. Argon exploited this: its accuracy rose from 0.17 at depth 16 to 0.67 at depth 24 with no reasoning. Depth is now capped at 13. The timing probe's default depths (up to 12) were never affected.
- **Tests:** 126 pass, including new tests for plan guards, the token budget, truncation, in-pass versus load-bearing synthetic models, the validity flag, finish_reason capture, and the CLI. Ruff, bandit, and ty are clean.

## Artifacts

Raw plans, per-request records, and analysis scripts are kept outside the repository (local `outputs/rds/budget/`, gitignored):

- `plan_*.json`, `plan_none_*.json`, `records_*.jsonl`, `records_none_*.jsonl`: sweeps A and B
- `analyze_final.py` / `analysis_final.json`: the numbers in this report (pointer-chase depth above 13 removed)
- `analysis.json`, `analysis_none.json`: earlier passes that include the shortcut items, kept for comparison
- `configs/`: published configs for the open references, checked with `inspect-config` (no declared recurrence)
