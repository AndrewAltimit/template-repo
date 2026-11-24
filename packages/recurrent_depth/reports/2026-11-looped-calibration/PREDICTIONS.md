# Pre-Registered Predictions: Calibrating the Toolkit on Known Looped Models

**Written:** 2026-11-23, before any calibration data was collected. The only facts used are the published configs and model cards listed under Subjects.
**Question:** When the ground truth is known, which of the toolkit's probes detect looping? The answer sets how much weight the black-box battery in [2026-11-argon-gpt6](../2026-11-argon-gpt6/README.md) deserves.

The battery there found Argon and GPT-6.1 Terra ahead on no-reasoning serial probes, but nothing in it had been checked against a model known to loop. This campaign runs the same probes, plus the white-box tools, on models whose loop structure is published.

## Subjects

| Model | Loop structure (from the published config and card) | Role |
|---|---|---|
| Huginn-0125 (`tomg-group-umd/huginn-0125`, rev `bb6621b6`) | 2 prelude + 4 recurrent + 2 coda layers; `mean_recurrence` 32. The step count is set per call (`num_steps`), and the card documents a zero-shot per-token adaptive exit (`criterion="kl"`). | Positive control, adaptive and fixed |
| Ouro-1.4B (`ByteDance/Ouro-1.4B`, rev `574fa66c`) | 24 layers run `total_ut_steps` = 4 times; `early_exit_threshold` 1.0 means always run every step. | Positive control, fixed |
| Ouro-2.6B (`ByteDance/Ouro-2.6B`, rev `1ed04250`) | 48 layers, 4 steps, same exit settings. | Positive control, fixed |
| SmolLM2-1.7B and Qwen3-1.7B-Base | Fixed depth. | Negative controls, sized like the positives |
| GLM-5.3 and GLM-5.4 (when weights or API open) | GLM-5.4 reportedly runs 28 layers of the GLM-5 base twice (prelude, two loop passes, coda). GLM-5.3 is the non-looped predecessor. | Matched pair at frontier scale |

Conditions:
- Huginn at fixed `num_steps` of 4, 8, 16, 32 and 64, plus adaptive exit (`criterion="kl"`, `exit_threshold=5e-4`, at most 64 steps).
- Ouro at `total_ut_steps` of 1, 2, 3 and 4, with exit threshold 1.0.
- All local models run on one GPU, one request at a time, through the toolkit's own server, so load cannot confound timing.

## C1. Config inspection (`inspect-config`)

- **Huginn and Ouro:** verdict "declares looping". The parser already knows `huginn_raven` and `ouro`.
- **Negative controls:** no declared recurrence.
- **GLM-5.4:** declares looping, **if** its config names the loop with any field the generic patterns catch (`num_loops`, `loop_*`, recurrence or iteration counts). If it uses names the parser misses, that is a toolkit gap and gets fixed, not a negative result.

## C2. Weight inspection (`inspect-weights`)

- **Every looped model:** no shared or duplicated layers detected, because looped checkpoints store the shared block once.
- This is the known blind spot. The calibration expects it to hold, and if `inspect-weights` flags any of these models, the detector needs checking.

## C3. Hidden-state dynamics (`capture-hidden` then `analyze-hidden`, per recurrent step)

- **Huginn:** state contraction below 1 from 16 steps on (the state converges), and logit-lens settling in fewer steps on easy tokens than hard ones.
- **Ouro:** contraction below 1 across its 4 steps.
- Negative controls are only measured per layer, as a reference, and carry no prediction.

## C4. Step-count knob on serial tasks (reasoning off; arithmetic chain and the short long-chain ladder)

- **Huginn:** serial-arithmetic steps at 50% rise by at least 1 from 4 to 32 steps, then change by less than 1 from 32 to 64 (the card says gains stop near 64).
- **Ouro:** accuracy rises from 1 to 4 steps on the same tasks.
- **Against:** no rise with step count. Then the serial tasks are not measuring in-pass depth at this model size, and the Argon and GPT-6 serial results lose much of their weight.

## C5. Timing (time to first token versus serial depth, the P5 method from the Argon battery)

- **Fixed-loop conditions** (every Huginn fixed setting, every Ouro setting): |z| below 2, the same as the negative controls. A fixed loop count costs the same at every task depth.
- **Huginn adaptive:** also |z| below 2 for time to first token. The exit rule reacts to how quickly each token's state settles, not to the serial depth of the task, and it applies while decoding rather than to the prompt. Confidence is low.
- **Huginn adaptive, decode time per token:** higher on hard items than easy ones, with z of at least 2.
- **What follows if these hold:** the timing probe used on Argon detects only adaptive loops, and only through decode time. A null timing result says little about a fixed loop.

## C6. Serial capability per stored parameter (reasoning off)

- **Huginn at 32 steps** beats Huginn at 4 steps on two-hop composition by at least 0.05 and on arithmetic steps at 50% by at least 1. The two-hop part is weak, because small base models may sit near the floor.
- **Huginn at 32 steps** scores at least as well as both negative controls on arithmetic steps at 50%. This is a direction only, not a size.

## C7. GLM-5.4 versus GLM-5.3 (same probes, same provider or same self-hosted engine)

- **Timing:** |z| below 2. A fixed two-pass loop should be invisible to the timing probe.
- **Serial probes:** GLM-5.4 beats GLM-5.3 by at least 1 arithmetic step at 50%, by at least 0.05 in two-hop composition, and by at least one rung on the long-chain horizon. Holding all three would mean the battery picks up a known loop at frontier scale.
- **Decode cost (self-hosted on the same node and engine only):**
  - The ratio of ms per token, GLM-5.4 over GLM-5.3, falls within 15% of (L + 28) / L.
  - Here L is the layer count in GLM-5.3's config, recorded before the run.
  - This assumes the reported 28-layer second pass and similar per-layer cost.

## Decision rules

- **Battery validated:** C4 holds for both positive families and C6 holds. Then the serial probes measure in-pass depth, and the Argon and GPT-6 serial results keep their weight, still confounded by capability.
- **Battery not validated:** C4 fails for either family. The Argon and GPT-6 serial findings are then reported as capability differences only.
- **Timing blind spot confirmed:** C5 fixed-loop conditions and the C7 timing result are null. The Argon report already treats a null timing result as ruling out adaptive loops only; a confirmed blind spot makes that explicit and closes the question.
- **Frontier result:** C7 serial predictions hold, or at least two of the three do. Then the GPT-6.1 Terra pattern from the Argon battery, which moved the same way, becomes more plausible as an architecture signal.

## Run order and spend ceiling

| Tier | Where | Purpose | Ceiling |
|---|---|---|---|
| 0 | Local containers, CPU | Config and weight inspection, one Ouro-1.4B hidden capture, every pipeline step on tiny inputs | $0 |
| 1 | One-GPU cloud instance | Huginn, Ouro and controls: C3 to C6 | $25 |
| 2 | Same instance type, longer run | Full reps for C4 to C6 if tier 1 is underpowered | $50 |
| 3 | 8-GPU node | GLM-5.3 and GLM-5.4: C1, C2 and C7 | Set when the weights are out |

Every stage checkpoints its outputs to S3 before the next starts, and every node shuts itself down at a fixed deadline. See `infra/aws/recurrent-depth/README.md`.
