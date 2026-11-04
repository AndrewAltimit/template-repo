# Is Gemini 4 Argon a Looped Model? (November 2026)

Black-box investigation, through OpenRouter, of whether Gemini 4 Argon shows recurrent-depth (looped) signatures, using the GPT-6 family as recurrent references. Total API spend was about $15.

**Bottom line:** Argon is inconclusive on architecture. It has the strongest serial reasoning without visible reasoning of any model measured, but Google describes it as a sparse MoE transformer, and no probe shows adaptive compute. Within the GPT-6 family, GPT-6.1 Terra differs from GPT-5.6 Terra on four probes in the direction looping predicts, while GPT-6 Luna differs from GPT-5.6 Luna only on two-hop composition.

Read in order:

| File | Contents |
|---|---|
| [01-timing-probe.md](01-timing-probe.md) | Round 1: time-to-first-token and serial-retention probe with likelihood scoring. Inconclusive; the timing slope did not replicate. |
| [02-budget-sweep.md](02-budget-sweep.md) | Reasoning-budget sweep: tokens per serial step and the share of accuracy reached with reasoning off (in-pass share). |
| [PREDICTIONS.md](PREDICTIONS.md) | Pre-registered predictions for the battery, written before data collection, with documented deviations. |
| [03-evidence-battery.md](03-evidence-battery.md) | Main report: long-chain horizon, filler tokens, latent two-hop composition, serial arithmetic steps at 50%, decode latency, and timing replication across load windows. |
| [published-evals.md](published-evals.md) | Desk-research compilation of published lab and third-party statements and safety-eval numbers, with sources. |

Raw plans, per-request records, and analysis scripts were kept outside the repository. Every probe can be rerun with the toolkit commands in the [package README](../../README.md): `probe`, `budget-probe`, `budget-features`, and `twohop-features`.
