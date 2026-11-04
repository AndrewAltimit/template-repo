# Recurrent-Depth Assessment: Google Gemini 4 Argon

**Target:** `google/gemini-4-argon` (canonical `google/gemini-4-argon-20261013`) via OpenRouter, served by Google (Vertex, global)
**Date:** 2026-11-03
**Toolkit:** `packages/recurrent_depth` (black-box probe harness, `features`, `scoring`, `validation`), RDEPTH-2026-HW-005 protocol
**Access level:** Black box only (no config, weights, or log-probabilities)

> **Update (same day):** a follow-up reasoning-budget sweep ([02-budget-sweep.md](02-budget-sweep.md)) found that Argon has the highest no-reasoning serial accuracy of any model measured (in-pass share 0.79, 95% CI 0.66 to 0.91). That is consistent with substantial in-pass compute, but Argon is the least token-efficient closed model once it reasons, and capability and about 3 to 4 hidden tokens per answer confound the comparison. The overall verdict below stays inconclusive.

## Verdict

**Inconclusive. Black-box probing gives no reproducible evidence that Gemini 4 Argon is a recurrent-depth model, and the method could not reliably detect the reportedly looped GPT-6 models either, so the result does not rule it out.**

The one recurrence-leaning signal from the first run, a rise in time-to-first-token (TTFT) with serial depth (z = +2.37), **did not replicate**. A second run on fresh items gave z = -1.50, and the two runs pooled give z = +0.63. Every calibration that scores Argon `recurrent` relies on the first run alone. With both runs pooled, every calibration and prior gives `inconclusive`.

| Argon data | Fixed refs only | + Astra as recurrent | + all GPT-6 as recurrent |
|---|---|---|---|
| Run 1, prior 0.5 | recurrent (0.95) | recurrent (0.96) | recurrent (0.96) |
| Run 1, prior 0.2 | inconclusive (0.83) | inconclusive (0.86) | inconclusive (0.86) |
| Run 2, prior 0.5 | inconclusive (0.25) | inconclusive (0.32) | inconclusive (0.45) |
| **Pooled, prior 0.5** | **inconclusive (0.51)** | **inconclusive (0.62)** | **inconclusive (0.65)** |
| **Pooled, prior 0.2** | **inconclusive (0.21)** | **inconclusive (0.29)** | **inconclusive (0.32)** |

Numbers are posterior P(recurrent). All signals exclude records that reported reasoning tokens (see Section 4). The pooled rows are the result to cite. The run-1 rows show how a single unreplicated probe can produce a confident-looking verdict.

## Method

Every model received the same probe plan: 4 task families (pointer chasing, S5 permutation tracking, prefix parity, graph reachability) x 5 nominal depths (1, 2, 4, 8, 12) x 6 repetitions = 120 streamed requests, temperature 0, no chain of thought requested, `max_tokens` 64, 20 requests per minute. Prompt length is constant across depths within each family. 1,200 of 1,200 requests returned HTTP 200.

| Role | Models | Reasoning setting |
|---|---|---|
| Target | Gemini 4 Argon, run 1 (seed 0) and run 2 (seed 1, later window) | `effort: minimal` (reasoning cannot be disabled) |
| Fixed-depth references | Llama 3.3 70B, Qwen 2.5 72B, Gemma 4 31B (all dense), Llama 4 Maverick (MoE) | none / disabled |
| Recurrent references | GPT-6 Astra | `effort: minimal` (cannot be disabled) |
| Recurrent references (sensitivity) | GPT-6.1 Sol, GPT-6.1 Terra, GPT-6 Luna | `effort: minimal` |

**Basis for the recurrent labels.** *The Information* reported on 2026-09-01 that GPT-6 Astra uses recurrent depth. On 2026-09-02, OpenAI chief scientist Jakub Pachocki responded on X without denying the looped design and said the computational-graph depth of OpenAI's frontier models, Astra included, is within a factor of two of GPT-4. OpenAI's system card does not describe the architecture. Astra is treated here as a recurrent reference. Sol, Terra, and Luna are labeled recurrent on the basis that the GPT-6 family is distilled from Astra and is positioned as the token-efficient family that came out of this architectural change. No public source found states their architecture, and distillation does not by itself carry architecture over, so they appear only as a sensitivity case.

## Findings

### 1. Argon's timing signal does not replicate

| Argon run | TTFT log-slope per depth unit | z | Median TTFT, depth 1 to 12 |
|---|---|---|---|
| Run 1 (seed 0) | +0.0156 | +2.37 | 2.69 s to 3.00 s |
| Run 2 (seed 1) | -0.0088 | -1.50 | 3.03 s to 2.74 s |
| Pooled (224 requests) | +0.0030 | +0.63 | |

In run 1 the rise came from pointer chasing and permutation at depth 12. In run 2 no family shows a positive slope above its standard error. Run-to-run variation of this size (|z| about 2) also appears in the fixed references: Llama 4 Maverick gave z = -2.26. At about 2.7 s of fixed overhead with an interquartile range near 1 s per cell, a 0.3 s per-depth effect cannot be measured reliably with 6 repetitions.

### 2. The reportedly looped models show no shared timing signature

| Model | TTFT slope z | Requests without reported reasoning | Deepest depth with any such request |
|---|---|---|---|
| GPT-6 Astra | +1.81 | 52 / 120 | 8 (3 items) |
| GPT-6.1 Sol | -2.10 | 47 / 120 | 8 (2 items) |
| GPT-6.1 Terra | -0.24 | 47 / 120 | 8 (3 items) |
| GPT-6 Luna | not computable | 4 / 120 | 12 (3 items) |
| Fixed references | -2.26 to +0.85 | 120 / 120 each | 12 |

If the GPT-6 family is looped, this probe does not detect it: their slopes spread across the same range as the fixed references. Leave-one-out validation reflects this. Astra alone is scored `recurrent` (0.90) only when all four GPT-6 models are labeled, and Sol, Terra, and Luna stay `inconclusive` (0.50 to 0.59).

There are two likely reasons, both relevant to how to read Argon:

- **A fixed loop count leaves no depth slope.** The TTFT and ITL probes detect *adaptive* recurrence, where the number of loop iterations grows with problem difficulty. A model that always runs the same number of loops is, in black-box timing, the same as a deeper fixed model. Pachocki's statement that depth stays within a factor of two of GPT-4 fits a modest, capped loop count, which this probe would miss by design.
- **The GPT-6 models reason in visible tokens on hard items, even at minimal effort.** The share of requests that report reasoning tokens grows with depth (Astra: 6 of 24 at depth 1, 24 of 24 at depth 12; median reasoning length 15 tokens at depth 1, 32 at depth 12). Once a model reasons in tokens, the toolkit correctly excludes the request from timing, leaving only the easy items to measure.

### 3. Hidden-token behavior

Argon, Astra, Sol, Terra, and Luna all bill exactly **5 completion tokens** for a 1 to 3 character answer when no reasoning is reported, against 1 to 2 tokens for the open references. This points to a fixed overhead of about 3 to 4 unreported tokens shared by both vendors' reasoning endpoints. For Argon it was constant at every depth (118 of 118 unreported-reasoning requests in each run), so it moves the latency baseline without biasing the depth slope. Argon escaped into reported reasoning on only 2 requests per run, against 47 to 116 per run for the GPT-6 models.

### 4. Behavioral signal: confounded by capability

| Model | Accuracy by depth (1, 2, 4, 8, 12), all requests | `serial_retention` (no-reasoning requests only) |
|---|---|---|
| Gemini 4 Argon, run 1 / run 2 | 1.00, 1.00, 1.00, 0.79, 0.58 / 1.00, 1.00, 1.00, 0.83, 0.58 | 0.58 / 0.53 |
| GPT-6 Astra | 1.00, 1.00, 1.00, 0.83, 0.75 | 0.67 (no depth-12 data) |
| Fixed references | 0.71 to 0.88 at depth 1, 0.29 to 0.33 at depth 12 | 0.07 to 0.14 |

In every calibration, `serial_retention` pushes Argon toward `recurrent` (+1.1 to +1.5 LLR). This reflects capability, not architecture: the four fixed references are previous-generation models that fail early, so any frontier model, looped or not, scores high against them. All four task families can be solved in about log2(d) parallel stages, so a strong fixed-depth model is expected to hold up to depth 12. **This family's contribution should be discounted.** It cannot separate a stronger model from a looped one without fixed-depth references of comparable capability.

Two measurement caveats:

- **Toolkit gap:** `features.accuracy_curves` does not exclude requests that report reasoning tokens, though the timing signals do. Unfiltered, the GPT-6 models score 0.75 retention, which mostly measures chain-of-thought accuracy. This report filters those requests for all signals (`analyze3.py`).
- **Filtering creates survivor bias:** filtering keeps only items a model chose to answer without reasoning, which skews toward easy items. For the GPT-6 models no depth-12 items survive, so their retention values rest on 2 to 3 items at depth 8. For Argon the filter removes only 2 requests per run, so this bias is small.

## Limitations

1. **Unproven sensitivity on API models.** The probe did not consistently separate the reportedly looped GPT-6 models from fixed references, so "no signal in Argon" carries little weight either way.
2. **Recurrent labels are reported, not documented.** Astra's architecture rests on press reporting and a non-denial from OpenAI's chief scientist. Sol, Terra, and Luna rest on family lineage.
3. **Different serving stacks.** The open references run on third-party providers, Argon on Google Vertex, and GPT-6 on OpenAI. Fixed latency overhead differs by roughly 5x across stacks.
4. **Mandatory reasoning** on Argon, Astra, and Sol (and the GPT-6 models' frequent visible reasoning even at minimal effort) blocks clean in-pass measurement on exactly the items that matter most.
5. **No ITL, logprobs, or knob signal.** Answers arrive in one chunk, and higher reasoning efforts report visible tokens.
6. **Capability mismatch** between the targets and the fixed references distorts the behavioral family (Section 4).

## Recommendations

1. **Treat timing as the only discriminating family, and power it up.** Run depths 1 and 12 only, with about 20 repetitions, across at least 3 load windows. Run 1's effect disappeared on replication, which is what more power would confirm or overturn.
2. **Add a fixed-depth reference of frontier capability**, at the lowest reasoning setting, so the behavioral family stops measuring capability.
3. **Toolkit fixes:**
   - (a) Exclude reported-reasoning requests from `accuracy_curves` and report how many were dropped per depth, flagging survivor bias.
   - (b) Add a diagnostic for completion tokens that exceed visible output (constant here, but on another endpoint it could fake a depth slope).
   - (c) State in the report and README that black-box timing detects adaptive, not fixed, recurrence.
4. **Recover ITL.** A task variant with a fixed-length answer suffix would produce multiple chunks and enable the hidden-decoding diagnostic.

## Cost and footprint

About 1,220 requests in total (10 runs of 120 plus about 20 pilot requests), all with `max_tokens` 64, at 20 requests per minute per model. Estimated spend is under one US dollar, mostly GPT-6 Astra. The probe plans set `acknowledge_terms: true` at the account holder's request. This is ordinary paid API usage measured from the outside: no weights are extracted and no access controls are bypassed.

## Sources for reference labels

- The Information report on Astra, as summarized in [Recurrent Depth: What We Know About OpenAI's Astra (kingy.ai)](https://kingy.ai/blog/recurrent-depth-openai-astra/)
- Pachocki's response, as reported in [aioga.com](https://www.aioga.com/en/news/cmtl5ax5c0idsroalnotsli1u/) and discussed on [LessWrong](https://www.lesswrong.com/posts/PLisnSFir8y5AHkmP/how-concerned-should-we-be-about-astra-s-recurrent). His X post itself was not retrieved.

## Artifacts

Raw plans, per-request records, and analysis scripts are kept outside the repository (local `outputs/rds/argon/`, gitignored):

- `plan_*.json`, `records_*.jsonl`: probe plans and per-request records for all 10 runs
- `analyze.py` / `analysis.json`: round 1 (Argon run 1 vs fixed references)
- `analyze2.py` / `analysis2.json`: round 2 (GPT-6 references, Argon replication, unfiltered behavioral signal)
- `analyze3.py` / `analysis3.json`: final scoring with reasoning-token requests excluded from all signals
- `refs.json`, `models.json`, `models_with_gpt6.json`: reference signals and fitted likelihoods
