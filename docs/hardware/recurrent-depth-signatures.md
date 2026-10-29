# Recurrent Depth Signatures

**Detecting looped and recurrent-depth language models from the outside**

| | |
|---|---|
| **Document** | RDEPTH-2026-HW-005 |
| **Version** | 1.0 (October 2026) |
| **Audience** | AI safety researchers, third-party evaluators, model auditors, and policy bodies who need to know how a model computes when the developer does not say |
| **Scope** | Measurement and inference only: configuration and weight inspection where weights are public, and ordinary API use where they are not. No weight extraction, no bypassing of access controls or rate limits, no model stealing. |
| **Companion code** | [`packages/recurrent_depth/`](../../packages/recurrent_depth/): config and weight analyzers, a rate-limited black-box probe harness, and a likelihood-ratio scorer with an inconclusive outcome |
| **Related documents** | [AI Agent Containment & Infrastructure Security Framework](./ai-agent-containment-infrastructure-security-framework.md); [Agent Swarm Honeypot Guide](./agent-swarm-honeypot-guide.md) |
| **PDF source** | [`latex/recurrent-depth-signatures.tex`](./latex/recurrent-depth-signatures.tex) |

> [!IMPORTANT]
> **The premise.** A recurrent-depth model runs the same block of layers several times per token, so it can do more sequential computation inside one forward pass than its parameter count suggests, and none of that computation has to appear as text. Several developers no longer disclose architecture. This guide sets out how to tell such a model from a conventional fixed-depth transformer using public weights where they exist and ordinary API access where they do not, how strong each kind of evidence is, and how to combine the evidence into a verdict that is allowed to say "inconclusive".

---

## Contents

- [How to Use This Guide](#how-to-use-this-guide)
1. [Executive Summary](#1-executive-summary)
2. [Architecture Taxonomy](#2-architecture-taxonomy)
3. [Why Architecture Matters for Safety](#3-why-architecture-matters-for-safety)
4. [What Theory and Evidence Say About Serial Depth](#4-what-theory-and-evidence-say-about-serial-depth)
5. [Detection Methods by Access Level](#5-detection-methods-by-access-level)
6. [Combining Signals into a Verdict](#6-combining-signals-into-a-verdict)
7. [Validation on Known Models](#7-validation-on-known-models)
8. [The Toolkit](#8-the-toolkit)
9. [Guardrails and Responsible Disclosure](#9-guardrails-and-responsible-disclosure)
10. [Recommendations](#10-recommendations)
11. [Checklists](#11-checklists)
12. [References](#12-references)
- [Document History](#document-history)

---

## How to Use This Guide

| If you are... | Start with | Then read |
|---------------|------------|-----------|
| A safety researcher or evaluator | Section 5 (methods) and Section 6 (scoring) | Sections 7 and 11 |
| A policy body or regulator | Section 1 (summary) and Section 3 (why it matters) | Section 10 |
| A model developer | Section 3 and Section 10.2 | Section 9 |
| An auditor with open weights | Section 5.2 (white box) | Sections 7 and 8 |
| Anyone reading about a specific model | Section 3.6 (the 2026 Astra episode) | Section 6.4 (inconclusive verdicts) |

### Key Terms

| Term | Meaning in this guide |
|------|-----------------------|
| **Fixed-depth model** | A conventional transformer: each token passes once through a stack of distinct layers |
| **Recurrent-depth (looped) model** | A model that applies a shared block of layers more than once per token, with weights tied across iterations |
| **Loop count** | The number of times the shared block runs for a token; fixed, sampled, or chosen per token |
| **Adaptive depth** | Any mechanism that varies computation per token: halting, early exit, routing to more or fewer recursions |
| **Serial depth** | The length of the longest chain of dependent operations the model can perform before emitting the next token |
| **Latent reasoning** | Computation that influences the answer without being written out as tokens |
| **CoT monitoring** | Reading a model's chain of thought to catch intent to misbehave |
| **Signal** | One scalar measurement (for example, a latency slope) that bears on the architecture question |
| **Family** | A group of signals that share confounders, such as all timing signals |

### Epistemic Markers

Key claims carry one of three markers, after the convention of this repository's ETRA reports:

| Marker | Meaning | Evidence standard |
|--------|---------|-------------------|
| **[O]** | Open-source documented | Published papers, model cards, system cards, dated reporting |
| **[E]** | Analytic judgment | The author's reasoned inference from documented evidence; gaps acknowledged |
| **[S]** | Speculative | Plausible but untested; significant uncertainty |

> [!NOTE]
> **Rumors are labeled as rumors.** Where this guide discusses what a developer is *reported* to have built, it says who reported it and whether the developer confirmed it. A report is never treated as an architecture fact.

---

## 1. Executive Summary

Looped transformers are no longer a curiosity. Open recurrent-depth models (Huginn-0125, the Ouro family) match much larger fixed-depth models on reasoning benchmarks [4][5]; recursion can be retrofitted into pretrained models [7][8][9]; and in September 2026 a frontier model was reported, on anonymous sourcing, to use "recurrent depth", a claim its developer neither confirmed in its system card nor fully denied (Section 3.6) [50][51][52].

Architecture matters for safety because the main window into how today's reasoning models think is their chain of thought, and that window depends on hard serial computation having to pass through tokens [27]. A model that can iterate inside the forward pass needs to verbalize less. Whether it does so in practice is an empirical question, but evaluators cannot even ask it without knowing which kind of model they are testing.

The guide's central claims:

| # | Claim | Marker | Confidence |
|---|-------|--------|------------|
| 1 | White-box inspection is decisive when available: looped models must tell their code how many iterations to run, and published configs do (Huginn: `mean_recurrence`; Ouro: `total_ut_steps`) | [O] | High |
| 2 | Weights alone can hide looping: a block that is reused is stored once, so a looped checkpoint looks like a shallow one unless the config or code is read | [O]/[E] | High |
| 3 | Adaptive per-token depth predicts that time to first token rises with an item's serial difficulty at fixed prompt and output length; fixed-depth dense models predict no such slope | [E] | Medium |
| 4 | Timing evidence is fragile: batching, queueing, speculative decoding, caching, mixture-of-experts routing, and hidden reasoning tokens all move latency, and adaptive depth is hard to batch, so providers may serve a fixed loop count that leaves no slope at all | [O]/[E] | High |
| 5 | Behavioral probes (state tracking, k-hop composition, parity, reachability, asked without chain of thought) measure serial capability in a single pass, which matters for monitoring whatever the architecture; they discriminate architecture only weakly | [O]/[E] | Medium |
| 6 | Log-probability access adds width estimates [30][31] and, combined with compute and capacity estimates, a compute-to-capacity ratio that points up for looping and down for mixture-of-experts | [O]/[S] | Low to medium |
| 7 | Signals should be combined as capped log-likelihood ratios, discounted within families that share confounders, with a decided verdict only when two independent families agree; otherwise the honest answer is "inconclusive" | [E] | High |
| 8 | No black-box classifier should be trusted until it has been benchmarked, leave-one-out, on open looped and fixed-depth models served the same way | [E] | High |

```mermaid
flowchart LR
    W["White box<br/>config, code, weights,<br/>activations"] --> V["Verdict<br/>recurrent / fixed /<br/>inconclusive"]
    G["Gray box<br/>log-probabilities,<br/>published budgets"] --> V
    B["Black box<br/>timing and serial-depth<br/>behavior via the API"] --> V
    classDef strong fill:#E0F2F1,stroke:#00838F,color:#1C2233
    classDef mid fill:#EEF0FA,stroke:#1A237E,color:#1C2233
    classDef weak fill:#FFF0CC,stroke:#C77700,color:#1C2233
    class W strong
    class G mid
    class B weak
```

*Figure 1. The evidence ladder: the less access you have, the weaker each signal and the more of them you need to agree.*

> [!IMPORTANT]
> **Five working principles**
>
> 1. **Prefer direct observation.** If a config, model card, or modeling code is available, read it first. Everything else is inference.
> 2. **Hold length fixed.** Every timing comparison must hold prompt length and output length constant, or it measures text length, not computation.
> 3. **Treat confounders as hypotheses.** For each signal, name the non-recurrent explanations and test them.
> 4. **Calibrate on known models.** A detector that has not been scored on open looped and fixed-depth models has no known error rate.
> 5. **Allow "inconclusive".** A verdict forced from weak evidence is worse than no verdict, because it will be quoted.

### 1.1 What This Guide Does Not Cover

> [!WARNING]
> **Out of scope.** This guide does not cover, and the toolkit does not implement:
>
> - recovering weights, embedding matrices, or any other model parameters;
> - bypassing authentication, rate limits, content filters, or other access controls;
> - side channels that require co-location with other customers' workloads or observation of other users' traffic;
> - attribution of a model's identity for competitive purposes.
>
> Width estimation from log-probabilities is discussed because it is published, cheap, and reveals one number about shape. It is not a step toward reconstructing a model, and Section 9 sets limits on how it is used.

---

## 2. Architecture Taxonomy

> **In brief.** "Looped" covers several designs that differ in what is shared, how the iteration count is set, and whether intermediate computation appears as tokens. Several other techniques change per-token compute or latency without adding serial depth; they are the main confounders.

### 2.1 Fixed-Depth Baseline

A standard decoder-only transformer passes each token through L distinct layers once. Its serial depth per token is fixed at L, and its per-token compute is proportional to the parameters it uses. Theory shows that such a model has hard limits on problems that require long chains of sequential steps unless it writes intermediate steps out as tokens (Section 4).

### 2.2 Weight-Tied Looping

The shared-block idea goes back to the **Universal Transformer** (Dehghani et al., 2018), which applied one transformer block repeatedly with a learned halting mechanism [1]. Current designs:

- **Huginn-0125** (Geiping et al., 2025): 3.5B parameters trained on 800B tokens [4]. A 2-layer *prelude* embeds the input, a 4-layer *core block* is iterated, and a 2-layer *coda* decodes. The core is run a random number of times during training (mean 32, sampled from a log-normal Poisson distribution) with the embedded input re-injected at each step, so at inference the loop count can be raised: 32 iterations unroll to 132 effective layers, and the authors evaluate up to 64. They report reasoning gains up to a compute load equivalent to about 50B parameters [O].
- **Ouro / LoopLM** (Zhu et al., ByteDance and collaborators, 2025): 1.4B and 2.6B looped models trained on 7.7T tokens, reported to match fixed-depth models up to 12B on many benchmarks [5]. The whole 24-layer (1.4B) or 48-layer (2.6B) stack is looped up to 4 times, with a learned exit gate trained by an entropy-regularized objective [O].
- **Retrofitted recurrence**: Relaxed Recursive Transformers convert pretrained models into layer-sharing ones and restore flexibility with per-layer LoRA [7]; McLeish et al. (2025) loop a block of a pretrained model with a recurrence curriculum and report better math accuracy per unit of compute than post-training the original model [8]; a 2026 preprint retrofits recurrent depth into Qwen2.5-0.5B-Instruct and reports that the recurrent model beats a scratchpad model (84% versus 72%) on its task while answering 7.6 times faster [9] [O].
- **Fixed-point models**: Deep Equilibrium Models solve directly for the fixed point of a weight-tied layer [41], and 2026 "attractor" language models extend the idea [46] [O].

### 2.3 Adaptive Iteration

Adaptive depth lets the model spend more iterations on harder tokens:

- **Halting** learned end to end: Adaptive Computation Time [2], PonderNet [3], and the Universal Transformer's halting [1].
- **Exit gates in looped LMs**: Ouro's gate outputs a per-step exit probability; deployment exits at the first step where the cumulative probability passes a threshold q [5]. Huginn exits when the KL divergence between successive steps' next-token distributions falls below 5x10^-4 [4].
- **Token-level routing**: Mixture-of-Recursions assigns each token its own recursion depth with lightweight routers and caches keys and values only for tokens still active [6]; RecurTrace (2026) adds a learned halting head [45]; LoopFormer (2026) trains for budget-conditioned depth [44] [O].

### 2.4 Latent-Thought Tokens

A different route to unwritten computation feeds hidden states back as inputs. **Coconut** passes the last hidden state back as the next input embedding ("continuous thought") instead of decoding a word [10]. **Pause tokens** [11] and **filler tokens** [12] give a fixed-depth model extra positions to compute on without meaningful text. These add serial steps *across positions*, not depth within a position, but they share the monitoring problem: the intermediate steps are not readable language [O].

### 2.5 Early Exit

Early-exit methods skip the remaining layers when the model is already confident: CALM reports up to 3x speedup [15]; LayerSkip pairs early exit with self-speculative decoding [16]. These *reduce* depth on easy tokens rather than adding it, but they produce the same observable pattern as adaptive looping (harder tokens take longer) and must be treated as a confounder [O]/[E].

### 2.6 Small Recursive Reasoners

The Hierarchical Reasoning Model (27M parameters, two interdependent recurrent modules) [13] and the Tiny Recursive Model (7M parameters, a single 2-layer network applied recursively; 45% on ARC-AGI-1 and 8% on ARC-AGI-2) [14] show how far recursion can substitute for parameters on puzzle tasks. They are not language models, but they are evidence that serial depth, not size, is the binding resource on some problems [O].

### 2.7 Confounders That Are Not Recurrence

| Technique | What it changes | Why it confuses detection |
|-----------|-----------------|---------------------------|
| Mixture-of-experts | Active parameters per token | Per-token compute can vary with routing; compute is *below* stored parameters, the opposite direction to looping |
| Mixture-of-Depths [17] | Which tokens a layer processes | Per-token compute varies with content, like adaptive depth, without iteration |
| Early exit [15][16] | Layers used per token | Latency rises with difficulty, like adaptive looping |
| Speculative decoding [18] | Tokens accepted per target-model step | Inter-token latency depends on how predictable the text is [32] |
| Batching and queueing | Time waiting for and sharing the GPU | Latency depends on other traffic, often more than on your request |
| Prefix caching | Prefill work for repeated prefixes | Repeated prompt prefixes run faster [33] |
| Hidden reasoning tokens | Tokens generated but not shown | The most important confounder for "invisible thinking": the extra compute is ordinary decoding, billed but not displayed |

```mermaid
flowchart LR
    subgraph FX["Fixed depth"]
      direction TB
      f1["Layer 1"] --> f2["Layer 2"] --> f3["..."] --> f4["Layer L"]
    end
    subgraph LP["Looped (prelude, core x r, coda)"]
      direction TB
      p["Prelude"] --> c["Core block<br/>(shared weights)"]
      c -- "repeat r times" --> c
      c --> d["Coda"]
    end
    subgraph AD["Adaptive"]
      direction TB
      a1["Shared block"] --> g{"Exit gate or<br/>KL settled?"}
      g -- "no" --> a1
      g -- "yes" --> o["Emit token"]
    end
    classDef fx fill:#EEF0FA,stroke:#1A237E,color:#1C2233
    classDef lp fill:#FFF0CC,stroke:#C77700,color:#1C2233
    classDef ad fill:#E0F2F1,stroke:#00838F,color:#1C2233
    class f1,f2,f3,f4 fx
    class p,c,d lp
    class a1,g,o ad
```

*Figure 2. Three per-token computation patterns. Only the last two reuse weights; only the last varies its depth per token.*

| Design | Weights reused | Iterations | Unwritten serial steps | Detectable from |
|--------|----------------|------------|------------------------|-----------------|
| Fixed-depth transformer | No | 1 | Bounded by L | (baseline) |
| Looped, fixed count (Ouro at a set step count) | Yes | Fixed | Up to r times the block depth | Config; compute versus capacity |
| Looped, adaptive (Huginn exit, Ouro gate, MoR) | Yes | Per token | Varies by token | Config; timing slope; behavior |
| Latent-thought tokens (Coconut, pause) | No | 1 per position | Across hidden positions | Token counts; timing per hidden position |
| Early exit | No | 1 (shortened) | Fewer than L | Timing (looks adaptive) |
| Hidden reasoning tokens | No | 1 per token | Across hidden tokens | Usage fields; billing |

---

## 3. Why Architecture Matters for Safety

> **In brief.** The case rests on one mechanism: looping lets a model do more sequential work per token without writing it down. That erodes chain-of-thought monitoring, moves test-time compute out of sight, allows effort to vary invisibly by input, breaks compute accounting based on parameter counts, and strains interpretability tools built for fixed stacks. Some of this is documented, some is reasoned inference, and the strength of each claim is marked.

### 3.1 Chain-of-Thought Monitoring

A 2025 position paper by researchers across several labs argued that chain-of-thought monitoring is "a new and fragile opportunity": for hard tasks, models must reason in tokens, and those tokens can be read by a monitor [27]. The paper names latent reasoning in continuous spaces as one way the window could close [O]. OpenAI researchers showed that a monitor reading the chain of thought catches reward hacking more effectively than one watching actions alone, and that optimizing against the monitor teaches models to hide intent [28] [O]. Emmons et al. found that when chain of thought is necessary for a task, models struggle to evade monitors without substantial help [29] [O].

The link to architecture follows from theory (Section 4): a fixed-depth transformer *needs* tokens to run long serial computations, which is exactly what makes those computations visible. A looped model can run some of them internally [19]. **[E]** Recurrence does not make monitoring impossible: the amount of hidden computation is bounded by loop count times block depth, and intermediate loop states may be decodable (Section 5.2.4). It does move the boundary of what must be verbalized.

### 3.2 Test-Time Compute Inside the Forward Pass

Reasoning models scale capability by generating more tokens. Recurrent-depth models offer a second axis: more iterations per token [4][5]. Huginn's accuracy on harder tasks keeps improving with more iterations, while easy tasks saturate around 8 [4] [O]. **[E]** Compute spent this way is invisible to anyone counting tokens, and on an API it may not show up in usage or billing.

### 3.3 Invisible, Selective Effort

With adaptive depth, the model decides how much to compute per token. Huginn's own analysis shows that it already varies effort by content: exits come later on moral-scenario questions than on high-school mathematics, by about 3.5 steps on average [4] [O]. **[S]** A model with situational awareness could in principle spend extra hidden computation on inputs it recognizes as evaluations, or spend less while appearing to try (sandbagging), without any trace in its visible reasoning. There is no public evidence of a looped model doing this. The concern is that the mechanism for content-dependent hidden effort exists, and that evaluation awareness in frontier models is rising (Section 3.6), so the two together deserve measurement rather than assumption.

### 3.4 Compute Accounting and Thresholds

Governance frameworks use compute as a proxy for capability. The EU AI Act presumes that a general-purpose model has high-impact capabilities when cumulative training compute exceeds 10^25 floating-point operations [56] [O]. **[E]** Training compute that is measured directly is unaffected by looping. Compute that is *estimated* from parameter count and tokens (the common 6ND rule of thumb) undercounts a looped model by roughly its loop factor, because each stored parameter is used r times per token. Inference compute becomes input-dependent under adaptive depth, so thresholds and evaluations framed in per-token cost are moving targets. Disclosure of loop counts (Section 10) closes this gap; external estimation can only bound it.

### 3.5 Interpretability Transfer

Tools such as the logit lens [37], the tuned lens [38], probing, and layer-wise representation similarity [39] assume a fixed layer index. In a looped model, "layer 3" is visited r times with different meanings. Lu et al. applied logit-lens and coda-lens probing to Huginn and found only limited evidence of interpretable latent chain of thought, with more recurrence giving marginal gains on their arithmetic tasks [40] [O]. **[E]** Tools need to be re-indexed by iteration, and their validity re-established, before their outputs on looped models are trusted.

### 3.6 Case Study: the 2026 Astra Reports

This episode shows why external detection matters and why it must stay calibrated.

| Date (2026) | Event | Status |
|-------------|-------|--------|
| 1 September | *The Information* reports, citing an anonymous source, that OpenAI's upcoming Astra model uses "recurrent depth", also called a looped transformer | Reported; paywalled, not read directly here; relayed by [51][53] |
| 2 September | OpenAI chief scientist Jakub Pachocki posts that "the depth of the computation graph for our present frontier models, including Astra, is within a factor of two of GPT-4" and calls the reporting confused [52] | Developer statement; neither confirms nor rules out limited looping |
| 3 September | Fortune reports that OpenAI researchers said use of the looped architecture was limited to keep reasoning readable, and that OpenAI did not deny using the technique; outside researchers call for an industry standard on monitorability [51] | Reported characterization |
| 3 September | The GPT-6 Astra system card states that "GPT-6 Astra's monitorability has decreased relative to GPT-5.6 Sol" and that OpenAI is "quite confident that changes in CoT controllability are not differentially due to any architectural changes" [50] | Primary source; architecture not described |
| September | The card reports that "the set of tasks Astra is able to accomplish without the use of CoT is greatly expanded"; UK AISI measured a no-CoT time horizon of 30.9 minutes against 3.6 minutes for GPT-5.6 Sol and attributed it to "a greatly increased ability to reason within a single forward-pass" [50] | Primary source |

**What follows from this [E].** The safety-relevant fact, documented by the developer, is that more reasoning now fits in a single forward pass and that chain-of-thought monitoring has become less effective. Whether looping causes that is undetermined: the developer attributes the controllability change to training rather than architecture; one independent commentator argues gains come mainly from training recipes and data [53]; another estimates three to four loops and notes that the larger concern is that loop count is a dial that could be turned up later [54]. These are opinions, not measurements. The measurements in Section 5 are designed for exactly this situation: they would help settle whether a deployed model's in-pass serial capability, latency, and compute behave like a fixed or a looped model, without needing the weights.

### 3.7 The Counter-Case

Looping has real benefits and the risk case is partly speculative:

- **Efficiency.** Fewer parameters for the same reasoning means cheaper deployment and smaller models that fit on local hardware [5][14].
- **Faithfulness claims.** Ouro's authors report that LoopLM reasoning traces align more closely with final outputs than explicit chain of thought, and that harmfulness on the HEx-PHI benchmark falls as recurrent steps increase [5] [O]. These are the authors' measurements, not yet independently replicated.
- **Bounded hidden computation.** Serial depth per token is still bounded by loop count times block depth; there is no unbounded hidden state carried across tokens as in a classic RNN [E].
- **Possible readability.** Intermediate loop states can be decoded through the coda or a lens, and Ouro's design produces a valid next-token distribution at every step [5][40] [O]. Whether those readouts are faithful enough to monitor is open.
- **Saturation.** Ouro's accuracy *falls* when run beyond its trained four steps (for example, the 2.6B Thinking model drops from 76.44 at four steps to 39.26 at eight on OlympiadBench) [5] [O], so "turn the dial up" is not free for every design.

> [!NOTE]
> **Balanced reading.** Looping is a capability and efficiency technique with a specific monitoring cost. The cost is real in mechanism and documented in its symptoms (Section 3.6), but which deployed systems carry it, and how much, is not publicly known. That is the gap this guide addresses.

---

## 4. What Theory and Evidence Say About Serial Depth

> **In brief.** Theory says fixed-depth transformers cannot solve some sequential problems in one pass, and that looping or chain of thought lifts the limit. Those same problems make the behavioral probes in Section 5.4.

- **Fixed depth is limited.** Hahn proved that self-attention cannot model periodic finite-state languages (parity is the classic case) or hierarchical structure unless layers or heads grow with input length [26]. Merrill, Petty, and Sabharwal showed that transformers and state-space models alike cannot solve state tracking such as permutation composition for long sequences [25] [O].
- **Chain of thought helps in proportion to its length.** Merrill and Sabharwal showed that intermediate generation extends a transformer's power, by an amount that depends on the number of steps [23] [O].
- **Depth growth helps too.** Transformers whose depth grows logarithmically with input length can recognize regular languages and solve graph connectivity, which fixed-depth ones cannot under standard conjectures [24] [O].
- **Loops can stand in for tokens.** Saunshi et al. showed that a k-layer transformer looped L times nearly matches a kL-layer model on reasoning tasks (addition, p-hop induction, math), that looped models can simulate T steps of chain of thought with T loops, and that looping helps reasoning far more than memorization [19] [O]. Looped transformers can emulate programmable computers [20], learn learning algorithms with under 10% of the parameters [21], and generalize to longer inputs when the step count adapts [22] [O].
- **Language models do some latent multi-hop reasoning already**, with strength that varies by relation [49] [O].

**Implication for detection [E].** Ask problems whose serial depth you control, in a format that forbids writing steps out. A fixed-depth model's accuracy should fall as depth passes what its layers can do in one pass; a looped model's should hold up for longer, and an adaptive one should spend more time on deeper items. Accuracy curves alone confound depth with scale (a larger fixed model also holds up longer), which is why Section 6 never lets behavior decide alone.

---

## 5. Detection Methods by Access Level

> **In brief.** Each method is described by the signal it yields, its confounders, and its evidence strength. White-box methods observe; gray- and black-box methods infer.

### 5.1 Overview

| Method | Access | Signal | Main confounders | Strength |
|--------|--------|--------|------------------|----------|
| Config and code inspection | White | Declared loop count, exit settings | Custom code that loops without declaring it | Decisive when positive |
| Exact or low-rank layer sharing | White | Duplicate or low-rank-related layer weights | Pruned or merged models | Strong |
| Declared versus stored depth | White | Fewer distinct layers than declared | Export quirks | Strong |
| Hidden-state convergence | White | Contraction toward a fixed point across iterations | Normalization effects | Moderate |
| Logit-lens settling | White | Per-token step at which predictions stop changing | Early-exit models settle too | Moderate |
| Width from log-probabilities | Gray | Hidden size | (descriptive, not diagnostic alone) | Context only |
| Compute-to-capacity ratio | Gray | Compute per token above stored capacity | Every input is a rough estimate | Weak |
| TTFT and inter-token slope | Black | Latency rises with serial depth at fixed length | Batching, queueing, early exit, MoD, speculative decoding | Moderate if controlled |
| Serial-depth retention | Black | No-CoT accuracy holds as depth grows | Model scale, training data | Weak alone |
| Compute knob sensitivity | Black | Latency and accuracy rise with a budget setting without extra tokens | Hidden reasoning tokens, routing to another model | Moderate |
| Family fingerprinting [35][36] | Black | Which known model family an endpoint resembles | Fine-tuning, system prompts | Context (sets the prior) |

### 5.2 White Box: Open Weights

#### 5.2.1 Config and code

Looped models must tell their modeling code how many iterations to run. In the published configs, Huginn declares `mean_recurrence` (32) and `n_layers_in_recurrent_block` (4) alongside prelude and coda sizes, for an effective depth of 132; Ouro declares `total_ut_steps` (4) and `early_exit_threshold`; ALBERT declares layer-group sharing with `num_hidden_groups` [4][5] [O]. The toolkit's `inspect-config` classified all eight published configs it was run on correctly (Section 7.3).

Absence is weak evidence. A config can omit recurrence if the modeling code (`auto_map`, `trust_remote_code`) loops anyway. Read the forward method: a loop over a shared module, or a module list that repeats the same object, is decisive.

#### 5.2.2 Parameter sharing in the weights

Three patterns, in decreasing order of directness:

1. **Exact duplicates.** Two layer slots hold byte-identical tensors (some exports write a shared block once per use).
2. **Low-rank relation.** The difference between two layers is low rank, as in a shared base matrix plus per-layer LoRA deltas [7]. Independent trained layers have full-rank differences: on SmolLM2-135M, adjacent layers' weight matrices are 1.32 to 1.41 apart in relative Frobenius distance, close to the square root of two expected for unrelated matrices of equal norm (Section 7.3).
3. **Storage-level reuse.** **[O]/[E]** A block that is looped is stored once. Huginn's checkpoint stores 8 layers; Ouro-1.4B stores 24 and runs them up to 4 times. Weight files alone therefore look like a shallow model, and only the config, the code, or a compute-versus-capacity mismatch reveals the looping.

#### 5.2.3 Representation similarity

Layer-by-layer similarity matrices (cosine or linear CKA [39]) show block structure in most models; Lad et al. and Gromov et al. document how redundant many deeper layers are [47][48]. A repeated block can produce a periodic pattern in such matrices. The toolkit measures this as excess similarity at one lag over its neighbors; on SmolLM2-135M the excess is 0.002, effectively none. **[E]** This is a heuristic: weight reuse does not guarantee repeated representations, so treat it as supporting evidence only.

#### 5.2.4 Iterate the core and watch it converge

The most informative activation test runs the suspected core block repeatedly and records the state after each iteration.

- Huginn's authors report that many tokens' states converge to a fixed point, some fall into orbits on harder problems, and some drift steadily in one direction ("sliders"), possibly acting as counters [4] [O].
- A fixed-depth model has no reason to converge across layers: on SmolLM2-135M the ratio of successive relative state changes over the last half of the stack is 1.12 (not contracting) (Section 7.3).
- Logit-lens decoding [37] of each iteration gives a per-token *settling step*, the iteration after which the decoded distribution stops changing. Huginn uses exactly this quantity (KL below 5x10^-4) as its exit rule [4]. Wide variation in settling steps across tokens, correlated with difficulty, is direct evidence of adaptive depth.

> [!CAUTION]
> **Repeating a fixed model's layer is a weak control.** Fixed-depth models tolerate deleting, swapping, and sometimes duplicating middle layers [47][48]. A layer that survives being repeated is not evidence of recurrent training. The contrast that matters is *convergence* under iteration, not mere robustness.

### 5.3 Gray Box: Log-Probabilities

- **Width.** The final layer maps a d-dimensional state to the vocabulary, so logit vectors from many prompts span at most d dimensions. Carlini et al. used this to confirm hidden sizes of 1024 and 2048 for OpenAI's Ada and Babbage models [30]; Finlayson et al. estimated gpt-3.5-turbo's embedding size at about 4096 and showed the same "model image" can detect model updates and identify the source model [31] [O]. Width alone says nothing about looping.
- **Compute-to-capacity ratio [S].** Combine an estimate of compute per token (from decode latency on known hardware, or a published figure) with an estimate of stored capacity (from width, a published size, or memorization probes). Looping pushes compute above what the stored parameters would cost once; mixture-of-experts pushes it below. Ouro's authors report that looped and non-looped models store knowledge similarly, so the advantage comes from knowledge manipulation rather than capacity [5], which is what makes capacity a usable denominator in principle. Every input has wide error bars; the toolkit caps this signal low.
- **Use limits.** Section 9 restricts this to vectors you are entitled to collect, at the rate limits you are given, and to estimating one shape parameter, never weights.

### 5.4 Black Box: API Access

#### 5.4.1 Timing

**Hypothesis.** With adaptive per-token depth, items needing more serial steps should get more iterations, so the time to first token (TTFT) and the inter-token latency (ITL) should rise with serial depth even when prompt and output lengths are identical. With a fixed-depth dense model they should not [E].

**Design controls.**

- **Constant length.** The toolkit's task generators keep prompt length identical across depths within each family (fixed-width fields, identity operations written in the same form as real ones, fixed edge counts) and cap the output at a few tokens.
- **Interleaving.** All conditions are shuffled into one seeded random order, so drift in server load spreads across depths.
- **Log scale and pooling.** Regress log latency on depth (with prompt tokens as a covariate when they vary), trim the slowest 5% per family, and pool families by inverse variance. The result is a z-score.
- **Exclusion of hidden tokens.** Requests whose usage reports reasoning tokens are dropped: hidden decoding is the most likely non-architectural cause of a latency slope.

**Confounders.**

| Confounder | Effect | Mitigation |
|------------|--------|------------|
| Batching and queueing | Large, variable delays unrelated to your request | Interleave; repeat; use medians; compare differences between consecutive tokens, which cancel shared delay [32] |
| Speculative decoding | ITL depends on how predictable the text is; detectable by its own signature [32] | Use TTFT as the primary signal; keep outputs to one or two tokens |
| Early exit and Mixture-of-Depths | Content-dependent compute without iteration | Cannot be separated by timing alone; combine with other families |
| Prefix caching | Repeated prefixes run faster [33] | Randomize content so no two prompts share long prefixes |
| Routing to a different model | Latency changes with the route | Fingerprint responses [35]; check consistency |
| Network jitter | Noise | Repetition; differential timing |

**Strength [E].** A large pooled slope that survives all controls is moderate evidence of content-dependent compute, of which adaptive looping is one source. A null result is weak evidence against looping: a provider serving a **fixed** loop count produces no slope, and adaptive-depth inference is hard to batch. Schwethelm et al. (2026) describe the problem ("tokens with different numbers of loops cannot share a uniform forward pass") and propose continuous depth batching, which realizes up to 99% of the estimated available speedup on Ouro 1.4B and Huginn 3.5B [42] [O]. Whether production servers do this is unknown.

Published timing attacks show that per-token timing through ordinary streaming APIs is informative: Majidi et al. (2026) detect speculative decoding remotely, estimate draft-model context length, and rank candidate layer counts and hidden sizes for dense models from a timing model of NVIDIA GPUs [32]. Their timing model assumes a dense decoder with a fixed layer count and does not address looped or MoE models; extending it is an open problem [O]/[E].

#### 5.4.2 Serial-depth behavior

The toolkit's suite uses four families in which depth varies while prompt length stays fixed:

| Task | Depth parameter | Why it probes serial computation |
|------|-----------------|----------------------------------|
| Pointer chasing | Number of hops through a random single-cycle mapping | k-hop composition; no shortcut through short cycles |
| Permutation tracking | Number of real swaps among a fixed number of operations | Word problem over S5, the canonical state-tracking task [25] |
| Prefix parity | Length of the prefix whose parity is asked | Parity is outside fixed-depth attention's reach in general [26] |
| Graph reachability | Shortest-path length | Connectivity requires depth growing with path length [24] |

Each item demands the final answer only. The signals are the chance-corrected accuracy curve against depth and a *retention* ratio (deep third over shallow third). **[E]** These measure single-pass serial capability, which is safety-relevant whatever the architecture: it is the quantity that bounds how much reasoning can escape the chain of thought, and it is what UK AISI's no-CoT time horizon measures at a larger scale [50]. As an architecture discriminator they are weak, because scale and training also raise the curve.

Two contrasts make behavior more diagnostic:

- **Depth extrapolation shape.** Looped models trained to a fixed number of steps degrade sharply past it (Ouro) [5], while those trained with sampled counts improve with more steps up to saturation (Huginn) [4]. If an API offers a depth or budget control, the shape of accuracy against that setting is informative.
- **Manipulation versus storage.** Looping helps reasoning far more than memorization [19][5]. A model whose serial-depth accuracy is high *relative to* its factual recall, compared with fixed-depth models of similar recall, is more likely to be reusing computation. **[S]** This contrast is untested as a classifier.

#### 5.4.3 Compute knobs

Some APIs expose effort or budget parameters. If raising one increases latency and accuracy **while visible and billed output tokens stay the same**, extra computation is happening per token or before the first token. **[E]** The usual explanation today is hidden reasoning tokens, which usage fields often report; the toolkit excludes any request whose usage shows them. What remains after that exclusion is moderate evidence of in-pass compute scaling.

---

## 6. Combining Signals into a Verdict

> **In brief.** Treat each signal as a likelihood ratio between "recurrent" and "fixed", cap it, discount signals that share confounders, add a prior, and decide only when independent families agree.

### 6.1 Likelihood Ratios

For each signal s with value x, define class-conditional densities p(x | R) and p(x | F), estimated from reference models (Section 7). Its contribution is the log-likelihood ratio LLR(x) = log p(x | R) - log p(x | F), clipped to a cap (about log 20 for most signals) so that no single measurement dominates.

### 6.2 Families and Correlation

Signals in the same family share confounders, so adding their LLRs would double count. Within a family of n signals with mean contribution m, the family LLR is m x n_eff with n_eff = n / (1 + (n - 1) rho), rho = 0.5 by default, then clipped to a family cap. Families (white-box config, white-box weights, white-box dynamics, gray box, timing, behavioral, compute knob) are treated as independent. The posterior log-odds are the prior log-odds plus the sum of family LLRs.

### 6.3 Decision Rule

| Condition | Verdict |
|-----------|---------|
| Posterior at least 0.9 and at least two families support it with LLR of at least 0.5, or a white-box config or weights family supports it | **Recurrent** |
| Posterior at most 0.1 and the same agreement condition | **Fixed** |
| Anything else | **Inconclusive** |

Config evidence is asymmetric: a declared recurrence contributes +6, a standard fixed-depth architecture class -1.5, and unrecognized custom code 0.

```mermaid
flowchart LR
    S["Signals"] --> L["Per-signal LLR<br/>(clipped)"] --> F["Family LLR<br/>(discounted, clipped)"] --> P["Prior + sum<br/>= posterior"] --> D{"Threshold met and<br/>2 families agree?"}
    D -- "yes" --> V1["Recurrent or fixed"]
    D -- "no" --> V2["Inconclusive"]
    classDef a fill:#EEF0FA,stroke:#1A237E,color:#1C2233
    classDef b fill:#FFF0CC,stroke:#C77700,color:#1C2233
    class S,L,F,P a
    class D,V1,V2 b
```

*Figure 3. Scoring pipeline.*

### 6.4 Worked Example (Synthetic)

The toolkit's simulator plays a fixed-depth model and an adaptive recurrent one (synthetic profiles, not real systems). With likelihoods fitted to a simulated reference fleet and an uninformative config signal (custom code), the recurrent endpoint scores timing +3.0, compute knob +2.0, behavioral -0.06, for a posterior of 0.993: **recurrent**. The fixed endpoint scores timing -2.97 and knob -1.98, posterior 0.007: **fixed**. With the *uncalibrated* default likelihoods, the same recurrent endpoint scores 0.883: **inconclusive**. That is the intended behavior: without calibration the scorer is conservative.

### 6.5 Priors

Set the prior from what is known about the developer and model family: public statements, papers, model cards, and family fingerprints [35][36]. Report the verdict at more than one prior. A verdict that flips between priors of 0.2 and 0.8 is driven by the prior, not the evidence.

---

## 7. Validation on Known Models

> **In brief.** Before measuring an undisclosed model, measure models whose architecture is documented, with the same plan and serving setup, and report the classifier's coverage and errors under leave-one-out.

### 7.1 Reference Sets

| Group | Candidates (open weights) |
|-------|---------------------------|
| Looped, sampled count | Huginn-0125 [4] |
| Looped, fixed count with exit gate | Ouro-1.4B, Ouro-2.6B and Thinking variants [5] |
| Retrofitted recurrence | Released retrofitting checkpoints [8] |
| Token-level recursion | Mixture-of-Recursions checkpoints, where released [6] |
| Fixed depth, similar size | Qwen2.5 0.5B to 3B, SmolLM2, OLMo-2, Llama 3.2 |
| Confounder controls | An MoE model (Qwen1.5-MoE-A2.7B); an early-exit model (LayerSkip checkpoints [16]); a speculative-decoding server configuration |

Serve all of them with the same inference server, hardware, batching settings, and sampling parameters. A difference in serving stack can produce a timing difference larger than the architectural one.

### 7.2 Protocol

1. Run the identical probe plan against every reference and the target.
2. Label references from their documentation only.
3. Leave each reference out in turn, fit likelihoods to the rest, and score it.
4. Report coverage (fraction decided), accuracy among decided verdicts, the number of wrong decided verdicts, Brier score, and log loss.
5. Repeat at more than one load level (quiet and busy hours), because batching changes timing.
6. Only then score the target, with the fitted likelihoods and several priors.

### 7.3 Results So Far

| Check | Data | Result |
|-------|------|--------|
| Config inspection | 8 published configs | All correct: Huginn-0125, Ouro-1.4B, Ouro-2.6B-Thinking, ALBERT-base-v2 recurrent or weight-shared; Qwen2.5-0.5B, SmolLM2-135M, OLMo-2-1B standard; Qwen1.5-MoE-A2.7B standard with an MoE note |
| Weight sharing, real fixed model | SmolLM2-135M (30 layers) | 30 distinct layers, no exact or low-rank pairs, adjacent distance 1.32-1.41 (no false positive) |
| Dynamics, real fixed model | SmolLM2-135M, 48 tokens | Tail contraction 1.12 (not converging), periodicity excess 0.002 |
| Scoring, synthetic fleet | 6 fixed and 6 recurrent simulated endpoints | Leave-one-out coverage 0.75, 0 wrong decided verdicts, Brier 0.016; all 3 undecided were recurrent |
| Black-box probes, real APIs | none yet | **Not yet run** |

> [!WARNING]
> **What has not been done.** No black-box measurement of any real endpoint has been made for this guide, and the white-box checks have not yet been run on a real looped model's weights or per-iteration activations. The simulated fleet tests the pipeline, not the world. The first real benchmark should be the reference set in Section 7.1.

### 7.4 Adversarial Robustness

A provider that does not want its architecture inferred can pad latency to a constant per token or buffer tokens and release them at fixed intervals, both of which Majidi et al. discuss as defenses at a cost in latency [32]. Either would remove the timing family. Behavioral and compute-knob signals would remain, but they are the weaker ones. **[E]** External detection is therefore a complement to disclosure, not a substitute for it.

---

## 8. The Toolkit

The companion package [`packages/recurrent_depth/`](../../packages/recurrent_depth/) implements the measurements and scoring above. It depends only on numpy (torch and transformers optionally, for recording activations), runs in the repository's `python-ci` container, and its tests run without network or GPU.

| Command | Section | What it does |
|---------|---------|--------------|
| `inspect-config` | 5.2.1 | Classifies a `config.json`; reports declared loops, exit settings, MoE fields, stored versus logical depth |
| `inspect-weights` | 5.2.2 | Memory-maps safetensors (including sharded and BF16), finds exact and low-rank layer sharing, compares declared and stored depth |
| `analyze-hidden` | 5.2.3-5.2.4 | Contraction, similarity periodicity, logit-lens settling steps from a recorded trajectory |
| `probe` | 5.4 | Runs a seeded, interleaved serial-depth plan against an OpenAI-compatible endpoint with a request budget, rate limit, backoff, and a terms acknowledgement |
| `features` | 5.4 | Computes timing slopes, serial retention, and knob effects; drops requests with hidden reasoning tokens |
| `score` | 6 | Combines signal files into a verdict with per-family contributions and notes |
| `fit`, `validate` | 7 | Fits likelihoods to labeled references; leave-one-out benchmark |
| `simulate`, `simulate-fleet` | 6.4 | Synthetic endpoints for offline testing |

---

## 9. Guardrails and Responsible Disclosure

> **In brief.** Measure, do not extract. Stay inside the provider's terms and the law. Tell the provider before you tell the world.

- **Terms and law.** Query only endpoints you are authorized to use, within their terms of service and rate limits. Take legal advice where terms are unclear; this guide is not legal advice.
- **No extraction.** Do not attempt to recover weights, embedding matrices, or training data. Width estimation is limited to vectors you are entitled to collect, at your normal rate limits, and is reported as a single number.
- **No access-control bypass.** Do not use multiple accounts to evade rate limits, spoof clients, or probe infrastructure other than the public API.
- **No harm to other users.** Do not use techniques that infer other customers' prompts or traffic. Several published timing attacks do exactly that [33][34]; they are cited here as confounders, not methods.
- **Disclose first.** Share findings that reveal a provider's undisclosed design with the provider before publishing, and give them time to respond, as Majidi et al. did with their speculative-decoding finding [32].
- **Publish carefully.** Publish verdicts with their evidence, priors, coverage, and error rates. Never publish a verdict without its uncertainty, and never present a reported architecture as fact.

---

## 10. Recommendations

### 10.1 For Evaluators

1. Measure single-pass serial capability (no-CoT accuracy against controlled depth) for every frontier model you evaluate, whatever its architecture.
2. Ask developers for architecture details under your access agreement before inferring them.
3. When you infer, publish the method, the reference benchmark, and the inconclusive rate.

### 10.2 For Developers

1. Disclose loop counts, whether they are adaptive, and their range at inference, in model or system cards.
2. Report chain-of-thought monitorability and no-CoT capability together, as the Astra card does [50], and say whether in-pass recurrence contributes.
3. Offer per-iteration readouts (decoded intermediate states) to monitors and auditors, since looped models can produce them [5].
4. Count training and inference compute directly, not from parameter counts.

### 10.3 For Policy Bodies

1. Require disclosure of maximum serial depth per token (layers times loops) alongside parameter count for models above existing compute thresholds.
2. Do not estimate compute from parameter counts for models that may reuse parameters.
3. Treat external architecture inference as evidence to prompt questions, not as findings, unless it is benchmarked and decisive.

### 10.4 Open Research Problems

- Extending per-token timing models [32] to looped and MoE architectures.
- Testing whether intermediate loop readouts are faithful enough to monitor.
- Measuring whether looped models vary hidden effort on evaluation-like inputs.
- Validating the manipulation-versus-storage contrast as a black-box classifier.

---

## 11. Checklists

### Before Probing an Endpoint

- [ ] Authorized to use the endpoint; plan within terms of service and rate limits
- [ ] Request budget and rate limit set; `acknowledge_terms` set truthfully
- [ ] Reference models chosen and served on the same stack
- [ ] Classifier benchmarked leave-one-out on the references
- [ ] Priors chosen and written down before seeing target results

### Per Measurement Run

- [ ] Prompt length constant across depths within each family
- [ ] Output capped and constant; temperature 0
- [ ] Conditions interleaved in a seeded random order
- [ ] Requests with hidden reasoning tokens excluded
- [ ] Run repeated at a second load level

### Before Publishing a Verdict

- [ ] Verdict reported with posterior, family contributions, and priors
- [ ] Coverage and errors from validation reported
- [ ] Confounders that could not be excluded listed
- [ ] Provider informed and given time to respond
- [ ] Reported or rumored architecture claims labeled as such

---

## 12. References

1. M. Dehghani et al., *Universal Transformers*, arXiv:1807.03819, 2018. https://arxiv.org/abs/1807.03819
2. A. Graves, *Adaptive Computation Time for Recurrent Neural Networks*, arXiv:1603.08983, 2016. https://arxiv.org/abs/1603.08983
3. A. Banino, J. Balaguer, and C. Blundell, *PonderNet: Learning to Ponder*, arXiv:2107.05407, 2021. https://arxiv.org/abs/2107.05407
4. J. Geiping et al., *Scaling up Test-Time Compute with Latent Reasoning: A Recurrent Depth Approach*, arXiv:2502.05171, NeurIPS 2025. https://arxiv.org/abs/2502.05171 (weights: `tomg-group-umd/huginn-0125`)
5. R.-J. Zhu et al., *Scaling Latent Reasoning via Looped Language Models* (Ouro), arXiv:2510.25741, October 2025 (revised October 2026). https://arxiv.org/abs/2510.25741
6. S. Bae et al., *Mixture-of-Recursions: Learning Dynamic Recursive Depths for Adaptive Token-Level Computation*, arXiv:2507.10524, NeurIPS 2025. https://arxiv.org/abs/2507.10524
7. S. Bae et al., *Relaxed Recursive Transformers: Effective Parameter Sharing with Layer-wise LoRA*, arXiv:2410.20672, 2024. https://arxiv.org/abs/2410.20672
8. S. McLeish et al., *Teaching Pretrained Language Models to Think Deeper with Retrofitted Recurrence*, arXiv:2511.07384, 2025. https://arxiv.org/abs/2511.07384
9. M. Shapiro, *Retrofitting Recurrent Depth into a Pretrained Language Model: Installation, Extrapolation, Transfer, and Retention at Two Parameter Budgets*, arXiv:2608.11233, 2026. https://arxiv.org/abs/2608.11233
10. S. Hao et al., *Training Large Language Models to Reason in a Continuous Latent Space* (Coconut), arXiv:2412.06769, 2024. https://arxiv.org/abs/2412.06769
11. S. Goyal et al., *Think before you speak: Training Language Models With Pause Tokens*, arXiv:2310.02226, 2023. https://arxiv.org/abs/2310.02226
12. J. Pfau, W. Merrill, and S. R. Bowman, *Let's Think Dot by Dot: Hidden Computation in Transformer Language Models*, arXiv:2404.15758, 2024. https://arxiv.org/abs/2404.15758
13. G. Wang et al., *Hierarchical Reasoning Model*, arXiv:2506.21734, 2025. https://arxiv.org/abs/2506.21734
14. A. Jolicoeur-Martineau, *Less is More: Recursive Reasoning with Tiny Networks*, arXiv:2510.04871, 2025. https://arxiv.org/abs/2510.04871
15. T. Schuster et al., *Confident Adaptive Language Modeling*, arXiv:2207.07061, 2022. https://arxiv.org/abs/2207.07061
16. M. Elhoushi et al., *LayerSkip: Enabling Early Exit Inference and Self-Speculative Decoding*, arXiv:2404.16710, 2024. https://arxiv.org/abs/2404.16710
17. D. Raposo et al., *Mixture-of-Depths: Dynamically allocating compute in transformer-based language models*, arXiv:2404.02258, 2024. https://arxiv.org/abs/2404.02258
18. Y. Leviathan, M. Kalman, and Y. Matias, *Fast Inference from Transformers via Speculative Decoding*, arXiv:2211.17192, 2022. https://arxiv.org/abs/2211.17192
19. N. Saunshi, N. Dikkala, Z. Li, S. Kumar, and S. J. Reddi, *Reasoning with Latent Thoughts: On the Power of Looped Transformers*, arXiv:2502.17416, ICLR 2025. https://arxiv.org/abs/2502.17416
20. A. Giannou, S. Rajput, J. Sohn, K. Lee, J. D. Lee, and D. Papailiopoulos, *Looped Transformers as Programmable Computers*, arXiv:2301.13196, 2023. https://arxiv.org/abs/2301.13196
21. L. Yang, K. Lee, R. Nowak, and D. Papailiopoulos, *Looped Transformers are Better at Learning Learning Algorithms*, arXiv:2311.12424, 2023. https://arxiv.org/abs/2311.12424
22. Y. Fan, Y. Du, K. Ramchandran, and K. Lee, *Looped Transformers for Length Generalization*, arXiv:2409.15647, 2024. https://arxiv.org/abs/2409.15647
23. W. Merrill and A. Sabharwal, *The Expressive Power of Transformers with Chain of Thought*, arXiv:2310.07923, 2023. https://arxiv.org/abs/2310.07923
24. W. Merrill and A. Sabharwal, *A Little Depth Goes a Long Way: The Expressive Power of Log-Depth Transformers*, arXiv:2503.03961, 2025. https://arxiv.org/abs/2503.03961
25. W. Merrill, J. Petty, and A. Sabharwal, *The Illusion of State in State-Space Models*, arXiv:2404.08819, 2024. https://arxiv.org/abs/2404.08819
26. M. Hahn, *Theoretical Limitations of Self-Attention in Neural Sequence Models*, arXiv:1906.06755, 2019. https://arxiv.org/abs/1906.06755
27. T. Korbak et al., *Chain of Thought Monitorability: A New and Fragile Opportunity for AI Safety*, arXiv:2507.11473, 2025. https://arxiv.org/abs/2507.11473
28. B. Baker et al., *Monitoring Reasoning Models for Misbehavior and the Risks of Promoting Obfuscation*, arXiv:2503.11926, 2025. https://arxiv.org/abs/2503.11926
29. S. Emmons et al., *When Chain of Thought is Necessary, Language Models Struggle to Evade Monitors*, arXiv:2507.05246, 2025. https://arxiv.org/abs/2507.05246
30. N. Carlini et al., *Stealing Part of a Production Language Model*, arXiv:2403.06634, ICML 2024. https://arxiv.org/abs/2403.06634
31. M. Finlayson, X. Ren, and S. Swayamdipta, *Logits of API-Protected LLMs Leak Proprietary Information*, arXiv:2403.09539, COLM 2024. https://arxiv.org/abs/2403.09539
32. S. Majidi, N. Mireshghallah, and K. Taram, *Leaky Language Models: Stealing Architecture and Inference Optimizations via Per-Token Timing*, arXiv:2607.20723, July 2026. https://arxiv.org/abs/2607.20723
33. N. Carlini and M. Nasr, *Remote Timing Attacks on Efficient Language Model Inference*, arXiv:2410.17175, 2024. https://arxiv.org/abs/2410.17175
34. Zhang, Saileshwar, and Lie, *Time Will Tell: Timing Side Channels via Output Token Count in Large Language Models*, arXiv:2412.15431, 2024. https://arxiv.org/abs/2412.15431
35. D. Pasquini, E. M. Kornaropoulos, and G. Ateniese, *LLMmap: Fingerprinting For Large Language Models*, arXiv:2407.15847, 2024. https://arxiv.org/abs/2407.15847
36. M. Sun et al., *Idiosyncrasies in Large Language Models*, arXiv:2502.12150, 2025. https://arxiv.org/abs/2502.12150
37. nostalgebraist, *interpreting GPT: the logit lens*, LessWrong, 31 August 2020. https://www.lesswrong.com/posts/AcKRB8wDpdaN6v6ru/interpreting-gpt-the-logit-lens
38. N. Belrose et al., *Eliciting Latent Predictions from Transformers with the Tuned Lens*, arXiv:2303.08112, 2023. https://arxiv.org/abs/2303.08112
39. S. Kornblith, M. Norouzi, H. Lee, and G. Hinton, *Similarity of Neural Network Representations Revisited*, arXiv:1905.00414, ICML 2019. https://arxiv.org/abs/1905.00414
40. Lu et al., *Latent Chain-of-Thought? Decoding the Depth-Recurrent Transformer*, arXiv:2507.02199, 2025. https://arxiv.org/abs/2507.02199
41. S. Bai, J. Z. Kolter, and V. Koltun, *Deep Equilibrium Models*, arXiv:1909.01377, NeurIPS 2019. https://arxiv.org/abs/1909.01377
42. K. Schwethelm, D. Rueckert, and G. Kaissis, *Depth-adaptive Inference of Looped Language Models via Continuous Depth Batching*, arXiv:2608.09444, 2026. https://arxiv.org/abs/2608.09444
43. R. Lin, Y. Guo, R.-J. Zhu, H. Ye, and J. K. Eshraghian, *Allocating Recurrent Compute in Looped Language Models*, arXiv:2608.18230, 2026. https://arxiv.org/abs/2608.18230
44. Jeddi, Ciccone, and Taati, *LoopFormer: Elastic-Depth Looped Transformers for Latent Reasoning via Shortcut Modulation*, arXiv:2602.11451, 2026. https://arxiv.org/abs/2602.11451
45. Wang et al., *RecurTrace: Adaptive Latent Reasoning with Loop-Time Memory*, arXiv:2609.03379, 2026. https://arxiv.org/abs/2609.03379
46. Fein-Ashley and Rashidinejad, *Solve the Loop: Attractor Models for Language and Reasoning*, arXiv:2605.12466, 2026. https://arxiv.org/abs/2605.12466
47. A. Gromov et al., *The Unreasonable Ineffectiveness of the Deeper Layers*, arXiv:2403.17887, 2024. https://arxiv.org/abs/2403.17887
48. V. Lad et al., *The Remarkable Robustness of LLMs: Stages of Inference?*, arXiv:2406.19384, 2024. https://arxiv.org/abs/2406.19384
49. S. Yang et al., *Do Large Language Models Latently Perform Multi-Hop Reasoning?*, arXiv:2402.16837, 2024. https://arxiv.org/abs/2402.16837
50. OpenAI, *GPT-6 Astra System Card*, Deployment Safety Hub, September 2026. https://deploymentsafety.openai.com/gpt-6-astra
51. Fortune, *AI experts worry OpenAI's Astra model may be a dangerous step toward models with opaque reasoning*, 3 September 2026. https://fortune.com/2026/09/03/reports-openais-astra-model-uses-a-new-more-efficient-ai-architecture-alarms-ai-safety-experts-who-worry-the-method-makes-models-harder-to-control/
52. J. Pachocki, post on X, 2 September 2026. https://x.com/merettm/status/2095023204993490967
53. S. Raschka, *GPT-6 Astra, Looped Transformers, and Hidden Reasoning*, 9 September 2026. https://magazine.sebastianraschka.com/p/gpt-6-astra-looped-transformers-and
54. R. Arike, *How concerned should we be about Astra's recurrent architecture?*, LessWrong, 2 September 2026. https://www.lesswrong.com/posts/PLisnSFir8y5AHkmP/how-concerned-should-we-be-about-astra-s-recurrent
55. *The Information*, report on OpenAI's Astra and recurrent depth, 1 September 2026 (paywalled; not read directly for this guide; known through [51] and [53]).
56. European Union, *Artificial Intelligence Act*, Article 51 (classification of general-purpose AI models with systemic risk). https://artificialintelligenceact.eu/article/51/

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | October 2026 | Initial release, with companion toolkit `packages/recurrent_depth` |

---

*Independent research, not affiliated with any institution or committee. Published for AI safety research, evaluation, and education. MIT License.*
