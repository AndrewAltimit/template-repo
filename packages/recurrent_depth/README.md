# Recurrent Depth Signatures Toolkit

> **Measurement tools for telling a recurrent-depth (looped, weight-tied) language model apart from a conventional fixed-depth transformer**

Companion code for [`docs/hardware/recurrent-depth-signatures.md`](../../docs/hardware/recurrent-depth-signatures.md) (RDEPTH-2026-HW-005). The report explains why the distinction matters for AI safety and how strong each kind of evidence is; this package implements the measurements and the scoring.

The toolkit measures and infers. It does not extract weights, bypass access controls, or evade rate limits, and the black-box harness refuses to run until a probe plan confirms that you are authorized to query the endpoint (see [Guardrails](#guardrails)).

## Validation Status

| Capability | Status |
|------------|--------|
| Config inspection (`inspect-config`) | Checked on 8 published configs: Huginn-0125, Ouro-1.4B, Ouro-2.6B-Thinking, and ALBERT-base-v2 flagged as recurrent or weight-shared; Qwen2.5-0.5B, SmolLM2-135M, OLMo-2-1B flagged as standard; Qwen1.5-MoE-A2.7B flagged as standard with an MoE note |
| Weight-sharing analysis (`inspect-weights`) | Unit-tested on synthetic tied, low-rank-shared, independent, single-group (ALBERT-style), and gapped stacks, and on FP8 decoding; on real SmolLM2-135M it reports 30 of 30 distinct layers, no exact or low-rank pairs, adjacent relative distance 1.32-1.41 (no false positive). Not yet run on a real weight-shared checkpoint |
| Hidden-state dynamics (`analyze-hidden`) | Unit-tested on synthetic trajectories; on real SmolLM2-135M the tail contraction is 1.12 and periodicity excess 0.002 (fixed-depth behavior). Not yet run on a real looped model's per-iteration states |
| Black-box probe harness (`probe`) | Tested end to end against a simulated endpoint and scripted transports (streaming, mid-stream errors, retries, hard budget, key handling, refused redirects). **Not yet run against a real API** |
| Scoring and leave-one-out validation | Tested on simulated reference fleets. The default likelihood parameters are engineering priors, **not calibrated on real models** |

Treat any verdict as provisional until the likelihoods have been fitted to real reference models measured with the same plan (see [Calibrate before you classify](#calibrate-before-you-classify)).

## What It Measures

| Module | Access level | Signal(s) |
|--------|--------------|-----------|
| `config_inspect` | White box (config) | `config_recurrence`: 1 if the config declares looping, 0.5 for custom code that cannot be judged, 0 for a standard fixed-depth class |
| `safetensors_io`, `weights` | White box (weights) | `shared_layer_fraction`, `weight_reuse_ratio`: exact duplicate layers, low-rank-related layers (shared base plus LoRA deltas), declared versus stored depth, and missing layer indices (Hugging Face drops aliased tensors on save). Reads F32/F16/BF16/FP8 and integer dtypes; FP8 block scales are not applied |
| `dynamics`, `hf_capture` | White box (activations) | `state_contraction`, `similarity_periodicity`, logit-lens KL settling steps per token |
| `graybox` | Gray box (log-probabilities) | Hidden-width estimate from the rank of logit vectors; `compute_capacity_ratio` from user-supplied compute and capacity estimates |
| `tasks`, `client`, `harness`, `features` | Black box (API) | `ttft_slope_z`, `itl_slope_z` (latency versus serial depth at fixed prompt and output length), `serial_retention` (no-CoT accuracy as depth grows), `knob_latency_log_ratio`, `knob_accuracy_gain` (effect of a compute knob without extra visible or billed tokens); diagnostic `ttft_excess_in_itl` (TTFT increase across depths in inter-token latencies, to flag unreported hidden decoding) |
| `scoring`, `validation` | Any | Likelihood-ratio combination (monotone in each signal's direction, with one-sided floors for absence-of-evidence signals) with family-level correlation discounts, an explicit `inconclusive` outcome, fitting to references, and leave-one-out benchmarking |

The task suite (pointer chasing, S5 permutation tracking, prefix parity, graph reachability) keeps the prompt length constant across depths within each family, so a latency slope cannot come from longer prompts.

## Running (container-first)

Python runs in the repository's `python-ci` container. numpy is the only runtime dependency; torch and transformers are needed only for `hf_capture`.

```bash
# Tests (no network, no GPU)
docker compose --profile ci run --rm python-ci \
  bash -c "cd packages/recurrent_depth && python -m pytest -q"

# Any CLI command
docker compose --profile ci run --rm -e PYTHONPATH=packages/recurrent_depth/src python-ci \
  python -m recurrent_depth --help
```

### White box

```bash
python -m recurrent_depth inspect-config path/to/config.json
python -m recurrent_depth inspect-weights path/to/checkpoint_dir --config path/to/config.json
python -m recurrent_depth analyze-hidden states.npy --unembed unembed.npy
```

`states.npy` is a `(steps, tokens, dim)` array: per-layer states for a fixed-depth model, or per-iteration states for a looped block. `hf_capture.capture_hidden_states()` records per-layer states from a Hugging Face model you have already loaded; read any `trust_remote_code` modeling file before loading it.

### Black box

```bash
cp packages/recurrent_depth/examples/probe_plan.example.json plan.json
# edit base_url, model, rate limits; set acknowledge_terms to true only if it is true
python -m recurrent_depth probe plan.json --out records.jsonl
python -m recurrent_depth features records.jsonl > blackbox_signals.json
python -m recurrent_depth score blackbox_signals.json config_signals.json
```

`score` accepts several signal files (for example config, weights, and black-box) and refuses duplicate signal names, so the same evidence cannot be counted twice by accident.

### Offline demonstration

```bash
python -m recurrent_depth simulate --kind recurrent --knob --out sim.jsonl
python -m recurrent_depth features sim.jsonl --knob-order low,medium,high
python -m recurrent_depth simulate-fleet --n-each 6 --out refs.json
python -m recurrent_depth validate refs.json
```

The simulator is synthetic. Its numbers illustrate the pipeline and are not measurements of any real system.

## Calibrate Before You Classify

1. Choose reference models whose architecture is documented: open looped models (for example Huginn-0125, Ouro) and open fixed-depth models of similar size, served the same way (same server software, batching, and hardware where possible).
2. Measure every reference with the same probe plan you will use on the target.
3. Write a references file: `[{"model": "...", "label": "recurrent" | "fixed", "signals": {...}}, ...]`.
4. `validate references.json` reports coverage, accuracy among decided verdicts, wrong decided verdicts, Brier score, and log loss under leave-one-out.
5. `fit references.json --out models.json`, then `score ... --models models.json` on the target.

A verdict is `recurrent` or `fixed` only when the posterior passes the threshold (default 0.9) and at least two independent evidence families agree; a white-box family (config or weights) that supports the verdict with a log-likelihood ratio of at least 3, such as a declared recurrence or exact layer reuse, counts as direct observation and may decide alone. Absence of evidence never decides alone: a standard config class contributes -1.5, and unshared weights at most -0.5, because looped checkpoints such as Huginn and Ouro store their shared block once. Otherwise the verdict is `inconclusive`.

## Guardrails

- The harness refuses a plan unless `acknowledge_terms` is `true`, which records that you are authorized to query the endpoint and that the plan respects the provider's terms and rate limits.
- A hard request budget (`max_requests`, counting retries) and a minimum spacing (`requests_per_minute`) are enforced; 429 and 5xx responses back off and honor `Retry-After`. If retries exhaust the budget, `probe` stops, keeps the records written so far, and exits with status 2.
- API keys are read from an environment variable, never written to records, and never sent over plain HTTP to a non-local host. Redirects are refused, because urllib would otherwise replay the `Authorization` header to the redirect target.
- Requests whose usage reports hidden reasoning tokens are excluded from timing and knob analysis rather than misread as in-pass computation; if any request in a run reports them, no knob signal is emitted.
- Nothing here recovers weights. `graybox.estimate_rank` estimates a width from vectors you are entitled to collect.

## Layout

```
packages/recurrent_depth/
  src/recurrent_depth/   config_inspect, safetensors_io, weights, dynamics, hf_capture,
                         graybox, tasks, client, harness, features, scoring, validation,
                         simulate, cli
  tests/                 offline unit tests (synthetic fixtures, virtual clock)
  examples/              probe plan template
```

## License

MIT, as for the rest of the repository.
