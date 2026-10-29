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

Treat any verdict as provisional until the likelihoods have been fitted to real reference models measured with the same plan (see [step 3 of the Quickstart](#3-calibrate-and-validate)).

## What It Measures

| Module | Access level | Signal(s) |
|--------|--------------|-----------|
| `config_inspect` | White box (config) | `config_recurrence`: 1 if the config declares looping, 0.5 for custom code that cannot be judged, 0 for a standard fixed-depth class |
| `safetensors_io`, `weights` | White box (weights) | `shared_layer_fraction`, `weight_reuse_ratio`: exact duplicate layers, low-rank-related layers (shared base plus LoRA deltas), declared versus stored depth, and missing layer indices (Hugging Face drops aliased tensors on save). Reads F32/F16/BF16/FP8 and integer dtypes; FP8 block scales are not applied |
| `dynamics`, `hf_capture` (`capture-hidden`) | White box (activations) | `state_contraction`, `similarity_periodicity`, logit-lens KL settling steps per token |
| `graybox` | Gray box (log-probabilities) | Hidden-width estimate from the rank of logit vectors; `compute_capacity_ratio` from user-supplied compute and capacity estimates |
| `tasks`, `client`, `harness`, `features` | Black box (API) | `ttft_slope_z`, `itl_slope_z` (latency versus serial depth at fixed prompt and output length), `serial_retention` (no-CoT accuracy as depth grows), `knob_latency_log_ratio`, `knob_accuracy_gain` (effect of a compute knob without extra visible or billed tokens); diagnostic `ttft_excess_in_itl` (TTFT increase across depths in inter-token latencies, to flag unreported hidden decoding) |
| `scoring`, `validation` | Any | Likelihood-ratio combination (monotone in each signal's direction, with one-sided floors for absence-of-evidence signals) with family-level correlation discounts, an explicit `inconclusive` outcome, fitting to references, and leave-one-out benchmarking |

The task suite (pointer chasing, S5 permutation tracking, prefix parity, graph reachability) keeps the prompt length constant across depths within each family, so a latency slope cannot come from longer prompts.

## Quickstart

The steps below take a new evaluator from nothing to a scored, validated verdict. Every command was run as written against this version of the CLI; the numbers quoted are what the simulator produces with the default seeds.

### 0. Setup (container-first)

Python runs in the repository's `python-ci` container, from the repository root. numpy is the only runtime dependency; torch and transformers (both in the container) are needed only for `capture-hidden`. Define a shell function so every later step is one line:

```bash
rd() {
  docker compose --profile ci run --rm -T \
    -e PYTHONPATH=packages/recurrent_depth/src python-ci \
    python -m recurrent_depth "$@"
}
mkdir -p outputs/rds            # gitignored scratch directory for every file below
rd --help                       # lists all commands; rd <command> --help for options

# Tests (no network, no GPU)
docker compose --profile ci run --rm -T python-ci \
  bash -c "cd packages/recurrent_depth && python -m pytest -q"
```

`-T` disables the pseudo-terminal so that redirected JSON is not mixed with progress messages. Every command prints JSON to stdout and progress to stderr, so `> file.json` saves a signals file that `score` reads. The container sees the repository at `/app`, so put checkpoints and outputs under the repository (for example `outputs/`, which is gitignored), or add `-v /path/to/models:/models:ro` to the function.

### 1. White box: a local checkpoint

Use any checkpoint you have already downloaded, for example SmolLM2-135M (fixed depth) or Ouro-1.4B (looped) in `outputs/rds/model/`. Nothing in the toolkit downloads anything.

```bash
M=outputs/rds/model
rd inspect-config  $M/config.json                      > outputs/rds/config_signals.json
rd inspect-weights $M --config $M/config.json          > outputs/rds/weight_signals.json
rd capture-hidden  $M --text "Each step of the loop refines the same state." \
   --out outputs/rds/states.npy --unembed-out outputs/rds/unembed.npy
rd analyze-hidden  outputs/rds/states.npy --unembed outputs/rds/unembed.npy > outputs/rds/dynamics_signals.json
rd score outputs/rds/config_signals.json outputs/rds/weight_signals.json
```

What to expect:

- `inspect-config` sets `config_recurrence` to 1 when the config declares looping (Huginn's `mean_recurrence`, Ouro's `total_ut_steps`, Nanbeige's `num_loops`), 0.5 for custom code it cannot judge, and 0 for a standard fixed-depth class. A declared recurrence decides `recurrent` on its own.
- On SmolLM2-135M, `inspect-weights` reports 30 distinct layers (`shared_layer_fraction` 0, `weight_reuse_ratio` 1), and scoring the config and weights files gives `inconclusive` (posterior 0.10). That is intended: absence of looping in a config and in stored weights never decides alone, because looped checkpoints store their shared block once.
- `capture-hidden` records one state per layer through the model's `output_hidden_states`. For a fixed-depth model that is the per-layer trajectory `analyze-hidden` compares against. A looped model's per-iteration states usually need hooks in its own modeling code; pass `--trust-remote-code` only after reading that code.
- `analyze-hidden` reports `state_contraction` (below 1 means the state is converging), `similarity_periodicity`, and, with `--unembed`, logit-lens settling steps per token. Tokens that never settle get `steps + 1`.

### 2. Black box: a simulated endpoint

The simulator plays a fixed-depth or an adaptive recurrent endpoint through the same records format as `probe`, so the whole black-box pipeline runs offline:

```bash
rd simulate --kind recurrent --knob --out outputs/rds/sim_recurrent.jsonl
rd simulate --kind fixed     --knob --out outputs/rds/sim_fixed.jsonl
rd features outputs/rds/sim_recurrent.jsonl --knob-order low,medium,high > outputs/rds/rec_signals.json
rd features outputs/rds/sim_fixed.jsonl     --knob-order low,medium,high > outputs/rds/fix_signals.json
echo '{"signals": {"config_recurrence": 0.5}}' > outputs/rds/custom_code.json   # config unknown
```

`features` emits `ttft_slope_z`, `itl_slope_z`, `serial_retention`, `knob_accuracy_gain`, and `knob_latency_log_ratio`, plus diagnostics (per-family slopes, accuracy curves, and `ttft_excess_in_itl`, which flags unreported hidden decoding). Signals that cannot be computed are omitted, not defaulted.

### 3. Calibrate and validate

A verdict means nothing until the scorer has been benchmarked on models whose architecture is known. With the simulator standing in for a reference fleet:

```bash
rd simulate-fleet --n-each 6 --out outputs/rds/refs.json
rd validate outputs/rds/refs.json                        # leave-one-out benchmark
rd fit      outputs/rds/refs.json --out outputs/rds/models.json
```

`validate` reports coverage 0.67 (8 of 12 decided), 0 wrong decided verdicts, Brier 0.016, and a confusion table. With real references, write the file yourself as `[{"model": "...", "label": "recurrent" | "fixed", "signals": {...}}, ...]`, one row per reference model measured with the same plan and serving stack as the target.

### 4. Score

```bash
rd score outputs/rds/rec_signals.json outputs/rds/custom_code.json --models outputs/rds/models.json
rd score outputs/rds/fix_signals.json outputs/rds/custom_code.json --models outputs/rds/models.json
rd score outputs/rds/rec_signals.json outputs/rds/custom_code.json --models outputs/rds/models.json --prior 0.2
```

With fitted likelihoods the recurrent endpoint scores `recurrent` (posterior 0.993; timing +3.0, knob +2.0, behavioral -0.06) and the fixed endpoint `fixed` (0.007). Without `--models` the uncalibrated defaults give 0.912 and 0.004: the recurrent verdict only just passes the threshold, which is why step 3 comes first. Report every verdict at more than one prior: at a prior of 0.2 the recurrent endpoint still scores `recurrent` (0.972). The output lists per-signal contributions, per-family log-likelihood ratios, the families that support the verdict, and notes. `score` accepts any number of signal files and refuses a signal name that appears in two of them.

### 5. A real endpoint

```bash
cp packages/recurrent_depth/examples/probe_plan.example.json outputs/rds/plan.json
# edit base_url, model, api_key_env, requests_per_minute, max_requests;
# set acknowledge_terms to true only if you are authorized and the plan respects the provider's terms
rd probe outputs/rds/plan.json --out outputs/rds/records.jsonl
rd features outputs/rds/records.jsonl > outputs/rds/target_signals.json
rd score outputs/rds/target_signals.json outputs/rds/config_signals.json --models outputs/rds/models.json
```

The example plan sends 120 requests (4 tasks x 5 depths x 6 repetitions) at 10 per minute under a hard budget of 400. Pass the API key into the container by adding `-e OPENAI_API_KEY` (or the variable named in `api_key_env`) to the `rd` function. A server running on the host is reachable from the container at `host.docker.internal`, not `localhost`; the client sends a key over plain HTTP only to local hosts such as these, and `api_key_env` can be `null` for a local server that needs no key. If the endpoint has a compute knob, set `knob_param` and `knob_values` and give `features` the same order with `--knob-order`. Measure the reference models with the same plan, on the same serving stack, at more than one load level, before scoring the target; the report's Section 7 sets out the protocol.

## Decision Rule

A verdict is `recurrent` or `fixed` only when the posterior passes the threshold (default 0.9) and at least two independent evidence families agree; a white-box family (config or weights) that supports the verdict with a log-likelihood ratio of at least 3, such as a declared recurrence or exact layer reuse, counts as direct observation and may decide alone. Absence of evidence never decides alone: a standard config class contributes -1.5, and unshared weights at most -0.5 per signal, because looped checkpoints such as Huginn and Ouro store their shared block once. Otherwise the verdict is `inconclusive`.

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
