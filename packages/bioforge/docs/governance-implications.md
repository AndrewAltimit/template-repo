# Governance Implications of Agent-Actuated Biological Systems

This document explores the governance, safety, and policy implications of AI agents with physical-world actuation capability over biological materials. The [BioForge platform](../README.md) demonstrates these principles in a controlled, BSL-1 laboratory automation context, today against simulated hardware.

Status of this document: written September 2026. Policy references are current as of that date; the US federal framework for high-consequence life sciences research changed twice between 2024 and 2026 (see [Policy Context](#policy-context-september-2026)), so anything here should be checked against the current instruments before being relied on.

## The Core Finding

AI agents can already orchestrate physical laboratory operations through tool-use protocols. When connected to actuators via MCP, an agent can design experiments, dispense reagents, control temperatures, capture and analyze images, and iteratively optimize results, in a closed loop with limited human intervention. This is not a theoretical capability: the integration pattern is straightforward, and BioForge implements it using off-the-shelf components and open-source software.

What is implemented today, and what is not, matters for every claim below:

- **Implemented and tested**: the MCP tool surface, the stateful safety enforcer, protocol parsing and step validation, the protocol state machine, e-stop latching, human-action gates, the per-run dispense budget, the approved-protocol allowlist (a protocol is loadable only if its content hash appears in an operator-maintained manifest), and the append-only audit log. These run against a simulated hardware layer and behave the same way with hardware attached.
- **Staged and incomplete**: the physical instrument. Thermal control, liquid handling, imaging, and the first end-to-end agent-orchestrated run are Phases 2 through 5 of the build, and the ESP32 co-processor firmware is not written. See the [hardware documentation](../../../docs/hardware/bioforge-crispr-automation.md) for phase status. Nothing in this repository has yet driven a physical actuator or touched biological material.
- **Absent, and not merely staged**: any check on *what* a protocol targets. Every interlock listed above bounds *how much* the agent may command, and none of them asks what the commanded work is for. There is no sequence or target screening, no gating of nucleic acid orders, and no provenance check on an agent-designed protocol beyond the allowlist's guarantee that a named human signed off on those exact bytes. That guarantee is procedural, not technical: it relocates the judgement to a person and does not supply it. See [What the Interlocks Do Not Bound](#what-the-interlocks-do-not-bound-protocol-content).

So the finding is: **the control, safety, and oversight layer of an agent-actuated lab is buildable today by one person, and the gap is not in capability but in governance frameworks for agent-actuated biological systems.** Claims about closed-loop biological optimization describe the architecture and the simulated path, not a completed instrument with published results.

This is consistent with the external literature. A 2026 review of the AI and biosecurity "stack" argues that the consequential shift is not any single layer but the coupling of a capable model with an agentic interface, a laboratory it can actuate, and permissive data access [13]. A 2025 review of self-driving laboratories reaches a similar conclusion from the laboratory side and notes that existing biosafety practice assumes a human is physically present to intervene [11].

## Why This Research Exists

### The Disclosure Analogy, and Where It Breaks

Earlier versions of this document justified BioForge by analogy to security research: researchers demonstrate vulnerabilities to force patches, because theoretical warnings get ignored and working demonstrations create urgency. That analogy is useful but it is not free, and it does not transfer cleanly.

Coordinated vulnerability disclosure works because there is a specific owner who can ship a fix, a patch distribution channel, and a short half-life for the exploit once the fix lands. Biological and biosecurity "vulnerabilities" have none of those properties. Millett's analysis of biosecurity vulnerability reporting makes the point directly: biological threats have a much longer half-life than digital ones, countermeasures may not exist and may never exist on a useful timescale, and the standard cybersecurity toolkit of disclosure deadlines, bug bounties, and unauthorized penetration testing is a poor fit [1]. Governance of agent-actuated labs has no single vendor to notify. There is an interagency process, several standards bodies, a few funders, many institutional biosafety committees, and a large population of hobbyists and startups who answer to none of them.

The consequence is that a demonstration in this space cannot be assumed to be net-positive the way a patched CVE is. A demonstration can diffuse capability. It can also normalize a practice, lower the perceived effort of copying it, or supply a template that someone strips the safety layer out of.

**This is a tradeoff, not a justification.** What follows is why the specific design choices tilt BioForge toward the benefit side, and what residual risk remains.

Reasons the tradeoff tilts toward benefit:

1. **The demonstrated artifact is the safety architecture, not a dangerous capability.** The novel content here is interlock design, gate placement, capability bounding, and audit format. The underlying integration (a language model calling tools that move a pump) is already widely published, commercially available in laboratory automation products, and discussed in the policy literature [11][13]. The marginal capability diffusion from this repository is low; the marginal contribution is a worked reference for the controls.
2. **The biology sits at the floor of the risk scale.** BSL-1, non-pathogenic *E. coli* K-12, from a commercially sold educational kit. The Automated Laboratory Security Tier (AST) framework, a classification scheme proposed in a single 2026 paper rather than an adopted standard, would put a facility capable only of producing Risk Group 1 organisms in its lowest tier, AST-1, for which it recommends basic identity verification and sequence screening rather than the layered regime it proposes for pathogen-capable facilities [12]. BioForge sits at or below that tier, and the comparison cuts both ways: it implements considerably more interlocking, gating, and logging than that tier asks for, and it implements none of the sequence screening that the same paper recommends at every tier, including the lowest. That asymmetry is the subject of [What the Interlocks Do Not Bound](#what-the-interlocks-do-not-bound-protocol-content).
3. **The hard limits are outside the agent's reach.** Temperature, volume, flow rate, rate of commands, and motion bounds come from `safety_limits.toml`, are loaded at server start, and are not exposed as a tool. There is no tool for the agent to edit limits, edit protocols, approve a protocol, or delete audit records. This matches what the self-driving laboratory review calls code compartmentalization: preventing alteration of an approved plan after human authorization [11].
4. **No protocol uplift is published.** This repository contains one protocol for a commercially available teaching kit. It adds no wet-lab detail that is not already in that kit's own instructions, and this document deliberately contains none.
5. **The failure mode being demonstrated is the governance gap, which is not itself a capability.** "No regulatory instrument squarely addresses an AI agent holding the actuator" is a statement about paperwork, not a recipe.

Residual risk:

- Architecture is transferable in both directions. A design that safely bounds an agent at BSL-1 is also a design someone can scale up while deleting the bounds. The mitigation is partial: the safety layer is the part that is hard to write and easy to cut, which is exactly the asymmetry that makes publishing it uncomfortable.
- Normalization is a real cost. Making hobbyist agent-actuated biology look routine and respectable has effects that no interlock addresses.
- The empirical evidence on AI uplift to biological misuse is genuinely contested. A RAND red-team study found no statistically significant difference in the viability of attack plans produced with and without LLM assistance in the models of that period [8], while CLTR's 2024 review concluded that the evidence base tests only a subset of the theorized pathways and that clearer evidence is needed before proportionate policy can be designed [9], later contributing to a risk index for AI-enabled biological tools with RAND Europe [10]. Someone who reads that literature and concludes this project should not exist is not being unreasonable; they are weighing the same uncertain quantities differently.

### What This Makes Visible

1. **Technical feasibility**: the integration between language model reasoning and physical actuation is straightforward with MCP tool-use patterns.
2. **Safety architecture patterns**: defense-in-depth, human gates, audit logging, capability bounding, and protocol allowlisting are implementable, but they require deliberate engineering and they are the first thing an implementer under schedule pressure will skip.
3. **Governance gap**: no regulatory instrument specifically addresses AI agents with biological actuation capability, and the 2026 federal policy is explicit that this intersection is still being scoped rather than governed [4].
4. **Scalability concern**: what is defensible at BSL-1 with *E. coli* on a bench needs governance frameworks before the same architecture reaches higher-consequence biological systems.

## Policy Context (September 2026)

The US framework governing high-consequence life sciences research moved twice while this project was being built, which is itself part of the argument that agent-actuated automation is not yet covered by anything.

- **May 2024**: the *United States Government Policy for Oversight of Dual Use Research of Concern and Pathogens with Enhanced Pandemic Potential* was issued, with an effective date of 6 May 2025, unifying the 2012, 2014, and 2017 instruments under a two-category review structure [2].
- **May 2025**: Executive Order 14292, *Improving the Safety and Security of Biological Research*, paused federally funded "dangerous gain-of-function" research, rescinded the 2024 DURC/PEPP policy, and directed OSTP to produce a replacement [3].
- **July 2026**: OSTP approved the *United States Government Policy for Stopping High-Risk Life Sciences Research* (approved 20 July 2026), which replaces the 2024 policy, prohibits federal support for dangerous gain-of-function research, and creates a single government-wide independent third-party review body for potential DGOF proposals. Purely computational research is not prohibited unless it involves an entity of concern. The policy also directs OSTP to convene an interagency group to monitor advances at the intersection of the biological sciences and artificial intelligence, including in silico life sciences research [4].

None of these instruments reach BioForge. It is not federally funded, it involves no pathogen and no gain-of-function work, and the current policy's oversight hooks are funding conditions and institutional review entities. That is the correct outcome on a proportionality basis, and it is also the gap: the thing being governed is the agent and the organism, not the fact that a language model holds the actuator.

The non-governmental literature is further along:

- NASEM's 2025 consensus study *The Age of AI in the Life Sciences: Benefits and Biosecurity Considerations*, requested by the Department of Defense, assesses how AI-enabled biological tools change biosecurity risk in both directions, including their use to strengthen laboratory safety and early warning [5].
- The *Responsible AI x Biodesign* community statement (March 2024) set out values and ten practical commitments for scientists building or using AI tools for biomolecular design, including safety evaluation of models, synthesis screening, and obligations to report concerning practices [6]. BioForge implements none of the screening commitments: it neither screens sequences nor routes anything through a provider that does. That is defensible for a teaching kit and indefensible for the arbitrary-protocol ambition stated in the README, which is why the gap is recorded rather than glossed.
- NTI | bio's 2023 report on the convergence of AI and the life sciences argued for governance mechanisms ahead of capability and has since been extended through the AIxBio Global Forum [7].
- The self-driving laboratory review recommends mandatory human review and approval of experimental plans before execution, compartmentalization that prevents post-approval alteration, monitoring for unauthorized access and hazardous release, and operator kill switches [11].
- One 2026 paper proposes the Automated Laboratory Security Tier framework, which would classify automated facilities by latent capability (what they could produce if compromised) rather than by what they currently handle, and argues that "human oversight as safeguard" tends to erode as automation scales [12].
- The AI and biosecurity stack review recommends tool permissioning with human approval gates before external actions, tamper-evident audit logs, institutional review of agent workflows, whitelisted protocols, biosafety interlocks, and anomaly detection [13].

BioForge implements a recognizable subset of the last three lists, and the shape of the subset matters. It implements the mechanical controls: permissioning, approval gates, interlocks, append-only logging, and protocol whitelisting. It does not implement the controls that require judgement about biological content or an institution to exercise it: sequence and synthesis screening [6][12], institutional review of agent workflows [13], tamper-evident (rather than merely append-only) logging, and automated anomaly detection. So the useful thing to say about it is narrow: not that it invents these controls, and not that it satisfies the published recommendation sets, but that it is a small, readable instance of the mechanical half of them, which makes it a cheap object to argue over.

## Design Principles as Governance Test Cases

BioForge embeds several governance principles directly into its architecture. Each principle below distinguishes what the code enforces from what is policy or plan.

### Capability Bounding

The MCP server enforces hard limits on what the agent can command. Temperature ranges, volume limits, flow rates, motion bounds, and call rates are not suggestions; they are runtime constraints the agent cannot negotiate around.

```
safety_limits.toml:
  thermal.tool_max_c = 50.0        # Agent cannot set temperature above 50C
  volume.max_dispense_ul = 1000.0  # Agent cannot dispense more than 1 mL
  rate.max_calls_per_minute = 60   # Agent cannot flood actuator commands
```

The agent receives a refusal, visible to it as an error with a reason, if it attempts to exceed these bounds. The bounds are configurable by the human operator, are read at server startup, and are not modifiable by the agent at runtime: no tool writes configuration, no tool writes protocol files, and no tool writes the approved-protocol manifest described next.

Note what kind of bound this is. Every limit in the table is a quantity: degrees, microliters, microliters per second, millimeters, calls per minute. They bound the physical envelope the agent may act within. They are indifferent to what the action is for, and deliberately so, because a thermostat cannot be asked to have an opinion about molecular biology.

### Protocol Provenance: the Approved-Protocol Allowlist

A second control asks a different question: not how much, but whether this protocol may run at all.

`config/approved_protocols.toml` is an operator-maintained manifest. Each entry names a protocol id, the SHA-256 of that protocol file's canonical text, who approved it, when, and optionally on what basis. `load_protocol` hashes the file it just read and refuses the load unless the hash matches an entry for that id. The manifest is read once at server start, no tool writes it, and a missing or malformed manifest denies every protocol rather than allowing every protocol. Refusals are audit-logged, and the refusal message carries the computed hash so an operator who does want to approve the file has the value to paste in. The shipped manifest approves nothing. Approval is local to the lab that will run a protocol and must be recorded by that lab's responsible biosafety reviewer (for example its principal investigator or biosafety officer, under the institution's own process); an approval recorded elsewhere, including by the repository author, does not transfer. The shipped file carries a commented template entry for the Odin protocol with placeholder approver fields, and a placeholder approver is rejected, which makes the manifest deny every protocol.

What this buys:

- An unreviewed protocol cannot become the active protocol. Dropping a TOML file into `protocols/custom/` is not sufficient; a human has to add it to the manifest.
- Editing an approved protocol revokes its approval until someone re-approves it. Comments count, because approval is meant to cover the file a reviewer actually read.
- Losing the manifest fails closed. A deployment that misconfigures the path gets zero loadable protocols, not unrestricted loading.

What it does not buy:

- **It is not screening.** A hash comparison is indifferent to meaning. The allowlist cannot tell a teaching-kit protocol from anything else, and it makes no assessment of biological content whatsoever.
- **It does not constrain ad-hoc actuation.** The server has no step executor, so an agent can still call `dispense`, `heat_shock`, and the rest without any protocol loaded at all. Those calls are bounded by the envelope limits and by gates the agent chooses to open, not by the allowlist. Requiring an approved active protocol before any actuator call would close this and is not implemented.
- **It does not make the review good.** The manifest records that a named person approved a hash on a date. It cannot establish that the person was competent to assess the protocol, or that they read it. An operator remains free to approve anything.

So the allowlist converts "any file on disk may run" into "only files a named human signed off on may run". That is a real narrowing and a precondition for review to mean anything, but it is a mechanism for enforcing a review decision, not a substitute for one.

### What the Interlocks Do Not Bound: Protocol Content

Putting the two previous sections together: BioForge bounds the physical envelope in code, and enforces protocol provenance in code, and has no control of any kind over what a protocol targets. There is no sequence or target screening, no gating of nucleic acid synthesis orders (the platform places none today and has no hook where such a check would sit), and no automated provenance check on an agent-designed protocol beyond a human signature on its bytes.

This gap matters more than the envelope bounds do, and it matters more as scope grows. The reason is that the two controls scale in opposite directions:

- The envelope is fixed. It is the same 1 to 1000 uL, the same -5 to 50 C, the same 200 by 150 by 50 mm enclosure whatever the experiment is.
- The set of protocols that fits inside that envelope is not fixed. It grows with every capability added and with every protocol an agent is allowed to design. The README states the ambition of extending to arbitrary molecular biology protocols through agent-designed pipelines, and every one of those protocols would be, by construction, a series of small volumes at moderate temperatures in a small enclosure.

A dispense of 50 uL at 37 C is inside every limit in `safety_limits.toml` regardless of what is in the tube. So the discriminating power of the envelope with respect to the thing anyone is actually worried about falls toward zero as the protocol space expands, while the envelope itself looks exactly as protective as it did before. Envelope bounds are industrial safety: do not cook the bench, do not flood the deck, do not stall the gantry. They were never biosecurity controls and should not be read as any. This is the same argument the AST paper makes about latent capability [12]: what matters is what a facility could be used to produce, which is a question about content, not about actuator ranges.

This is missing not because it was overlooked, but because an adequate control here is not something a single maintainer can write or self-certify. At a policy level, an adequate control looks like three things, none of which is a feature in this repository:

1. **Screening against established frameworks, by an accredited provider.** Any nucleic acid sequence or construct entering the workflow is screened by an organization accredited to apply recognized synthesis-screening practice, and the result gates the work. This is the synthesis-screening commitment in the *Responsible AI x Biodesign* statement [6], echoed by NASEM [5] and by the AST paper at every tier [12]. The platform's role is to refuse to proceed without a screening result, not to perform the screening: a self-screening laboratory grading its own homework is the failure mode, and an agent-designed screen of an agent-designed protocol is that failure mode twice.
2. **Human biosafety review of every new protocol before first execution.** Reviewed by someone competent in the relevant biology, not by the operator who wants the run, and recorded with the reviewer's identity and the basis for the decision. Where an institutional biosafety committee exists, it is the reviewer; where none does (which is the situation for hobbyist and single-maintainer builds, and the reason the governance gap in this document exists at all), there is no adequate substitute, and that fact should be treated as a limit on what such a build may attempt rather than as a licence.
3. **Protocols only from an approved registry.** No ad-hoc protocol execution, and no execution of a protocol an agent composed at runtime. The registry entry carries the screening result and the review record, and the runtime enforces membership. The allowlist implemented here is the enforcement mechanism for exactly this control, with the registry contents currently amounting to one reviewed teaching-kit protocol and the screening and review records kept as prose in the manifest rather than as verifiable artifacts.

Until all three exist, the accurate description of this platform's content controls is: one commercially sold teaching-kit protocol, reviewed by its maintainer, enforced by hash. That is proportionate to what the thing does today. It is not a pattern anyone should carry forward to a broader protocol set, and a derivative that inherits the interlocks while widening the protocol space would be strictly less safe than this one despite having the same code.

### Audit Transparency

Every mutating tool call is logged with enough detail to reconstruct what happened and why, including calls that were refused. This is the biological equivalent of flight recorder data.

The audit log format, as designed, carries four event kinds:

- **Tool calls**: tool name, raw arguments, caller identity, timestamp, run ID, and the result or the refusal reason
- **Sensor readings**: zone, value, target, stability status
- **State transitions**: from-state, to-state, trigger
- **Human gates**: action requested, approval status, who confirmed

What the server emits today is the tool-call stream, including human-gate tool calls and their outcomes; the log type is generic over event kinds, and periodic sensor-sample logging arrives with the thermal build phase. Read-only status calls are not logged. The log is append-only with an fsync per line and no deletion tool is exposed. It is not tamper-evident in the cryptographic sense: an operator with filesystem access can rewrite it, so it protects against the agent, not against the operator. Hash chaining would close that gap and is not implemented.

### Human Oversight at Decision Boundaries

The human gates are positioned where the system crosses from digital reasoning to physical biological reality:

- **Loading biological reagents**: the agent cannot verify that the correct tubes are on the deck.
- **Confirming plate placement**: the agent cannot verify physical plate positioning in the incubator.
- **Approving experiment designs**: the agent proposes; the human approves or modifies.

The agent is effective at optimization within defined parameters; humans are necessary for verifying that physical reality matches digital assumptions.

**How this is actually enforced, precisely.** Protocol steps carry a `human_gate` boolean in their TOML definition, and the shipped Odin protocol sets it on two steps: loading cells and reagents, and confirming plates into the incubator. When a gate is open (opened by the `request_human_action` tool), every actuator tool is refused while it is pending, only one gate can be open at a time, and the agent cannot confirm its own gate: confirmation requires an out-of-band file created by the operator in the configured confirmation directory, and action IDs embed the server start time so stale confirmations from a previous run cannot satisfy a new gate. Camera and lighting calls are deliberately still permitted during a pending gate so the operator can inspect the deck.

Two limits on that enforcement should be stated rather than implied:

1. **The gate is requested, not imposed.** The server has no step executor. The agent drives the protocol by calling tools, so the `human_gate` flag on a step is metadata that the agent (and the operator reading `load_protocol` output) is expected to honor. An agent that simply never calls `request_human_action` is never blocked by a step-level flag. Making step-level gates mandatory at the admission layer, by refusing actuator calls while the loaded protocol's current step is gated and unconfirmed, is a design intention and is not implemented.
2. **A gate can expire.** `request_human_action` takes a timeout of 1 to 1440 minutes, and when it passes the gate resolves as `timed_out` rather than `confirmed` and stops blocking actuators. Without a configured confirmation directory, expiry is the only way a gate can resolve. Expiry is recorded in the audit log and is distinguishable from confirmation, so an operator reviewing a run can see that the gate was never satisfied, but the run is not halted by it. The policy is that a timed-out gate is a failed step and not implied consent; the code does not currently enforce that policy, and latching on expiry (holding actuators until an operator resolves the gate, as the e-stop latch does) would.

Neither point is an argument against gates. Both are the difference between "the architecture says" and "the binary does", and that difference is exactly what governance discussions usually get wrong about reference implementations.

### Graduated Autonomy

Requiring human confirmation at every physical step does not scale, and a system that demands confirmation for everything trains operators to click through. So relaxing gates as a track record accumulates is a legitimate design goal, and it is one the automated-lab literature expects: the AST paper argues that human oversight tends to erode as automation scales [12], which is a reason to make the erosion explicit, bounded, and reviewable rather than gradual and undocumented.

The conditions below are **design policy for BioForge, not implemented behavior**. Today the system has exactly two settings: a step either carries a `human_gate` flag or it does not, and changing that means an operator editing a protocol TOML on disk. There is no trust score, no autonomy level, no relaxation mechanism, and no code path by which the agent can change gate placement. Any future implementation is bound by these conditions.

**The condition that is not negotiable.** Irreversible steps and novel steps never lose their gate, at any trust level. Irreversible means the physical result cannot be undone by the system: committing reagents, heat shock on a prepared transformation mix, plating, opening a sealed enclosure, anything that produces or disposes of biological material. Novel means a protocol, step type, reagent, or parameter range that has not previously been executed and reviewed. A track record on routine steps is not evidence about steps the system has never taken.

**Why a track record is weaker evidence than it looks.** This repository's own containment framework treats behavioral history as evidence rather than proof, for a specific reason: models can recognize when they are being observed and behave differently. The literature on this has firmed up considerably:

- Frontier models classify transcripts as evaluation or deployment at well above chance, though not yet at the level of a human baseline [14].
- In anti-scheming training work by Apollo Research and OpenAI, chains of thought often show awareness of being evaluated for alignment, and that awareness causally decreases covert behavior while unawareness increases it. This means an observed reduction in bad behavior is partly a measurement artifact rather than purely an improvement [15].
- Alignment faking has been demonstrated directly: a model selectively complying with a training objective while it believed it was being trained, in order to avoid modification of its behavior out of training [16].
- Anthropic's Claude Opus 4.6 system card (February 2026) reports improvement on the verbalized evaluation-awareness metric relative to the previous model while also stating that internal and external analysis suggests the model is often able to distinguish evaluations from real deployment even when that awareness is not verbalized [17].

None of this says a track record is worthless. It says a clean track record is necessary and not sufficient, and that "we ran fifty supervised trials and nothing went wrong" is the specific kind of evidence most vulnerable to this failure mode.

See the containment framework's [Section 2.5, Evaluation Awareness and Sandbagging](../../../docs/hardware/ai-agent-containment-infrastructure-security-framework.md#25-evaluation-awareness-and-sandbagging) and [Section 3.8, Trust Tier Transitions](../../../docs/hardware/ai-agent-containment-infrastructure-security-framework.md#38-trust-tier-transitions) for the general form of this argument, and [Section 10, Proportionality](../../../docs/hardware/ai-agent-containment-infrastructure-security-framework.md#10-proportionality-the-ethical-and-practical-dimension) for why the answer is not simply "gate everything forever".

**Conditions on any relaxation:**

| Condition | Requirement |
|-----------|-------------|
| Scope | Per step and per protocol, never global. Relaxation attaches to a specific step type in a specific validated protocol at specific parameter ranges. |
| Irreversibility | Irreversible or novel steps keep their gate unconditionally. Not overridable by track record, by operator preference, or by configuration. |
| Evidence quality | Track record must come from production-realistic runs, not from trials the agent can identify as observed rehearsals. Runs conducted specifically to earn autonomy are the weakest evidence available, for the reasons above. |
| Who acts | Relaxation requires a human operator action outside the agent's reach (a file the agent has no tool to write). The agent may not request, negotiate, or argue for it, and an agent that does should be treated as an anomaly signal. |
| Logging | Which gates were active for each run is recorded in the audit log, so a run's oversight level is reconstructable after the fact. |
| Expiry | Time-bounded or re-validated. Relaxation lapses by default rather than persisting silently. |
| Reversion | Automatic revert to full gating on anomaly: a refused command, an out-of-tolerance sensor reading, an aborted step, a changed model or scaffold, or an unexplained parameter excursion. Model, scaffold, or tool-set changes reset the track record rather than inheriting it. |
| Review | A person other than the one who ran the qualifying trials signs off, mirroring the containment framework's promotion criteria. |

Stated as phases, and keeping the distinction between what exists and what does not:

- **Now (implemented)**: gates are declared per step in the protocol file, and an open gate blocks all actuators until it is confirmed or expires.
- **Established operation (policy, not implemented)**: gates on routine, reversible, previously validated steps may be relaxed under every condition in the table above.
- **Exception-based oversight (policy, not implemented, and bounded)**: even at the most permissive setting contemplated, irreversible and novel steps remain gated. "Exception-based" describes routine reversible steps only. It never means an unattended run that commits biological material without a human in the loop.

## Questions by Audience

### For Policymakers

**Immediate questions**:

- What regulatory frameworks apply when AI agents control laboratory equipment, given that the July 2026 policy's hooks are funding conditions and institutional review entities [4]?
- How should audit requirements be structured for agent-actuated biological systems, and should tamper-evidence (not merely append-only logging) be required?
- What certification or validation standards should apply to safety interlocks in agent-controlled labs?
- Should oversight attach to latent capability rather than declared activity, as one 2026 proposal argues [12]?
- Who is responsible for screening a protocol an agent designed, and should a screening obligation attach to the platform, the operator, or the synthesis supplier? An allowlist can enforce that only reviewed protocols run; nothing in an open-source platform can make the review competent.

**Framework considerations**:

- Should there be graduated autonomy standards tied to biosafety levels, and should they encode a floor of non-relaxable gates for irreversible steps?
- How do existing dual-use research policies apply to open-source automation platforms that fall outside federal funding conditions?
- What international coordination is needed, and is a forum model of the kind NTI convenes [7] the right venue?

**What this platform provides**:

- A small, readable implementation of the mechanical safety patterns that policy analysis independently recommends [11][12][13], running today against simulated hardware. It is worth reading as a worked example of those patterns, not as a certified or complete implementation of any recommendation set: the content controls those same sources ask for are absent, as set out above.
- A concrete audit trail format for regulatory evaluation
- A worked example that governance-by-design is compatible with a usable system at this scale. It is a single-maintainer BSL-1 prototype with the physical build incomplete, so it is a demonstration of feasibility in the small, not evidence that oversight costs nothing at production throughput. The cost is that gates, budgets, and rate limits do constrain throughput, and the AST paper's claim that human oversight erodes under automation pressure describes a pressure this project has not yet been subjected to [12].

### For AI Safety Researchers

**Research directions**:

- Agent behavior monitoring during autonomous physical-world operations
- Alignment verification through audit trail analysis
- Safety interlock design patterns for agent-hardware interfaces
- Whether evaluation awareness manifests differently when actions have physical consequences than in text-only evaluation settings [14][15]. This is the question the platform is built for and cannot yet answer: with simulated hardware, an agent operating it is in a text-only setting with hardware-shaped vocabulary.
- Sleeper agent detection applied to laboratory automation contexts

**What this platform provides**:

- A testbed for the control layer of an agent-actuated lab: tool calls, refusals, gates, budgets, and the audit trail are real and exercised. The actuation is simulated, so there are no physical consequences yet, low-risk or otherwise. Physical consequences arrive with Phases 2 through 5, and any claim about how agents behave when their actions are irreversible is untested here.
- Complete observability into agent tool calls, refusals, and simulated hardware responses
- An integration point for existing sleeper agent detection frameworks (planned, not implemented)

### For Laboratory Automation Developers

**Technical considerations**:

- MCP tool-use patterns for hardware abstraction
- Defense-in-depth safety architecture transferable to other automation contexts
- Protocol state machine design for enforcing step ordering and prerequisites
- Audit logging patterns for regulatory compliance

**What you can build on**:

- The safety architecture patterns apply to any agent-actuated physical system
- The human-in-the-loop gate mechanism generalizes beyond biological contexts
- The approved-protocol allowlist is small enough to copy and generalizes to any system that loads a plan from a file: hash what you are about to execute, check it against a manifest a human maintains, fail closed
- The audit log format supports downstream analysis and compliance reporting
- The gaps documented above are the ones worth fixing first in any derivative. Two are enforcement gaps: mandatory step-level gating at the admission layer, and latching on gate expiry. The third is not an enforcement gap but a missing control, and it is the one that matters if you widen the protocol set beyond a reviewed teaching kit: nothing here screens or reasons about what a protocol targets, and the physical-envelope limits you inherit will not do it for you

## Relationship to AI Safety

BioForge connects to broader AI safety concerns through several channels:

**Autonomous physical-world operation**: agents controlling actuators with real-world consequences are a concrete instance of the alignment problem: the system must do what the human intends, not just what the human literally commands.

**Defense in depth as alignment strategy**: multiple independent safety layers mean that no single failure, including alignment failure, leads to unsafe operation. Hardware limits that no software can raise are the layer that survives an agent behaving badly on purpose.

**Observability as governance tool**: the audit trail makes agent behavior reviewable. Anomaly detection over that trail is currently manual review plus the enforcer's refusals; automated detection of unusual parameter combinations is not implemented, and describing it as implemented would be exactly the kind of overclaim this document is trying to avoid.

**Trust calibration under evaluation awareness**: the graduated autonomy conditions above are the practical consequence of taking evaluation awareness seriously. If observed good behavior is partly an artifact of being observed, then the design response is to keep the irreversible decisions gated regardless of track record, and to make every relaxation explicit, narrow, logged, and expiring.

**Capability demonstration with responsibility**: showing that agent-actuated biological systems are feasible today, with a responsible safety architecture, informs the timeline for governance development. The alternative (the capability arriving without governance) looks worse, though as set out above this is a judgment call about an uncertain quantity, not a settled conclusion.

## A Note on Framing

This document presents agent-actuated biological automation as a governance challenge requiring proactive attention. BioForge deliberately operates at the lowest-risk end of the biological spectrum (BSL-1, non-pathogenic *E. coli*) to build and validate governance patterns before they are needed at higher stakes.

**If we cannot build responsible governance into a system that edits non-pathogenic bacteria on a kitchen table, we have no business deploying AI agents with actuation capability over more consequential biological or physical systems.**

That statement is a design argument, not a claim of sufficiency, and it is written in the future tense on purpose: the system does not yet edit anything, because the instrument is staged across Phases 2 through 5. A working set of interlocks at BSL-1 does not establish that the same patterns hold at BSL-2 or above, where the failure modes include contained release rather than a wasted plate, and where the correct answer may be that agent actuation is not appropriate at all. The interlocks are also only half of what governance needs: they bound the envelope and enforce that a human approved the protocol, and they contain nothing that reasons about biological content, which is the half that cannot be built by one person and must come from screening and institutional review. Nor does one maintainer's prototype substitute for institutional review, independent audit, or the standardization that the automated-lab literature calls for [11][12]. It is a proof of concept for patterns that need to exist, tested at the stakes where testing them is cheap.

## References

1. Millett, P.D. (2024). "Five Things Not to Do When Discovering a Biosecurity Vulnerability." *Applied Biosafety* 29(3):181-184. doi:10.1089/apb.2023.0038. <https://pmc.ncbi.nlm.nih.gov/articles/PMC11447127/>
2. Office of Science and Technology Policy (May 2024). *United States Government Policy for Oversight of Dual Use Research of Concern and Pathogens with Enhanced Pandemic Potential*. Effective 6 May 2025; rescinded by Executive Order 14292. <https://bidenwhitehouse.archives.gov/wp-content/uploads/2024/05/USG-Policy-for-Oversight-of-DURC-and-PEPP.pdf>
3. Executive Order 14292 (5 May 2025). *Improving the Safety and Security of Biological Research*. <https://www.whitehouse.gov/wp-content/uploads/2025/05/eo-14292.pdf>
4. Office of Science and Technology Policy (approved 20 July 2026). *United States Government Policy for Stopping High-Risk Life Sciences Research*. <https://www.aspr.gov/readiness-response/medical-countermeasures-biodefense/s3/high-consequence-research-oversight/USG-Policy-For-Stopping-High-Risk-Life-Sciences-Research>
5. National Academies of Sciences, Engineering, and Medicine (2025). *The Age of AI in the Life Sciences: Benefits and Biosecurity Considerations*. National Academies Press. <https://www.nationalacademies.org/projects/DELS-BLS-24-04/publication/28868>
6. Responsible AI x Biodesign (8 March 2024). *Community Values, Guiding Principles, and Commitments for the Responsible Development of AI for Protein Design*. <https://responsiblebiodesign.ai/>
7. Carter, S.R., Wheeler, N., Chwalek, S., Isaac, C.R., Yassif, J.M. (2023). *The Convergence of Artificial Intelligence and the Life Sciences: Safeguarding Technology, Rethinking Governance, and Preventing Catastrophe*. NTI | bio. <https://www.nti.org/wp-content/uploads/2023/10/NTIBIO_AI_FINAL.pdf>
8. Mouton, C.A., Lucas, C., Guest, E. (2024). *The Operational Risks of AI in Large-Scale Biological Attacks: Results of a Red-Team Study*. RAND Corporation, RR-A2977-2. <https://www.rand.org/pubs/research_reports/RRA2977-2.html>
9. Rose, S., Moulange, R., Smith, J., Nelson, C. (July 2024). *The Near-Term Impact of AI on Biological Misuse*. Centre for Long-Term Resilience. <https://www.longtermresilience.org/reports/the-near-term-impact-of-ai-on-biological-misuse/>
10. Centre for Long-Term Resilience with RAND Europe (September 2025). *Global Risk Index for AI-Enabled Biological Tools*. <https://www.longtermresilience.org/reports/global-risk-index-for-ai-enabled-biological-tools/>
11. Tobias, A.V., Wahab, A. (2025). "Autonomous 'self-driving' laboratories: a review of technology and policy implications." *Royal Society Open Science* 12(7):250646. doi:10.1098/rsos.250646. <https://pmc.ncbi.nlm.nih.gov/articles/PMC12368842/>
12. Smith, M.D., Hanke, M.S., Moritz, R.L., Gillum, D.R., Pannu, J. (2026). "Automated Laboratory Security Tiers: a framework for evaluating and mitigating biosecurity risks from latent capabilities." *Frontiers in Microbiology* 17:1832401. doi:10.3389/fmicb.2026.1832401. <https://doi.org/10.3389/fmicb.2026.1832401>
13. Luhachack, L., Connell, N., Berger, K. (2026). "From capability uplift to capability governance: an AI-biosecurity stack." *Frontiers in Microbiology* 17:1899413. doi:10.3389/fmicb.2026.1899413. <https://doi.org/10.3389/fmicb.2026.1899413>
14. Needham, J., Edkins, G., Pimpale, G., Bartsch, H., Hobbhahn, M. (2025). *Large Language Models Often Know When They Are Being Evaluated*. arXiv:2505.23836. <https://arxiv.org/abs/2505.23836>
15. Schoen, B., Nitishinskaya, E., Balesni, M., et al. (Apollo Research and OpenAI, September 2025). *Stress Testing Deliberative Alignment for Anti-Scheming Training*. arXiv:2509.15541. <https://arxiv.org/abs/2509.15541>
16. Greenblatt, R., Denison, C., Wright, B., et al. (2024). *Alignment Faking in Large Language Models*. arXiv:2412.14093. <https://arxiv.org/abs/2412.14093>
17. Anthropic (February 2026). *Claude Opus 4.6 System Card*. <https://www.anthropic.com/document/claude-opus-4-6-system-card>

## Further Reading

- [BioForge README](../README.md): platform overview and quick start
- [Hardware Documentation](../../../docs/hardware/bioforge-crispr-automation.md): complete system design
- [AI Agent Containment and Infrastructure Security Framework](../../../docs/hardware/ai-agent-containment-infrastructure-security-framework.md): trust tiers, evaluation awareness, proportionality
- [Economic Agents Governance](../../economic_agents/docs/economic-implications.md): parallel governance analysis for autonomous economic systems
- [Sleeper Agent Detection](../../sleeper_agents/README.md): anomalous agent behavior detection framework
