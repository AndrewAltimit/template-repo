# Pre-Registered Predictions: Recurrent-Depth Evidence Battery

**Written:** 2026-11-03, before any battery data was collected.
**Question:** Is Gemini 4 Argon a recurrent-depth (looped) model? Secondary: does the GPT-6 family as a whole show signatures consistent with the looped design reported for GPT-6 Astra?

Each probe below states what looping predicts and what a fixed-depth model predicts, plus the result that would count *against* looping. No probe here is decisive on its own: capability, training for concise reasoning, and serving differences confound all of them. Results are read as "consistent with" or "inconsistent with" a prediction, and the summary weighs all probes together.

Definitions:
- "Corrected accuracy" is chance-corrected accuracy, averaged over task families.
- "Horizon" is the largest depth at which corrected accuracy with reasoning off is at least 0.5, pooled over the long task families (pointer chasing on a 256-node cycle, S5 permutation over 128 operations, reachability on a 300-node graph).
- A depth step is one rung of the ladder 4, 8, 16, 32, 48, 64, 96, 128.

## P1. Serial-depth horizon with reasoning off

- **Looped (family-wide):** GPT-6.1 Terra's horizon is at least one depth step beyond GPT-5.6 Terra's, and the same holds for GPT-6 Luna against GPT-5.6 Luna. Accuracy declines more gradually with log depth for the GPT-6 member of each pair.
- **Fixed / no change:** within each pair, horizons are within one depth step and the decline slopes overlap.
- **Argon:** looping predicts a horizon at least one depth step beyond GPT-5.6 Sol, the strongest OpenAI model that allows reasoning off. **Against looping:** Argon's horizon at or below GPT-5.6 Sol's. Capability alone could also push Argon past GPT-5.6 Sol, so a positive result is weak evidence. A negative result is stronger evidence against.
- **Open fixed-depth references** (DeepSeek V4 Pro, Kimi K2.6): expected horizon at the bottom of the ladder. They only bound the scale.

## P2. Filler tokens (reasoning off, N periods before the answer, N in 0, 32, 128, 512)

- **Expected for all models:** no gain from filler (Pfau et al. 2024 found filler gains only with specific training).
- **Finding of interest:** corrected accuracy at N = 128 or 512 at least 0.10 above N = 0, among filler-compliant responses (compliance at least 70%). That would show hidden computation without legible content. It is a monitorability finding, and only weakly tied to looping (looped and fixed models could both learn it).

## P3. Explicit reasoning-budget curve (Argon, and any model that honors `reasoning.max_tokens`)

- **Looped:** Argon reaches corrected accuracy 0.8 at depths 32 and 64 with at most about 5 reasoning tokens per serial step, similar to or below GPT-6 Astra's and GPT-6.1 Sol's self-chosen 5 to 6.
- **Against:** Argon needs at least 8 tokens per step, as at medium effort today (about 10).

## P4. Latent two-hop composition (TwoHopFact, reasoning off)

- **Looped (family-wide):** the composition rate (two-hop accuracy among facts whose single hops are both answered correctly) is higher for GPT-6.1 Terra than GPT-5.6 Terra, and for GPT-6 Luna than GPT-5.6 Luna, with non-overlapping 95% intervals or a consistent gap of at least 0.10.
- **Fixed / no change:** gaps under 0.10 or inconsistent in sign.
- **Argon:** reported against the same models; capability confounds it as in P1.

## P5. Timing replication (Argon at minimal effort, depth 1 versus 12, 20 repetitions per cell, 3 load windows)

- **Adaptive looping:** a positive TTFT depth slope with z of at least 2 in each window, and a pooled z of at least 3.
- **No adaptive looping:** pooled |z| below 2, or signs that disagree between windows.
- A fixed-depth reference (Llama 3.3 70B) runs in the same windows. If it shows |z| of at least 2 in a window, that window is load-confounded.

## P6. Decode latency per reasoning token (from the reasoning runs)

- **Looped, more passes per token:** higher ms per token for each GPT-6 model than its same-tier GPT-5.6 predecessor on the same provider.
- This is weak: model size and serving hardware are unknown. It is reported, not weighed heavily.

## P7. Serial arithmetic steps at 50% (added 2026-11-03, after R1 to R4 had started, before any results were examined)

Added after the user pointed to a post summarizing Google's and Greenblatt's no-CoT measurements. The task is an arithmetic chain (1 to 12 dependent add, subtract, and multiply steps), with reasoning off and with 128 filler tokens. A logistic fit gives the steps completed with 50% probability.

- **Reference values (Google's own method, not directly comparable):** Gemini 4 Argon about 5.5, Gemini 3.8 Flash 4.2, Gemini 3.1 Pro 3.6 (Gemini 4 Argon Safety & Security Report, sec. 3.4.5.3).
- **Looped (family-wide):** GPT-6.1 Terra and GPT-6 Luna exceed their GPT-5.6 counterparts by at least 1 step with non-overlapping intervals.
- **Argon:** our estimate should be in the same range as Google's 5.5 if the task is comparable. Argon above every OpenAI model measured would be consistent with more serial depth per pass, but capability confounds it.
- **Filler:** Google reports a small filler uplift for Argon (2 NCRI points). A gain of at least 1 step at f128 would be a notable disagreement with that.

Pre-registration deviation: P3 (explicit reasoning budgets) could not run as planned, because OpenRouter did not enforce `reasoning.max_tokens` for these models in the pilot (Argon spent 0 tokens at budgets of 64 and 512; the others overran the cap). P3 is replaced by tokens per step at medium effort on the long chains (R2).

## Decision rule for the summary

- **"Consistent with looping":** P1 and P4 both favor the GPT-6 member of both pairs, and for Argon, P1, P3 and P4 all point the same way with no contradiction from P5.
- **"Against":** two or more probes produce their "against" outcome.
- **Otherwise:** inconclusive, with each probe's direction reported.
