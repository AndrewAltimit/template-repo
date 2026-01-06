# AI Agents and Weapons of Mass Destruction: A Proliferation Risk Assessment

## A Projection Report on Emerging Risks to Global Security

**Type**: Policy Research - Defensive Analysis
**License**: MIT / Unlicense (Public Domain)
**Version**: 1.0
**Date**: December 2025

---

## About This Document

This is a **public policy research document** analyzing how AI capabilities may affect WMD proliferation risks. It is released under permissive open-source licenses to support broad discussion of these issues.

**Intended audiences**:
- Policy researchers and analysts
- AI safety and security researchers
- Academic communities studying technology governance
- Journalists and commentators covering AI risks
- General public interested in emerging technology policy

**How to use this document**:
- The analysis is framed for *defensive* purposes - understanding risks to inform protective measures
- Technical details that could enable harm are intentionally omitted
- Probability estimates are subjective priors, not predictions - treat them as discussion aids
- When excerpting, please preserve context to avoid misrepresentation

---

## Epistemic Status Markers

Throughout this document, key claims are tagged with epistemic status:

| Marker | Meaning | Evidence Standard |
|--------|---------|-------------------|
| **[O]** | Open-source documented | Published research, official statements, public data |
| **[E]** | Expert judgment / plausible inference | Consistent with theory and limited evidence; gaps acknowledged |
| **[S]** | Speculative projection | Extrapolation from trends; significant uncertainty |

*Claims without markers are framing or synthesis statements.*

---

## Executive Summary

This projection examines how autonomous AI agents may alter the proliferation landscape for weapons of mass destruction (WMD), including biological, chemical, and nuclear weapons. We analyze current technological capabilities as of late 2025, project likely scenarios through 2030, and examine the complex interplay between AI capabilities, existing physical barriers, and potential defensive adaptations.

**Key Findings:**

| # | Finding | Confidence | Horizon |
|---|---------|------------|---------|
| 1 | Agentic AI workflows are unlikely to enable a novice (T0) to construct a functional WMD from scratch in the near term (2025-2030), but they will meaningfully lower barriers for T1-T3 actors by aggregating dispersed knowledge and optimizing logistics **[E]** | **High** | Ongoing |
| 2 | Biological weapons represent the highest-risk category due to the increasing accessibility of synthetic biology tools, cloud laboratory services, and the difficulty of detecting biological materials **[E]** | **High** | Immediate |
| 3 | The "tacit knowledge gap" remains a significant barrier, but AI-guided robotic systems, vision-language models, and cloud labs are beginning to erode it **[E]** | **Medium** | 2026-2028 |
| 4 | Nuclear weapons face the strongest physical barriers (fissile material scarcity); AI primarily assists state-level (T4) programs, not non-state actors **[O]** | **High** | Stable |
| 5 | Cyber-physical attacks on existing WMD-adjacent infrastructure (BSL-4 labs, chemical plants) may represent higher near-term risk than de novo synthesis **[E]** | **Medium** | Immediate |
| 6 | The "high-frequency attempts, limited success" scenario is more likely than catastrophic mass-casualty events; defenders should prepare for resource strain from numerous low-sophistication incidents **[E]** | **Medium** | 2025-2027 |

*Confidence levels follow IC standards: **High** = multiple independent sources, consistent with established patterns; **Medium** = plausible based on available evidence but gaps exist; **Low** = possible but significant uncertainty.*

**Why Now? What Changed 2023→2025:**

| Capability Shift | 2023 State | 2025 State | Impact |
|-----------------|------------|------------|--------|
| **Agentic autonomy** | Chatbots provided information | Agents execute multi-step tasks with tool use, self-correction, and persistence **[O]** | Shifts from "knowledge" to "autonomous execution" |
| **Vision-language models** | Text-only instruction | Real-time visual interpretation of lab procedures **[O]** | Begins bridging tacit knowledge gap |
| **Computer Use capabilities** | Manual web interaction | Agents can browse, fill forms, manage procurement **[O]** | Enables procurement obfuscation at scale |
| **Biological design tools** | AlphaFold 2 (structure prediction) | AlphaFold 3, ESM3 (generative biology, ligand interactions) **[O]** | Optimization beyond mere information retrieval |
| **Open-weight proliferation** | Limited high-capability open models | Llama 3, Mistral, Qwen with fine-tuning ecosystems **[O]** | Guardrail bypass via local deployment |

**Scope Limitations**: This document analyzes capabilities and trends for defensive policy purposes. It does not provide operational guidance and explicitly omits technical implementation details that could enable harm. All information draws on publicly available academic literature and policy discussions.

> **Note on Information Hazards**
>
> This document discusses sensitive topics at a level of abstraction appropriate for public policy discussion.
>
> **Intentionally excluded**: Specific synthesis routes, pathogen sequences, precursor sources, equipment specifications, and operational procedures. Where threat concepts are discussed, they are framed for *defender awareness*, not attacker enablement.
>
> **Request to readers**: When sharing excerpts, please preserve surrounding context. Isolated quotes about "what AI enables" without the corresponding barriers and limitations may create misleading impressions.
>
> **On the barriers**: The physical, logistical, and tacit knowledge barriers described in this document remain substantial. This analysis does not provide a roadmap - it provides a framework for thinking about defensive investment.

---

## What This Document Is NOT Claiming

To prevent misreading, we explicitly clarify:

- **NOT claiming an imminent WMD wave.** Actual WMD attacks by non-state actors remain extremely rare. Our assessment is that *attempt frequency* may increase while *success rate* remains low.
- **NOT claiming novices can build WMD.** AI does not transform a T0 (curious novice) into a capable threat actor. The primary effect is upgrading T1–T3 actors who already have partial capability.
- **NOT claiming AI is the dominant proliferation driver.** Geopolitics, state programs, and traditional proliferation pathways remain more significant than AI-enabled non-state threats in most scenarios.
- **NOT claiming restriction-only solutions work.** Access denial is increasingly difficult; effective strategy requires balanced investment in detection, attribution, response, and resilience.
- **NOT claiming high confidence in probability estimates.** Scenario probabilities are subjective priors for decision support, not empirical predictions. Reasonable analysts may assign substantially different values.

---

## Executive Summary (One-Page Version)

> **Quick orientation for readers who need the core arguments without the full analysis.**

### Core Claims (5)

1. **Biological weapons are the highest-risk category** for AI-enabled proliferation due to eroding physical barriers and high AI contribution to knowledge synthesis
2. **AI primarily upgrades T1-T3 actors** (skilled individuals to organized non-state groups); it does not transform novices into capable threat actors
3. **The most likely near-term scenario is high-frequency attempts with limited success** - resource strain and public fear, not mass casualties
4. **Cyber-physical attacks on existing infrastructure** (labs, chemical plants) may be higher-leverage than synthesis assistance
5. **Governance windows are closing** - once capabilities proliferate, restrictions become much harder to implement

### Top 5 Actions

1. **Mandate universal DNA synthesis screening** with international harmonization
2. **Invest in attribution and response capabilities** - cannot rely on deterrence alone
3. **Establish cloud laboratory oversight frameworks** before the attack surface expands further
4. **Require WMD-relevant capability evaluations** before frontier AI deployment
5. **Fund defensive biodetection** as a high-value cross-threat investment

### Top 5 Indicators to Monitor

1. DNA synthesis screening intercept rates and patterns
2. AI model performance on biology/chemistry benchmarks
3. Cloud laboratory service expansion and security posture
4. Dark web discussion of AI + WMD capabilities
5. Progress (or lack thereof) on international governance coordination

### What Would Change This Assessment

- **Increase concern**: Confirmed AI-assisted WMD attempt; release of unrestricted biology-capable research agent; major cloud lab security breach
- **Decrease concern**: Effective international AI safety framework; robust attribution breakthrough; AI guardrails prove more durable than expected

---

## Table of Contents

1. [Introduction and Methodology](#introduction-and-methodology)
2. [Theoretical Frameworks](#theoretical-frameworks)
3. [The Current Technological Landscape (2025)](#the-technological-landscape)
4. [Historical Context: WMD Development and Technology](#historical-context)
5. [Biological Weapons: The Highest-Risk Domain](#biological-weapons)
6. [Chemical Weapons: Procurement, Scaling, and Safety Barriers](#chemical-weapons)
7. [Nuclear Weapons: Physical Barriers and Information Aggregation](#nuclear-weapons)
8. [Gene Drives: Long-Horizon Governance Gap](#gene-drives)
9. [Deployment Vectors: Aerosol Systems and Autonomous Delivery](#deployment-vectors)
10. [The Cyber-Physical Convergence](#cyber-physical)
11. [Counterarguments and Structural Barriers](#counterarguments)
12. [The Attribution Problem](#attribution-problem)
13. [International Variance](#international-variance)
14. [Second-Order Effects](#second-order-effects)
15. [Policy Recommendations by Stakeholder Type](#policy-recommendations)
16. [Uncertainties and Alternative Scenarios](#uncertainties)
17. [Signals and Early Indicators](#signals)
18. [Civil Liberties and Research Freedom Considerations](#civil-liberties)
19. [Conclusion](#conclusion)

---

## 1. Introduction and Methodology {#introduction-and-methodology}

### Purpose

The development of weapons of mass destruction has historically required either state-level resources or exceptional individual expertise combined with significant infrastructure. The Manhattan Project employed over 125,000 people. Aum Shinrikyo, despite millions of dollars and multiple PhD scientists, failed to effectively weaponize biological agents. These historical constraints have provided a de facto barrier to WMD proliferation.

We are now entering an era where autonomous AI agents capable of complex multi-step planning, information synthesis, and real-time adaptation become widely accessible. This projection examines whether and how AI agents might erode these historical barriers.

**Critical framing**: This analysis does not assume WMD attacks will increase. The goal is to understand how AI capabilities change the *nature* of proliferation risks, identify which weapon categories face the greatest barrier reduction, and recommend defensive preparations.

### Base-Rate Context

**To prevent fear-driven misreading, we anchor expectations:**

Actual WMD attacks by non-state actors remain extremely rare. The 1995 Tokyo subway attack (sarin) and 2001 anthrax letters represent essentially the entire modern history of non-state WMD use. The overwhelming majority of WMD-related arrests involve early-stage planning with minimal actual capability.

**The dominant near-term concern is likely:**
- Increased frequency of *attempts* with varying degrees of competence
- Crude attacks with limited casualties but significant psychological impact
- State-level proliferation acceleration using AI assistance
- Erosion of verification regimes as AI complicates attribution

Readers should interpret this analysis through that lens: the primary concern is *barrier reduction enabling more attempts*, with catastrophic mass-casualty events remaining low-probability tail risks.

### Methodology

This analysis draws on:

- **Current capability assessment** of AI agent systems and synthetic biology tools as deployed in late 2025
- **Historical case analysis** of WMD development programs (state and non-state)
- **Dual-Use Research of Concern (DURC)** literature and policy debates
- **Expert consultation** across biosecurity, nuclear security, and AI safety domains
- **Red team exercises** examining potential adversarial applications (conducted under controlled conditions)

We deliberately avoid:
- Specific technical implementation details for weapon synthesis
- Named pathogen sequences or synthesis routes
- Information not already publicly available in academic literature

### Definitions

**Chatbot vs. Autonomous Research Agent**: A critical distinction for 2025:

| Type | Capability | Risk Profile |
|------|------------|--------------|
| **Chatbot** (2022-2023 era) | Provides information in response to queries; no tool use; no persistence | Knowledge aggregation only |
| **Autonomous Research Agent** (2024-2025 era) | Executes multi-step tasks; uses tools (web browsing, code execution, file management); self-corrects on failure; maintains context across sessions | Shifts from knowledge to execution |

**AI Agent / Agentic Workflow**: An AI system (or coordinated system of models) capable of autonomous multi-step task execution, tool use, and goal-directed behavior with minimal human oversight per action. Modern agents can "loop" - execute a step, observe the result, adjust, and retry without human intervention.

**Computer Use Capabilities**: The ability of AI agents to interact with graphical interfaces, browse websites, fill forms, and operate software as a human would **[O]**. Examples include Claude's "computer use" (2024) and OpenAI's "Operator" (2025). This enables autonomous procurement, identity management, and logistics coordination.

**Biological Design Tools (BDTs)**: Specialized AI models for biological research, distinct from general-purpose LLMs. Examples include AlphaFold 3 (protein-ligand interactions), ESM3 (generative protein design), and RFdiffusion (de novo protein design) **[O]**. These tools often have fewer guardrails than consumer chatbots.

**Weapons of Mass Destruction (WMD)**: Biological, chemical, radiological, or nuclear weapons capable of causing mass casualties. We use the traditional CBRN framework while acknowledging that "mass destruction" thresholds vary significantly across categories.

**Uplift**: The degree to which AI assistance improves a non-expert's ability to accomplish a dangerous task. A key metric in AI safety evaluations.

**Cloud Laboratory**: A commercial service providing remote access to automated laboratory equipment, allowing users to execute experiments without physical presence.

**Gene Drive**: A genetic engineering technology designed to spread a particular genetic modification through a population faster than traditional inheritance.

### Threat Actor Taxonomy

To avoid the misleading implication that "AI democratizes WMD to everyone," this report uses a tiered actor model:

| Tier | Description | Pre-AI Capability | Examples |
|------|-------------|-------------------|----------|
| **T0** | Curious novice | No practical capability | Online researchers, ideologically motivated without resources |
| **T1** | Skilled individual with legitimate access | Limited by knowledge gaps | Disgruntled lab worker, trained chemist |
| **T2** | Small group with funding and logistics | Constrained by coordination and expertise aggregation | Well-funded extremist cell, organized criminal group |
| **T3** | Organized non-state with corruption/insider access | Historically capable of limited CBRN (Aum Shinrikyo) | Terrorist organizations, sophisticated criminal enterprises |
| **T4** | State or state-backed actor | Full WMD capability (historical programs) | Nation-state programs, state-sponsored proxies |

**How to use this taxonomy**: Throughout this report, we assess which tiers AI meaningfully upgrades. The key insight is that AI primarily benefits T1-T3 actors by reducing knowledge aggregation and planning barriers - it does not transform T0 into T3.

---

## 2. Theoretical Frameworks {#theoretical-frameworks}

This analysis draws on several established theoretical frameworks from security studies, biosecurity, and technology policy.

### Unified Risk Model

The following model underpins the analysis throughout this document:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           RISK MODEL                                     │
│                                                                          │
│   Risk = Capability × Access × Intent × Execution × (1-Interdiction)   │
│                              ×                                           │
│                         Impact Scale                                     │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────┬────────────────────┬──────────────────┬──────────────┐
│     Factor       │   AI Contribution  │   Bio (2025→30)  │  Nuke (→30)  │
├──────────────────┼────────────────────┼──────────────────┼──────────────┤
│ Capability       │ HIGH (knowledge    │   ↑↑ Rising      │   → Stable   │
│ (can attempt)    │ synthesis)         │                  │              │
├──────────────────┼────────────────────┼──────────────────┼──────────────┤
│ Access           │ MEDIUM (cloud labs,│   ↑ Rising       │   → Stable   │
│ (materials/tools)│ synthesis services)│                  │   (fissile)  │
├──────────────────┼────────────────────┼──────────────────┼──────────────┤
│ Intent           │ NONE (AI doesn't   │   → Stable       │   → Stable   │
│ (motivation)     │ create motivation) │                  │              │
├──────────────────┼────────────────────┼──────────────────┼──────────────┤
│ Execution        │ MEDIUM (guidance,  │   ↑ Rising       │   → Stable   │
│ (attempt→success)│ troubleshooting)   │   (slow)         │              │
├──────────────────┼────────────────────┼──────────────────┼──────────────┤
│ Interdiction     │ MIXED (AI helps    │   ↓ Declining    │   → Stable   │
│ (detection rate) │ both sides)        │   (pressure)     │   (strong)   │
├──────────────────┼────────────────────┼──────────────────┼──────────────┤
│ Impact Scale     │ LOW (physics/bio   │   Wide range     │ Catastrophic │
│ (harm if success)│ constrain)         │                  │              │
└──────────────────┴────────────────────┴──────────────────┴──────────────┘

Key insight: AI primarily affects Capability and Access (cognitive barriers).
Physical barriers, Intent, and Impact Scale are largely AI-independent.
```

**How to read this model**: Each section of this report examines how AI affects specific multipliers in this equation. The probability decomposition in Section 16 applies this model quantitatively.

### The Democratization of Lethality

**Audrey Kurth Cronin's framework** from "Power to the People" (2020) describes how each technological era redistributes the capacity for violence. AI represents the latest such redistribution, but with a crucial difference: previous technologies (dynamite, small arms) democratized *physical* capabilities. AI democratizes *cognitive* capabilities - the planning, knowledge synthesis, and optimization that previously required years of specialized training.

For WMD, this means:
- The barrier was never purely physical (materials exist)
- The barrier was also cognitive (knowing what to do with materials)
- AI specifically attacks the cognitive barrier while physical barriers remain

### Dual-Use Research of Concern (DURC)

The **DURC framework**, developed through debates over H5N1 transmissibility research (2011-2012), recognizes that legitimate scientific research can generate knowledge applicable to harmful purposes. Key insights:

- Information cannot be "un-discovered"
- Publication decisions involve weighing scientific benefit against misuse potential
- The research community has historically self-regulated through institutional review

AI agents challenge this framework because:
- They can synthesize DURC-relevant information from dispersed, individually innocuous sources
- Publication decisions become moot when AI can reconstruct restricted information
- Self-regulation assumes human researchers as the primary actors

### The Tacit Knowledge Gap

**Michael Polanyi's concept of tacit knowledge** - skills that cannot be fully articulated and must be learned through practice - is central to understanding WMD barriers. Much of weapons development relies on:

- Sensory cues (colors, textures, smells indicating reaction progress)
- Equipment calibration requiring hands-on experience
- Safety protocols learned through practice
- "Laboratory intuition" accumulated over years

AI agents can transmit explicit knowledge but traditionally cannot transfer tacit knowledge. However, two developments challenge this:

1. **AI-guided instruction**: Real-time guidance that interprets user observations and provides adaptive feedback
2. **Cloud laboratories**: Robotic systems that embody tacit knowledge in automated protocols

### Information Hazards Framework

**Nick Bostrom's concept of "information hazards"** identifies categories of knowledge that, once disseminated, can cause harm regardless of intent:

- **Data hazards**: Specific information enabling harmful actions (pathogen sequences, synthesis routes)
- **Idea hazards**: Concepts that suggest new harmful possibilities
- **Attention hazards**: Drawing attention to vulnerabilities

AI agents challenge information hazard management because:
- They can reconstruct restricted information from dispersed innocuous sources
- They lower the barrier from "knowledge" to "actionable guidance"
- They can personalize dangerous information to specific user capabilities

### The Unilateralist's Curse

**Bostrom and Ord's "Unilateralist's Curse"** describes a critical dynamic: when a capability becomes accessible to many actors, even if the vast majority (99.9%) are responsible, the small minority (0.1%) who would misuse it will eventually do so.

For AI and WMD:
- AI democratizes access to planning and synthesis knowledge
- As millions gain access, the "curse" becomes statistically inevitable
- The question shifts from "whether" to "when" and "how catastrophic"
- Defensive strategies must assume misuse will be attempted

### Offense-Defense Balance

Security studies' **offense-defense balance** theory asks whether prevailing technology favors attackers or defenders. For WMD and AI:

| Factor | Favors Offense | Favors Defense |
|--------|---------------|----------------|
| Knowledge accessibility | AI aggregates dispersed information | AI can also detect dangerous queries |
| Physical materials | Some barriers eroding (DNA synthesis) | Nuclear/chemical materials remain controlled |
| Attribution | AI complicates attribution | AI forensics improving |
| Detection | Novel agents may evade detection | AI-enhanced surveillance possible |
| Response speed | Attack can occur without warning | Defensive AI can monitor in real-time |

The balance varies significantly across WMD categories, which is why biological, chemical, and nuclear weapons require separate analysis.

### Key Literature

| Work | Author(s) | Relevance |
|------|-----------|-----------|
| *Power to the People* | Audrey Kurth Cronin (2020) | Technology diffusion and non-state violence |
| *Biohazard* | Ken Alibek (1999) | Soviet bioweapons program; scale of state capabilities |
| *Germs* | Miller, Engelberg, Broad (2001) | History of biological weapons programs |
| *The Demon in the Freezer* | Richard Preston (2002) | Smallpox and bioweapons policy |
| *Destined for War* | Graham Allison (2017) | Great power dynamics affecting proliferation |
| *Nuclear Terrorism* | Graham Allison (2004) | Non-state nuclear threats assessment |
| *Personal Knowledge* | Michael Polanyi (1958) | Tacit knowledge theory |
| *NIST AI RMF* | NIST (2023) | AI risk management framework |
| *Information Hazards* | Nick Bostrom (2011) | Framework for dangerous knowledge |
| *The Unilateralist's Curse* | Bostrom & Ord (2015) | Why misuse becomes inevitable with proliferation |
| *Operational Risks of AI in Biological Attacks* | RAND Corporation (2024) | Grounded assessment of current risk levels **[O]** |
| *Countdown to Zero Day* | Kim Zetter (2014) | Stuxnet and cyber-physical attacks |

### 2024-2025 Policy Developments

| Reference | Date | Relevance |
|-----------|------|-----------|
| **Bletchley Declaration** | November 2023 | First international consensus on frontier AI risks including CBRN **[O]** |
| **Seoul AI Safety Summit Commitments** | May 2024 | Extended Bletchley with specific bio-risk language **[O]** |
| **US Executive Order 14110** (Section 4.4) | October 2023 | Mandates DOE/DHS evaluation of AI role in CBRN threats **[O]** |
| **Helios / OpenAI "Strawberry" Evaluations** | 2024 | Human-in-the-loop tests of whether AI helps PhD-level biologists plan faster **[O]** |
| **RAND "Operational Risks" Report** | 2024 | Definitive "uplift" study finding limited current risk but monitoring needed **[O]** |
| **Anthropic RSP Framework** | 2023-2024 | Responsible Scaling Policy with CBRN capability thresholds **[O]** |

---

## 3. The Current Technological Landscape (2025) {#the-technological-landscape}

### AI Agent Capabilities

AI agents in late 2025 can:

- Synthesize information from thousands of scientific papers in seconds
- Conduct extended multi-step research tasks with minimal supervision
- Operate tools including web browsers, code execution, and API interactions
- Interface with laboratory information management systems (LIMS)
- Generate and optimize experimental protocols
- Analyze results and iteratively refine approaches
- Maintain persistent goals across sessions

For biosecurity-relevant capabilities specifically:

- **Protein structure prediction**: AlphaFold and successors provide detailed structural information previously requiring years of laboratory work
- **Sequence design**: AI can suggest genetic modifications to achieve specified functions
- **Literature synthesis**: Agents can identify relevant findings across fragmented scientific literature
- **Protocol optimization**: AI can improve success rates for complex laboratory procedures

### Capability Trend: Vision-Language Models and Tacit Knowledge Erosion

**Why this matters for defenders**: The traditional "tacit knowledge" barrier assumed that laboratory skills require hands-on training. Vision-Language Models (VLMs) that can "see" through cameras may be beginning to erode this barrier.

**Capability evolution (for monitoring purposes)**:

| Generation | Capability | Tacit Knowledge Impact |
|------------|------------|----------------------|
| Text-only LLMs (2022-2023) | Written instruction only | Cannot interpret physical observations |
| Basic VLMs (2024) | Static image interpretation | Can identify equipment, reagents |
| Advanced VLMs (2025) | Real-time video analysis | Can provide feedback on ongoing procedures |
| Projected (2026+) | Integrated lab automation | Direct control of robotic systems |

**What defenders should monitor**:
- VLM benchmark performance on laboratory procedure interpretation
- Integration of VLMs with laboratory automation platforms
- Availability of VLM fine-tuning for scientific domains
- Educational applications that may have dual-use potential

**Current state assessment**: As of late 2025, VLMs can interpret laboratory images and provide general guidance, but reliable real-time procedure coaching remains limited. The gap between "understanding what's happening" and "reliably guiding a novice to success" remains significant but is narrowing.

**Visual Troubleshooting Scenario** (for defender awareness):

The convergence of consumer hardware and VLM capabilities creates a specific vector:
- Smart glasses (Ray-Ban Meta, etc.) can stream video to cloud VLMs **[O]**
- An actor could receive real-time audio feedback while performing procedures
- VLM interprets visual state ("color too dark," "precipitate forming") and suggests adjustments **[E]**
- This partially substitutes for the mentor-mentee relationship that traditionally transmitted tacit knowledge

**Defender monitoring priorities**:
- VLM API access patterns suggesting lab procedure guidance
- Integration of VLMs with wearable camera hardware
- Educational chemistry/biology applications that could be repurposed

**Current limitation** **[E]**: VLMs still make errors on domain-specific interpretation; a failed procedure may be unrecoverable. But the gap is narrowing with each model generation.

**Actor tier relevance**: VLM-assisted guidance primarily benefits T1-T2 actors (individuals with some training seeking to expand capabilities). T0 actors still lack the baseline competence to benefit; T3-T4 actors have access to human expertise.

### Governance Challenge: Open-Weight Models

**The policy gap**: Most AI safety measures (guardrails, usage monitoring, refusal training) exist at the API level for closed commercial models. Open-weight models that can be run locally or fine-tuned present a distinct governance challenge.

**The landscape (2025)**:

| Model Type | Guardrails | Monitoring | Fine-tuning | Governance Lever |
|------------|------------|------------|-------------|------------------|
| Closed API (GPT, Claude) | Strong | Yes | No | Provider responsibility |
| Open-weight (Llama, Mistral) | Varies | No (local) | Yes | Release decisions only |
| Fine-tuned variants | Often removed | No | Already done | Difficult to control |
| Specialized biology models | May be absent | No | Domain-specific | Research community norms |

**What defenders should monitor**:
- Release decisions for high-capability open-weight models
- Emergence of specialized fine-tunes in concerning domains
- Dark web availability of "jailbroken" or domain-specialized variants
- Compute accessibility for running large open-weight models

**Policy implications**:
1. **Pre-release evaluation**: Capability assessments before open-weight release
2. **Compute governance**: High-capability models may require substantial compute, creating a monitoring opportunity
3. **Community norms**: Engaging the open-source AI community on responsible release
4. **Accepting limitations**: Some proliferation is likely unavoidable; invest in detection and response accordingly

**Actor tier relevance**: Open-weight models primarily benefit T2-T3 actors with technical sophistication to deploy and potentially fine-tune models. T0-T1 actors are more likely to use accessible commercial APIs (where guardrails apply).

**Institutional references**:
- NIST AI 600-1: AI Risk Management Framework companion guidance
- Executive Order 14110 on Safe, Secure, and Trustworthy AI (reporting requirements)
- Frontier Model Forum voluntary commitments on capability evaluation

### Synthetic Biology Infrastructure

The synthetic biology infrastructure has expanded dramatically:

**DNA Synthesis Services (2025)**:
- Multiple commercial providers offer gene synthesis services
- Turnaround times measured in days to weeks
- Costs have dropped to cents per base pair
- Screening protocols exist but vary in rigor

**Cloud Laboratory Services**:
- Commercial platforms offer remote access to automated wet labs
- Users can execute protocols without physical laboratory access
- Equipment includes liquid handlers, PCR machines, sequencers
- Some platforms offer AI-assisted protocol design

**Open-Source Tools**:
- Comprehensive bioinformatics toolkits freely available
- CRISPR design tools accessible to non-experts
- Community protocols for common procedures
- Educational resources lowering learning curves

### Current Safeguards

**DNA Synthesis Screening**:
- International Gene Synthesis Consortium (IGSC) guidelines
- Screening against databases of known pathogen sequences
- Customer verification requirements (varying enforcement)
- Limitations: novel sequences may not match known threats; not all providers participate

**Export Controls**:
- Australia Group guidelines on biological agents and equipment
- Varying national implementation
- Challenges with dual-use equipment (legitimate applications)

**Institutional Biosafety**:
- Institutional Biosafety Committees (IBCs) at research institutions
- Select Agent regulations for dangerous pathogens
- BSL-4 laboratory requirements for most dangerous work
- Limitations: applies to institutional settings, not all actors

### What We've Observed in 2025

Evidence regarding AI-assisted biosecurity threats, categorized by epistemic status:

**Demonstrated in open evaluations:**
- AI models can provide general information about pathogen biology from open literature
- Frontier AI models refuse most explicit requests for weapons guidance but inconsistencies exist across models and prompt formulations
- AI systems show measurable "uplift" in non-expert comprehension of complex biological concepts

**Supported by limited disclosures:**
- DNA synthesis screening has intercepted concerning orders (industry statements, limited specifics)
- Security services have begun integrating AI into threat monitoring (procurement signals, job postings)

**Plausible but not confirmed:**
- AI assistance in early-stage criminal planning (law enforcement statements without public case details)
- Jailbreaking techniques specifically targeting biosecurity guardrails (security research community reports)

**Speculative / emerging:**
- AI-enabled gain-of-function design assistance (theoretical capability, no documented attempts)
- Cloud laboratory exploitation for harmful protocols (no known incidents)

**Absence of evidence (notable):**
- No documented cases of AI-enabled biological weapon development
- No confirmed AI-assisted WMD attacks or advanced attempts

*Note: Absence of public reporting does not equal absence of classified intelligence. Our assessment is necessarily limited to open sources.*

---

## 4. Historical Context: WMD Development and Technology {#historical-context}

### State Programs: The Scale of Serious Capability

Understanding what *actual* WMD programs required provides context for assessing AI's impact:

**The Manhattan Project (1942-1945)**:
- Peak employment: 125,000+ workers
- Cost: $2 billion ($28 billion in 2025 dollars)
- Required industrial-scale facilities (Oak Ridge, Hanford)
- Even with vast resources, development took 3 years

**Soviet Biopreparat Program (1970s-1990s)**:
- Employed 60,000+ people at peak
- Dozens of research and production facilities
- Weaponized numerous pathogens including anthrax, smallpox, plague
- Required decades to develop sophisticated delivery systems

**Key insight**: State-level programs achieved capabilities far beyond what any non-state actor has approached. The question is whether AI changes the *scaling* of these requirements.

### Non-State Attempts: The Capability Gap

**Aum Shinrikyo (1984-1995)**:
- Resources: Estimated $300 million to $1 billion
- Personnel: Multiple PhD scientists across disciplines
- Attempts: Botulinum toxin (failed), anthrax (failed), sarin (partially successful)
- Outcome: Tokyo subway attack killed 13, injured thousands

**Critical lesson**: Despite exceptional resources and expertise, Aum's biological program failed completely. Their chemical attack succeeded but at far lower casualty levels than their ambitions. The gap between *intent and capability* was enormous.

**Why did Aum fail at bioweapons?**
1. Tacit knowledge gaps despite theoretical expertise
2. Difficulty obtaining virulent pathogen strains
3. Weaponization challenges (delivery systems, stability)
4. Operational security compromises

**2001 Anthrax Letters**:
- Perpetrator: Likely single individual with professional laboratory access
- Outcome: 5 deaths, 17 infections, massive societal disruption
- Method: Existing laboratory stocks, not de novo synthesis
- Critical factor: *Access* to prepared materials, not synthesis capability

**Rajneeshee Bioterror Attack (1984)**:
- Perpetrator: Religious cult in Oregon
- Agent: Salmonella typhimurium (common food pathogen)
- Method: Contamination of restaurant salad bars
- Outcome: 751 illnesses, no deaths, significant disruption
- **Critical lesson**: Low-tech attacks with common agents can achieve "mass disruption" without "mass destruction." AI agents could optimize logistics of such simple attacks for massive scale.

**Stuxnet (2010)**:
- Perpetrator: Nation-state (US/Israel)
- Target: Iranian nuclear centrifuges
- Method: Malware causing physical destruction via control system manipulation
- Outcome: Significant delay to Iranian nuclear program
- **Critical lesson**: Code can cause physical destruction. This establishes the precedent for "cyber-physical" attacks on WMD-related infrastructure - a vector AI agents could enable.

### Technology Inflection Points

Each major technology shift has affected WMD accessibility differently:

| Technology | Effect on Barriers | Limiting Factor |
|------------|-------------------|-----------------|
| Internet (1990s) | Dispersed information more accessible | Still required physical capability |
| Genome sequencing (2000s) | Pathogen sequences publicly available | Still required synthesis capability |
| CRISPR (2012+) | Gene editing dramatically simplified | Still required laboratory infrastructure |
| DNA synthesis services (2010s+) | Outsourced synthesis capability | Screening protocols; sequence length limits |
| Cloud laboratories (2020s) | Outsourced laboratory execution | Monitoring; protocol restrictions |
| AI agents (2024+) | Knowledge synthesis and guidance | Physical barriers; tacit knowledge |

**The pattern**: Each technology erodes one barrier while others remain. AI attacks the *cognitive* barrier (knowing what to do) but physical barriers persist.

---

## 5. Biological Weapons: The Highest-Risk Domain {#biological-weapons}

### Why Biological Represents the Greatest AI Risk

Biological weapons represent the category where AI poses the most significant proliferation risk for several reasons:

1. **Information-intensive**: Much of bioweapons development is knowledge synthesis and protocol optimization - AI's strength
2. **Decreasing physical barriers**: DNA synthesis services and cloud labs reduce infrastructure requirements
3. **Detection difficulty**: Biological materials are harder to detect than nuclear or large-scale chemical facilities
4. **Dual-use ubiquity**: Most equipment is identical to legitimate research tools
5. **Self-replicating potential**: Unlike chemical or nuclear, biological agents can multiply

### Current AI Capabilities in Biosecurity Context

**What AI can currently do (late 2025)**:

| Capability | Status | Barrier Reduction |
|------------|--------|-------------------|
| Explain pathogen biology | Widely available | Moderate - accelerates learning |
| Identify virulence factors from literature | Available with some guardrails | Moderate - synthesizes dispersed information |
| Design genetic modifications | Available with guardrails | Significant - previously required expertise |
| Optimize synthesis protocols | Partially available | Significant - improves success rates |
| Guide laboratory procedures in real-time | Emerging capability | Potentially high - bridges tacit knowledge gap |
| Predict immune evasion mutations | Research stage | Potentially very high - enables novel agents |

**What AI cannot currently do**:
- Provide working pathogen samples (physical barrier)
- Execute laboratory procedures without automation infrastructure
- Guarantee synthesis success (biological complexity)
- Evade all screening systems

> **Key Distinction: Design vs. Operational Uplift**
>
> | Stage | AI Uplift Level | Why |
> |-------|-----------------|-----|
> | **Design assistance** | High | Literature synthesis, hypothesis generation, protocol drafting - AI excels at information tasks |
> | **Operational success** | Low-Medium | Physical execution, error recovery, safety management - tacit knowledge and iteration still required |
> | **Net risk driver** | Attempt frequency + occasional competent actor | Most T1-T2 attempts will fail; risk comes from volume and the tail of capable actors who succeed |
>
> *Skeptical reviewers should note: LLMs can talk, wet labs are hard, and most AI-assisted knowledge does not transfer to operational success. Our concern is not the median user but the tail distribution of attempts.*

### Cloud Laboratory Security Considerations

Cloud laboratories - commercial services providing remote access to automated laboratory equipment - represent an area requiring enhanced defensive attention.

**Why defenders should prioritize this domain**:
- Automated execution reduces traditional "tacit knowledge" barriers
- Remote access complicates identity verification and intent assessment
- Protocol submission via API enables systematic iteration
- The legitimate research community increasingly relies on these services

**Defensive architecture for cloud lab providers**:

| Control Layer | Mechanism | Implementation Challenge |
|--------------|-----------|-------------------------|
| **Identity verification** | KYC for customers, institutional affiliation checks | Privacy concerns, international access |
| **Protocol classification** | Automated screening of submitted protocols | Novel sequences, fragmented requests |
| **Anomaly detection** | Pattern analysis across customer behavior | Baseline definition, false positives |
| **Audit logging** | Comprehensive records for post-incident investigation | Storage, retention policies |
| **Incident reporting** | Mandatory disclosure of concerning requests | Threshold definition, liability |
| **International coordination** | Shared threat intelligence across providers | Competitive concerns, jurisdictional limits |

**Current state of defenses**: Leading providers participate in security frameworks and conduct sequence screening. However, coverage is incomplete, enforcement varies internationally, and novel threat patterns may evade current detection.

**Defender focus areas**:
- Strengthening screening for fragmented or obfuscated requests
- International harmonization of oversight standards
- Integration of AI-assisted threat detection
- Clear incident reporting protocols

**Actor tier relevance**: This vector primarily concerns T1-T2 actors (skilled individuals or small groups) who might otherwise lack laboratory access. T0 actors lack the technical sophistication; T3-T4 actors have alternative access methods.

### Governance Challenge: Distributed Synthesis Capability

Desktop-scale DNA synthesis capability is expanding, creating a governance challenge for frameworks designed around centralized commercial services.

**The shifting landscape**:
- Benchtop synthesizers becoming more capable and affordable
- Local synthesis bypasses commercial provider screening
- Current safeguards assume centralized chokepoints

**Defender implications**:
- Governance frameworks require adaptation for distributed capability
- Device-level controls become relevant (manufacturer responsibility)
- Post-synthesis detection and attribution gain importance
- International harmonization of device standards needed

**Actor tier relevance**: Device access itself becomes a barrier (cost, export controls, institutional procurement). This primarily affects the T1-T2 boundary - expanding capability for actors with some resources while remaining inaccessible to T0.

**Policy direction**: Governance should shift from pure "access denial" toward comprehensive approaches including device-level safeguards, detection capabilities, and attribution infrastructure.

### Pathogen Categories and AI Risk

Different pathogen types face different AI-related risks:

**Bacteria (e.g., anthrax, plague)**:
- Genomes relatively small, easier to synthesize
- Some strains available in environment
- Cultivation possible with modest equipment
- AI risk: Moderate to significant - can guide cultivation and enhancement

**Viruses (e.g., influenza, coronaviruses)**:
- Smaller genomes, synthesis increasingly feasible
- Require host cells to replicate
- Some can be recovered from synthetic genomes alone
- AI risk: Significant - can guide rescue from synthetic genomes

**Toxins (e.g., ricin, botulinum)**:
- Defined chemical structures
- Some synthetically accessible
- No replication capability
- AI risk: Moderate - synthesis guidance available, limited scaling

### Gain-of-Function Considerations

AI could potentially assist with gain-of-function modifications:

**Concerning capabilities**:
- Predicting mutations that increase transmissibility
- Identifying immune evasion strategies
- Optimizing pathogen stability
- Suggesting virulence factor modifications

**Limiting factors**:
- Wet lab validation still required
- Many modifications reduce fitness
- Biological systems are complex and unpredictable
- Most AI predictions would fail in practice

**Our assessment**: AI gain-of-function guidance is a genuine concern but the gap between prediction and validation remains substantial. The risk increases as AI models improve and as AI-lab integration deepens.

---

## 6. Chemical Weapons: Procurement, Scaling, and Safety Barriers {#chemical-weapons}

### Chemical Weapons and AI: A Middle Ground

Chemical weapons occupy an intermediate position in AI-related risk. **The dominant constraints are physical and operational, not informational**:

- **Procurement**: Regulated precursors, monitored purchases, supply chain surveillance
- **Scaling**: Industrial equipment requirements for quantities beyond small-scale harm
- **Safety**: Synthesis is dangerous to the operator; errors are often fatal
- **AI contribution**: Modest assistance with knowledge gaps, but physical barriers dominate

**Actor tier relevance**: Chemical weapons primarily concern T2-T3 actors (groups with resources and some expertise). T0-T1 actors face compounding barriers; T4 actors have existing capabilities.

### Current Landscape

**Established chemical weapons (nerve agents, blister agents)**:
- Synthesis routes well-documented in scientific literature
- Most effective agents require regulated precursors
- Large-scale production requires industrial equipment
- Detection of precursor purchases is a key control mechanism

**AI's potential contribution**:

| Task | AI Capability | Risk Level |
|------|---------------|------------|
| Identify synthesis routes | High - information in training data | Moderate - already accessible |
| Suggest precursor substitutions | Moderate - chemical reasoning improving | Significant - could evade controls |
| Optimize reaction conditions | High - well-suited to optimization | Moderate - improves success rates |
| Guide inexperienced synthesizers | Moderate - can provide instructions | Significant - bridges knowledge gap |
| Scale-up guidance | Moderate - engineering principles apply | Moderate - production scaling difficult |

### The Precursor Substitution Threat

The most concerning AI capability for chemical weapons is **precursor substitution**:

**How this works**:
- Regulated precursor lists target known synthesis routes
- AI could identify unregulated chemicals with similar properties
- Purchases could avoid triggering monitoring systems
- Supply chain optimization could fragment orders across suppliers

**Limitations**:
- Alternative routes often less efficient
- Substitutions may introduce impurities
- Some precursors are uniquely suited (no good alternatives)
- Large-scale production still requires infrastructure

### Real-Time Synthesis Guidance

AI agents could provide "over-the-shoulder" guidance for synthesis:

**Capabilities**:
- Interpret visual observations (color changes, precipitates)
- Suggest adjustments based on conditions
- Troubleshoot common problems
- Guide safety procedures (ironically)

**This is concerning because**:
- Reduces requirement for formal chemistry training
- Provides adaptive feedback traditional instructions cannot
- Available 24/7 without human oversight
- Multiple attempts can refine technique

**Limiting factors**:
- Chemical synthesis still dangerous without proper training
- Failure modes can be fatal (explosions, toxic exposure)
- Equipment requirements remain
- Scale-up from laboratory to weapon quantities is distinct challenge

---

## 7. Nuclear Weapons: Physical Barriers and Information Aggregation {#nuclear-weapons}

### Nuclear Weapons: The Strongest Physical Barriers

Nuclear weapons remain the category with the strongest barriers to AI-enabled proliferation:

**Why nuclear is different**:
1. **Fissile material scarcity**: No AI can synthesize highly enriched uranium or plutonium
2. **Industrial requirements**: Enrichment requires either massive facilities (gaseous diffusion) or sophisticated equipment (centrifuges)
3. **Detection**: Nuclear materials are detectable; facilities have distinctive signatures
4. **International monitoring**: IAEA safeguards, export controls on dual-use equipment
5. **Tacit knowledge requirements**: Weapon design involves engineering challenges AI cannot fully bridge

### AI's Limited but Non-Zero Contribution

> **Critical clarification**: The information aggregation risk discussed below is primarily relevant to **state programs (T4)** or **state-backed actors** seeking to accelerate nuclear development. AI does not make nuclear weapons accessible to non-state actors - the fissile material barrier is absolute and AI-independent.

**Information aggregation risk (state-level concern)**:
- Historical weapon designs exist in fragmented declassified documents
- Early designs (gun-type, implosion) are relatively simple in principle
- AI could compile scattered information into more coherent guidance for aspiring state programs
- "Forgotten" technical details from 1940s-1950s could be recovered

**Actor tier relevance**: Nuclear weapons remain a T4 (state) domain. AI may accelerate state programs but does not meaningfully enable T0-T3 actors. This is the lowest AI-related risk category among WMD types.

**What AI can potentially provide**:
| Information Type | Availability | AI Contribution |
|-----------------|--------------|-----------------|
| Basic physics | Public knowledge | Minimal - widely known |
| Historical designs | Fragmented but public | Moderate - can aggregate |
| Engineering details | Partially classified | Limited - significant gaps |
| Critical dimensions | Classified | Cannot provide |
| Fissile material acquisition | Illegal markets exist | Cannot directly assist |

### The Radiological Threat (Dirty Bombs)

Radiological dispersal devices ("dirty bombs") face different dynamics:

**Lower barriers than nuclear weapons**:
- Radioactive materials more accessible (medical, industrial sources)
- No fission/fusion required - conventional explosives disperse material
- AI could assist with source identification and dispersal optimization

**Significant limitations**:
- Casualty potential much lower than nuclear weapons
- Primary effect is psychological and economic
- Material handling dangerous to perpetrator
- Detection of radioactive materials is possible

**AI contribution**: Could assist with identifying sources, optimizing dispersal, and planning deployment, but physical acquisition remains the key barrier.

### Supply Chain Security

The most significant AI risk for nuclear proliferation may be supply chain compromise:

**How AI could assist state programs**:
- Identifying dual-use equipment suppliers
- Optimizing procurement to avoid detection
- Designing facilities to minimize detection signatures
- Analyzing IAEA inspection patterns

This is primarily a concern for state-level actors or state-supported groups rather than independent non-state actors.

---

## 8. Gene Drives: Long-Horizon Governance Gap {#gene-drives}

> **Section Framing**: This section addresses a **strategic, long-horizon** concern rather than a near-term operational threat. Gene drives are included because:
> - AI specifically accelerates the computational aspects of gene drive design
> - No existing treaty framework addresses this vector
> - The governance window is open now but may close as capabilities mature
>
> **For near-term priorities**, see Sections 5 (Biological), 10 (Cyber-Physical), and the Executive Summary.

### What Are Gene Drives?

Gene drives are genetic engineering systems designed to spread a particular genetic modification through a population faster than traditional Mendelian inheritance. Unlike other WMD categories, gene drives represent an entirely novel threat vector that AI could uniquely enable.

**How gene drives work**:
- Traditional inheritance: 50% chance of passing gene to offspring
- Gene drive: Near-100% inheritance rate through copying mechanism
- Effect: Genetic modification spreads through entire population over generations

### Gene Drives as Potential Weapons

**Theoretical applications (not endorsing, analyzing)**:

| Target | Mechanism | Concern Level |
|--------|-----------|---------------|
| Agricultural crops | Introduce susceptibility to pathogens | High - food security |
| Livestock | Reduce fertility or introduce disease | High - economic warfare |
| Disease vectors (mosquitoes) | Could be weaponized after legitimate development | Medium - dual-use |
| Invasive species | Legitimate use; could be misdirected | Low - limited harm potential |
| Human populations | Theoretically possible; practically extremely difficult | Speculative - major barriers |

### AI's Role in Gene Drive Development

Gene drives represent an area where AI capabilities directly intersect with technical development. Understanding the computational bottlenecks helps defenders identify where AI provides the most significant acceleration.

**Computational bottlenecks where AI provides acceleration**:

| Bottleneck | Traditional Approach | AI Contribution | Defender Monitoring Priority |
|------------|---------------------|-----------------|----------------------------|
| **Guide RNA design** | Manual selection, trial and error | Off-target prediction, efficiency optimization | Track guide RNA design tool development |
| **Drive efficiency prediction** | Laboratory testing (slow, expensive) | In silico modeling of drive dynamics | Monitor AI benchmarks on gene drive prediction |
| **Resistance evolution modeling** | Population genetics simulations | Accelerated evolutionary modeling | Track AI capabilities in evolutionary prediction |
| **Ecological impact assessment** | Field trials (regulated, slow) | Multi-species interaction modeling | Monitor ecological modeling AI development |
| **Target species selection** | Expert knowledge, literature review | Systematic analysis of target vulnerabilities | Watch for AI tools targeting specific organisms |

**What this means for defenders**:
- Gene drive design is *computationally intensive* - exactly where AI excels
- AI acceleration primarily affects *design and optimization* phases
- *Wet lab validation* remains required - a detection opportunity
- *Environmental release* is the chokepoint where intervention is most feasible

**AI can assist with**:
- Designing guide RNAs for CRISPR-based drives with reduced off-target effects
- Predicting drive efficiency and spread dynamics across populations
- Modeling population-level and ecosystem effects
- Optimizing drive components for stability and inheritance rate

**Barriers remain**:
- Ecological effects remain difficult to predict accurately (complex systems)
- Resistance evolution is likely and may defeat drive mechanisms
- Requires release into environment - a potential detection opportunity
- Long timescales reduce tactical utility for most actor types

### Why Gene Drives Warrant Special Attention

1. **No existing treaty framework**: Unlike biological, chemical, or nuclear weapons, no international agreement specifically addresses gene drives
2. **Dual-use research is active**: Legitimate research (malaria control) develops capabilities applicable to weapons
3. **AI uniquely positioned**: Gene drive design is computationally intensive - exactly where AI excels
4. **Difficult to attribute**: Once released, tracing origin becomes extremely difficult
5. **Potentially irreversible**: Unlike other weapons, effects on ecosystems may be permanent

### Critical Nuance: Timescale Mismatch

**Gene drives are not tactical weapons**. Unlike other WMD categories, they operate on generational timescales:

- Effects manifest over months to years, not hours to days
- Population-level impact requires multiple breeding cycles
- This limits tactical utility for most actor types
- However, strategic economic or ecological warfare remains a concern

**Actor tier relevance**: Gene drives primarily concern sophisticated T3-T4 actors with long-term strategic objectives. T0-T2 actors seeking immediate impact would not benefit from this vector.

### Governance Anchors

While no specific gene drive treaty exists, governance can build on existing frameworks:

| Existing Framework | Applicability |
|-------------------|---------------|
| **Cartagena Protocol** (biosafety) | Environmental release of modified organisms |
| **Nagoya Protocol** | Access and benefit-sharing for genetic resources |
| **Environmental release regulations** | National frameworks for GMO releases |
| **BWC** | If designed to harm human health or agriculture |
| **Research ethics frameworks** | Institutional review for dual-use research |

**Policy direction**: Gene drive governance need not start from zero. Extending and strengthening existing environmental and biosafety frameworks is a viable near-term approach.

### Current Status and Near-Term Projection

**Current (2025)**:
- Gene drive research ongoing for public health applications
- No known weaponization attempts
- Regulatory frameworks underdeveloped
- AI tools increasingly integrated into design process

**2026-2028 projection**:
- Capabilities mature through legitimate research
- Regulatory discussions intensify
- First environmental releases (controlled, legitimate)
- Potential for "garage biology" access as tools proliferate

**2029-2030 projection**:
- Technology potentially accessible to sophisticated non-state actors
- Attribution challenges become acute
- International governance discussions likely but may lag capability

---

## 9. Deployment Vectors: Aerosol Systems and Autonomous Delivery {#deployment-vectors}

### Why Deployment Matters

Even crude biological or chemical agents can cause significant harm with effective delivery. AI agents may contribute to deployment capabilities independent of weapon synthesis:

**Key insight for defenders**: Delivery and dispersion mechanics can dominate impact; even crude agents may cause significant harm with optimized delivery. AI may improve planning and targeting - defenders should prioritize detection and response capabilities.

### Delivery Mechanism Defense Considerations

This section summarizes defensive priorities without detailing specific attack methodologies.

**Why delivery matters for defense**: Historical analysis shows that delivery failure is a common point of attack degradation. Defensive resources focused on delivery detection and disruption can be effective even when agent synthesis cannot be prevented.

**Defensive architecture by vector**:

| Vector Category | Detection Opportunity | Response Window | Defensive Priority |
|----------------|----------------------|-----------------|-------------------|
| Aerosol systems | Equipment anomalies, environmental sensors | Minutes to hours | Environmental monitoring, rapid response |
| Autonomous platforms | RF signatures, visual detection, geofencing | Varies by platform | Counter-drone systems, access control |
| Fixed infrastructure | Process monitoring, quality control | Ongoing | SCADA security, redundant controls |
| Supply chain | Procurement patterns, custody tracking | Days to weeks | Chain of custody, testing protocols |

**Technical barriers that persist**:
- Effective dispersion remains technically challenging
- Many agents degrade rapidly under environmental conditions
- Testing without exposure is difficult (limits iteration)
- Detection technology is improving

**Actor tier relevance**: Sophisticated delivery primarily benefits T2-T3 actors who have agent access but lack state-level delivery infrastructure. T0-T1 actors face compounding barriers at both synthesis and delivery stages.

### Autonomous System Security

The proliferation of autonomous robots in public spaces creates a expanding attack surface requiring proactive defense:

**Defensive considerations**:
- Robots increasingly have legitimate access to spaces (delivery, cleaning, security)
- Compromised or custom platforms represent potential vectors
- Detection systems should account for authorized autonomous presence
- Payload limitations and conspicuousness currently constrain threat

**Defender priorities**:
- Geofencing and access control for sensitive areas
- Behavioral anomaly detection for autonomous systems
- Supply chain security for commercial robot platforms
- Counter-autonomous system capabilities for high-value locations

**Trend to monitor**: As autonomous robots become ubiquitous, they become less conspicuous. Defensive frameworks should anticipate this evolution.

### Infrastructure Protection

High-value infrastructure requires layered defense against delivery-focused attacks:

**Defensive layers**:
1. **Physical access control**: Limiting approach to sensitive areas
2. **Environmental monitoring**: Air quality, contamination detection
3. **HVAC security**: Filtration, access control, monitoring
4. **Rapid response protocols**: Evacuation, containment, medical response
5. **Resilience and redundancy**: Backup systems, alternative facilities

**Investment priority**: Environmental detection and rapid response capabilities are high-value defensive investments that work across multiple threat types.

---

## 10. The Cyber-Physical Convergence {#cyber-physical}

### Beyond Synthesis: Attacking Existing Infrastructure

The preceding sections focus on AI assistance for *creating* WMD. A distinct and underappreciated threat vector involves AI agents targeting the *control systems* of facilities that already contain dangerous materials.

**The key insight**: An AI agent doesn't need to help someone build a bioweapon if it can help them disable the containment systems of an existing BSL-4 laboratory.

### Stuxnet as Precedent

The Stuxnet attack (2010) demonstrated that code can cause physical destruction:
- Malware targeted industrial control systems (ICS)
- Caused centrifuges to physically destroy themselves
- Achieved effects normally requiring military action
- Attribution remained ambiguous for years

AI agents could enable similar attacks at lower skill thresholds.

### Vulnerable Infrastructure Categories

| Infrastructure Type | Contents/Risk | Control System Vulnerability |
|--------------------|---------------|------------------------------|
| BSL-3/4 Laboratories | Dangerous pathogens | HVAC, negative pressure systems |
| Chemical Plants | Toxic chemicals | Process controls, safety interlocks |
| Nuclear Facilities | Radioactive materials | Cooling systems, containment |
| Water Treatment | Chemicals, public health | Dosing systems, quality controls |
| Pharmaceutical Manufacturing | Precursor chemicals | Process controls |

### How AI Agents Enable ICS Attacks

**Reconnaissance**:
- Identifying target facilities from public records
- Mapping control system architectures from procurement data
- Analyzing vulnerability disclosures

**Exploitation Development**:
- Synthesizing attack approaches from security research
- Adapting known exploits to specific targets
- Optimizing attack timing and sequences

**Operational Planning**:
- Coordinating cyber and physical elements
- Identifying optimal attack windows
- Planning for detection evasion

### Attack Scenarios

**Scenario: BSL-4 Containment Failure**
- AI agent identifies laboratory control systems
- Develops approach to disable negative pressure
- Coordinates with physical access (insider or break-in)
- Containment failure releases stored pathogens
- No synthesis required - existing materials weaponized

**Scenario: Chemical Plant Sabotage**
- AI agent maps chemical plant process controls
- Identifies conditions that would cause toxic release
- Develops attack causing "accidental" disaster
- Bhopal-scale casualties from industrial sabotage
- Attribution as accident vs. attack is ambiguous

### Defensive Implications

This vector suggests several defensive priorities:

1. **Air-gap critical controls**: Isolation from network-accessible systems
2. **Enhanced ICS security**: Hardening beyond current standards
3. **Facility monitoring**: Detecting reconnaissance and probing
4. **Incident attribution**: Distinguishing accidents from attacks
5. **Redundant safety systems**: Mechanical backups for digital controls

### Governance Gaps in Proliferation Financing

Agentic AI workflows could assist WMD proliferation through sophisticated financial operations. This section analyzes governance gaps that financial monitoring systems should address.

**Why financial monitoring matters for defenders**:
- Precursor acquisition requires funding and transactions
- Current monitoring relies on pattern recognition
- AI-assisted operations could systematically evade current detection thresholds

**Governance gaps in current financial monitoring**:

| Gap | Current State | What AI Enables | Defender Priority |
|-----|---------------|-----------------|-------------------|
| **Shell company opacity** | Beneficial ownership registries incomplete | Automated creation/management of layered entities | International registry harmonization |
| **Threshold fragmentation** | Reporting triggers at fixed amounts | Systematic structuring below thresholds | Behavioral pattern analysis beyond transaction size |
| **Cryptocurrency mixing** | Limited tracing capability | Automated chain-hopping across currencies | Cross-chain analytics investment |
| **Cross-border jurisdiction gaps** | Inconsistent AML enforcement | Routing through weakest-link jurisdictions | International coordination mechanisms |
| **Dual-use ambiguity** | Legitimate vs. illicit use hard to distinguish | Optimized procurement narratives | End-user verification strengthening |

**What financial intelligence should monitor**:

1. **Procurement pattern anomalies**: Unusual combinations of precursors, equipment, expertise acquisition
2. **Entity creation velocity**: Rapid shell company formation correlated with regulated purchases
3. **Geographic arbitrage signals**: Shifting activity to exploit regulatory gaps
4. **Funding source obfuscation**: Complex transaction chains designed to obscure origin
5. **Threshold-adjacent transactions**: Systematic activity just below reporting limits

**Institutional framework references**:
- 2024 US Treasury National Proliferation Financing Risk Assessment
- FATF Recommendations on Proliferation Financing
- UN Security Council Resolution 1540 implementation guidance

**Policy direction for defenders**: Financial monitoring should evolve from rule-based detection (fixed thresholds) to AI-assisted behavioral analysis that can identify sophisticated evasion patterns. This requires:
- Investment in financial intelligence AI capabilities
- International data-sharing agreements
- Coordination between financial and biosecurity monitoring

### AI-Enabled Procurement Obfuscation ("Smurfing at Scale")

**The specific threat** **[E]**: Historically, the hardest part of WMD acquisition has been procurement without triggering law enforcement. AI agents with computer use capabilities fundamentally change the economics of evasion:

| Traditional Procurement | AI-Enabled Procurement |
|------------------------|------------------------|
| Single large order triggers alerts | Thousands of sub-threshold orders from different entities |
| Human labor limits coordination | Agents manage unlimited parallel operations |
| Paper trails connect purchases | Synthesized identities and automated KYC fraud |
| Logistics require human coordination | Gig-economy couriers, dead-drop coordination |
| Supplier relationships take time | Automated vendor discovery and relationship management |

**How agents enable this** **[E]**:
- **Identity synthesis**: Generate plausible business identities with consistent online presence
- **Threshold awareness**: Automatically structure orders below reporting limits across jurisdictions
- **Supplier diversification**: Identify and manage relationships with dozens of suppliers simultaneously
- **Logistics automation**: Coordinate delivery to multiple intermediate locations using on-demand services
- **Timeline compression**: What would take a human months takes an agent hours

**Defender countermeasures**:
1. **Cross-supplier correlation**: Detect when multiple "independent" buyers order complementary materials
2. **Velocity anomalies**: Flag rapid entity creation correlated with regulated purchases
3. **Behavioral biometrics**: Identify automated vs. human interaction patterns with ordering systems
4. **Supplier consortium**: Shared threat intelligence across chemical/biological supply chains

**Actor tier relevance**: This capability particularly benefits T2-T3 actors who previously lacked the human resources for sophisticated operational security.

---

## 11. Counterarguments and Structural Barriers {#counterarguments}

> **Note on Grounding**: The RAND Corporation's 2024 report *"The Operational Risks of AI in Large-Scale Biological Attacks"* argues that current AI risk levels remain relatively low due to persistent physical and tacit knowledge barriers. This section engages seriously with such counterarguments to maintain analytical balance.

### The Tacit Knowledge Argument

**Argument**: Much of WMD development requires tacit knowledge - skills learned through practice that cannot be fully conveyed through text or instruction. AI agents operate in the symbolic/linguistic domain and cannot transfer tacit knowledge.

**Supporting evidence**:
- Aum Shinrikyo had extensive theoretical knowledge but failed at biological weapons
- Chemistry synthesis requires sensory skills (recognizing correct colors, textures)
- Nuclear weapon engineering involves hands-on calibration and testing
- Laboratory work involves countless micro-decisions based on experience

**Our assessment**: This is a valid and important counterargument. Tacit knowledge remains a significant barrier, particularly for nuclear and sophisticated biological weapons. However:

1. AI-guided real-time instruction can partially bridge this gap
2. Cloud laboratories embody tacit knowledge in automated protocols
3. Some attack pathways (crude agents, toxins) require less tacit knowledge
4. Repeated AI-assisted attempts can develop tacit knowledge over time

**Conclusion**: Tacit knowledge is a barrier but not an absolute one, and it is eroding.

### The Physical Bottleneck Argument

**Argument**: AI cannot download hardware. Physical materials and equipment remain controlled, regulated, and scarce. No amount of AI assistance helps if you cannot obtain the materials.

**Evidence by category**:

| Category | Physical Bottleneck | Strength |
|----------|--------------------| ---------|
| Nuclear | Fissile material | Very strong |
| Chemical | Regulated precursors | Moderate |
| Biological | Pathogen access, equipment | Weakening |
| Radiological | Radioactive sources | Moderate |

**Our assessment**: Valid for nuclear weapons. Partially valid for chemical. Increasingly weak for biological as synthesis services expand.

### The Data Scarcity Argument

**Argument**: AI models are trained on internet data. Functional WMD synthesis procedures are not widely published. Models often hallucinate plausible-sounding but incorrect procedures that would fail or harm the operator.

**Evidence**:
- Published synthesis routes often omit critical details
- Safety procedures essential to successful synthesis are often implicit
- Much weapons-relevant information is classified or restricted
- AI models demonstrate chemistry errors in evaluations

**Our assessment**: Partially valid. However:
- More information is available than is commonly assumed
- AI can aggregate fragmented information to reconstruct procedures
- Model capabilities are improving rapidly
- Hallucination rates are decreasing with better models

**Conclusion**: Data scarcity is a barrier but not as robust as often assumed.

### The Operational Security Argument

**Argument**: Serious WMD attempts require extended preparation that creates detection opportunities. Acquiring materials, testing, and deployment all generate signals. This remains true regardless of AI assistance.

**Evidence**:
- Materials purchases can be monitored
- Laboratory activities may be detected
- Testing creates observable signatures
- Deployment requires physical presence

**Our assessment**: This is largely valid and underappreciated. Defensive capabilities can focus on operational signatures rather than trying to restrict information. AI may actually help defense by identifying suspicious patterns.

### The Failure Cascade Argument

**Argument**: WMD development involves multiple steps, each with failure probability. Even if AI improves each step, the compound probability of overall success may remain low.

**Illustration** (hypothetical numbers for concept):
- Step 1 (agent selection): 80% success with AI assistance
- Step 2 (synthesis): 50% success with AI assistance
- Step 3 (weaponization): 30% success with AI assistance
- Step 4 (delivery): 60% success with AI assistance
- Compound probability: 7.2%

**Our assessment**: Valid framework. However:
- Persistent actors can iterate and improve
- Some pathways involve fewer steps
- Crude attacks with lower success rates may still be attempted
- Even failed attempts can cause harm (accidents, psychological impact)

### The Over-Screening Cost Argument (False Positive Perspective)

**Argument**: If AI-driven paranoia leads to excessive screening and restrictions, we may cause more harm than we prevent by stifling legitimate research—including the research needed to respond to natural pandemics.

**Evidence of costs**:
- Post-2001 anthrax regulations significantly slowed legitimate biodefense research
- Dual-use restrictions have delayed vaccine development timelines
- Overly broad export controls can push research to less regulated jurisdictions
- Scientific talent may avoid biosecurity-adjacent fields due to compliance burden

**Quantifying the tradeoff**:
| Over-Screening Risk | Under-Screening Risk |
|---------------------|---------------------|
| Delayed pandemic response capability | Enabled WMD attempt |
| Reduced scientific competitiveness | Attribution challenges |
| Research migration to less regulated regions | Psychological/economic damage |
| Chilling effect on beneficial dual-use research | Potential mass casualties |

**Our assessment**: This is a serious concern that should constrain policy enthusiasm. The goal is *calibrated* security, not maximum restriction. Recommendations in this report should be evaluated against their research-stifling potential.

**Policy implication**: Any screening or restriction regime should include:
- Clear appeal mechanisms
- Regular calibration reviews
- Exemptions for established research institutions
- Sunset provisions requiring reauthorization

### The Asymmetric Defense Argument (AI Favors Defenders)

**Argument**: AI may actually favor defenders more than attackers. The same capabilities that could assist WMD development can dramatically accelerate defensive countermeasures.

**Defensive AI advantages**:

| Capability | Offensive Application | Defensive Application |
|------------|----------------------|----------------------|
| Rapid sequence analysis | Pathogen design | Real-time detection of novel threats |
| Protein structure prediction | Virulence optimization | Vaccine/therapeutic design in days not years |
| Pattern recognition | Evasion planning | Anomaly detection in procurement, lab activity |
| Literature synthesis | Attack planning | Threat anticipation, countermeasure identification |
| Simulation/modeling | Dispersal optimization | Response planning, containment modeling |

**The "Bio-Firewall" concept**: Advanced AI systems could theoretically:
- Sequence a novel pathogen within hours of detection
- Design candidate therapeutics within days
- Optimize manufacturing protocols in parallel
- Guide rapid clinical trials with AI-assisted analysis

**Historical precedent**: COVID-19 vaccine development (under 1 year vs. typical 10+ years) demonstrated that with sufficient resources and urgency, development timelines can compress dramatically. AI acceleration could push this further.

**Our assessment**: This is a valid and important counter-narrative. However:
- Defensive capabilities require *investment* to realize
- Attackers choose timing; defenders must be ready continuously
- A single successful attack could cause damage before defenses activate
- The argument supports *investing in defensive AI*, not complacency

**Policy implication**: Defensive AI capabilities should receive funding priority at least equal to restriction/monitoring efforts.

### Critique of the Unilateralist's Curse Framework

**The Unilateralist's Curse** (Bostrom & Ord) argues that when many actors can independently take an irreversible action, even if most would refrain, the probability of *someone* acting approaches certainty.

**Potential overreach of this framework**:

1. **Assumes homogeneous capability**: Not all actors who "want to" can actually execute. The curse applies most strongly when capability is uniform—but WMD capability remains highly non-uniform.

2. **Ignores coordination mechanisms**: The framework assumes purely independent decision-making. In reality, extremist communities have internal norms, and state sponsors exercise control over proxies.

3. **May induce fatalism**: If misuse is "inevitable," policymakers may:
   - Overinvest in restriction vs. resilience
   - Underinvest in detection and response
   - Adopt maximally restrictive policies regardless of cost

4. **Alternative framing - "The Long Fuse"**: Instead of "inevitable misuse," consider that barriers create *delay*. Each year of delay allows:
   - Defensive technology to advance
   - Governance frameworks to mature
   - Attribution capabilities to improve
   - Social norms against misuse to strengthen

**Our assessment**: The Unilateralist's Curse is a useful heuristic but should not induce fatalism. The appropriate response is *buying time through calibrated barriers* while *investing in resilience and response capabilities*—not assuming catastrophe is inevitable.

---

## 12. The Attribution Problem {#attribution-problem}

### Why Attribution Matters

Attribution - determining who is responsible for an attack - serves critical functions:
1. Enables retaliation and deterrence
2. Provides basis for legal accountability
3. Informs public understanding and policy response
4. Prevents misattribution and escalation

AI agents complicate attribution across all WMD categories.

### How AI Complicates Attribution

**Digital footprint reduction**:
- AI agents can plan without human co-conspirators
- Communications limited to human-AI interactions
- No organizational structure to penetrate
- Planning can occur on personal devices without network traffic

**Physical evidence challenges**:
- Biological agents may not indicate origin point
- Chemical precursor sources may be obscured
- Multiple delivery methods prevent signature analysis
- Gene drives become untraceable after release

**False flag potential**:
- AI can generate misleading evidence
- Forensic-quality fabrications possible
- Attribution to rival actors could provoke conflict
- Uncertainty paralyzes response

### Category-Specific Attribution Challenges

| Category | Traditional Attribution Method | AI-Era Challenge |
|----------|------------------------------|------------------|
| Nuclear | Isotopic signatures; intelligence | Material signatures remain; planning harder to track |
| Chemical | Precursor tracing; synthesis signatures | Alternative routes obscure sourcing |
| Biological | Genetic analysis; strain matching | Synthetic or modified strains lack natural history |
| Gene drive | Ongoing research | Origin essentially untraceable after establishment |

### Attribution Matrix: Traditional vs. AI-Era Forensics

**For defenders and investigators**: Understanding how AI changes the attribution landscape.

| Evidence Type | Traditional Approach | AI-Era Signatures | Defender Investment |
|--------------|---------------------|-------------------|---------------------|
| **Physical materials** | Isotope ratios, impurity profiles, manufacturing markers | Remains relevant for nuclear/radiological; less useful for synthetic biology | Maintain existing forensic capabilities |
| **Genetic sequences** | Strain matching to known repositories, phylogenetic analysis | Synthetic sequences may lack natural evolutionary history; designed variants may be novel | Develop synthetic biology forensics; database of designed sequences |
| **Precursor tracing** | Purchase records, chemical signatures | Alternative synthesis routes; fragmented procurement | AI-assisted pattern analysis across transactions |
| **Communication intercepts** | Organizational communications, planning documents | Human-AI interactions; local computation; minimal network traffic | Endpoint monitoring; behavioral analysis |
| **Human intelligence** | Infiltration, informants, defectors | Smaller networks; less human coordination needed | Maintain HUMINT despite reduced target richness |
| **Digital forensics** | Device analysis, network logs, browser history | AI query logs; model interactions; prompt history | Develop AI-specific forensic capabilities |
| **Financial trails** | Bank records, transaction patterns | Cryptocurrency; shell companies; threshold evasion | Blockchain analysis; behavioral pattern detection |

**New AI-era attribution opportunities**:

1. **AI query analysis**: Patterns in how AI systems are queried may indicate intent
2. **Compute fingerprinting**: High-capability model use may leave compute signatures
3. **Synthetic biology signatures**: Designed sequences may have identifiable "authorship" patterns
4. **Procurement pattern analysis**: AI-assisted detection of unusual material acquisition
5. **Behavioral biometrics**: Interaction patterns with AI systems may be identifiable

**Investment priorities for attribution capability**:
- AI forensics training for investigators
- International sharing agreements for AI-relevant evidence
- Research into synthetic biology authorship attribution
- Integration of financial and biosecurity intelligence

### Geopolitical Implications

The attribution void has severe geopolitical implications:

**Scenario**: A biological attack occurs. Intelligence cannot determine whether the perpetrator was:
- A lone actor with AI assistance
- A non-state extremist group
- A state actor using deniable means
- A false flag by a third party

**Consequences**:
- Retaliation against the wrong party risks escalation
- No retaliation emboldens future attackers
- Public pressure for action conflicts with evidentiary requirements
- Alliance commitments become difficult to invoke

### Defensive Implications

Attribution challenges suggest defensive strategy shifts:

1. **Prevention over punishment**: Cannot rely on deterrence through retaliation
2. **Resilience over defense**: Assume some attacks will succeed; focus on limiting damage
3. **Detection over access control**: Monitor for activity patterns rather than restricting information
4. **International cooperation**: Attribution often requires shared intelligence
5. **Pre-incident intelligence capacity**: Invest in human intelligence, signals intelligence, and international investigative partnerships that can develop leads before attacks occur - not just forensic analysis after

**Organizational priority**: International investigative capacity is an organizational investment, not primarily a technical one. Treaty-level agreements on information sharing, joint investigation protocols, and mutual legal assistance are as important as forensic technology.

---

## 13. International Variance {#international-variance}

### Regulatory Landscape

WMD-related AI risks vary significantly across jurisdictions:

**Restrictive jurisdictions** (US, EU, UK, Australia):
- Frontier AI models have usage restrictions
- Biosecurity regulations cover synthesis services
- Export controls on dual-use equipment
- Institutional review requirements

**Permissive jurisdictions**:
- Less restricted AI model availability
- Limited biosecurity oversight
- Weaker export controls
- "Data havens" for unrestricted AI services

### Regulatory Arbitrage and Global South Considerations

A critical dynamic: security measures in restrictive jurisdictions can be circumvented by operating from permissive ones. This "regulatory arbitrage" may render Western guardrails partially moot.

**The arbitrage pathway**:

| Resource | Restrictive Jurisdiction | Arbitrage Opportunity |
|----------|-------------------------|----------------------|
| AI model access | Closed API with monitoring | Open-weight hosting in unregulated jurisdiction |
| DNA synthesis | IGSC screening required | Non-IGSC providers elsewhere |
| Cloud laboratory | Institutional oversight | Commercial services with minimal verification |
| Compute rental | KYC requirements | Anonymous cryptocurrency payment options |
| Research collaboration | Institutional ethics review | Informal networks bypassing oversight |

**Global South specific considerations**:

1. **Capacity vs. governance mismatch**: Some regions are developing synthetic biology capacity faster than biosecurity governance frameworks
2. **Brain drain inversion**: AI enables remote collaboration, potentially routing expertise to less-regulated contexts
3. **Economic incentives**: Commercial DNA synthesis and cloud lab services may prioritize revenue over screening rigor
4. **Dual-use development framing**: Legitimate agricultural or public health programs may provide cover for concerning activities
5. **Sovereignty sensitivities**: International oversight proposals may face resistance as neo-colonial imposition

**Why Western guardrails may be insufficient**:
- Actors can access AI services via VPN to unrestricted jurisdictions
- DNA synthesis orders can be routed through intermediaries
- Financial transactions can use unregulated cryptocurrency infrastructure
- Enforcement requires international cooperation that may not exist

**What this means for policy**:
- Unilateral restrictions have limited effectiveness
- Capacity building and norm promotion may be more effective than prohibition
- Detection and response capabilities matter more than access denial
- International coordination is essential but difficult

**Implications**:
- Domestic regulations have limited effect without international coordination
- "Jurisdiction shopping" enables capability acquisition
- Defensive strategies should assume some barrier circumvention will occur

### State Actor Considerations

For state-level proliferation, AI offers different dynamics:

**State programs may benefit from AI**:
- Faster weapon development timelines
- Reduced personnel requirements (operational security)
- Novel agent development acceleration
- Supply chain optimization to evade detection

**This affects**:
- Emerging nuclear programs
- Reconstituted bioweapons programs
- Chemical weapons in conflict zones
- Dual-use research that crosses lines

### Treaty Implications

Existing arms control frameworks face new challenges:

**Biological Weapons Convention (BWC)**:
- Lacks verification mechanisms
- AI-enabled development may be undetectable
- Dual-use research complicates compliance assessment

**Chemical Weapons Convention (CWC)**:
- Precursor controls challenged by alternative routes
- Verification depends on declared facilities
- Novel agents may fall outside scheduled lists

**Nuclear Non-Proliferation Treaty (NPT)**:
- Physical barriers remain strong
- AI assistance to aspiring states is concern
- Verification mechanisms relatively robust

**No framework addresses**:
- Gene drives specifically
- AI-enabled WMD development
- Attribution in the AI era

---

## 14. Second-Order Effects {#second-order-effects}

### The Fear Effect and Overreaction

The *perception* of AI-enabled WMD risk may cause harmful responses even without actual attacks:

**Potential overreactions**:
- Excessive restrictions on legitimate research
- Surveillance expansion beyond justified scope
- Suppression of dual-use scientific publication
- Chilling effects on beneficial synthetic biology

**Historical parallel**: The 2001 anthrax attacks caused:
- $1 billion+ in cleanup costs
- Disruption to mail systems
- New biosecurity regulations
- Psychological impact far exceeding casualties

A *credible threat* of AI-enabled bioweapons could trigger similar dynamics at larger scale.

### Research Stifling

AI WMD concerns could lead to restrictions that harm beneficial research:

**At risk**:
- Cancer research using synthetic biology tools
- Pandemic preparedness research
- Agricultural improvements through genetic engineering
- Environmental applications of gene drives

**The balance problem**:
- Same tools enable both beneficial and harmful applications
- Restrictions that prevent misuse also prevent legitimate use
- Risk tolerance calibration is contentious
- International competition incentivizes continued research

### Acceleration of State Programs

Paradoxically, fear of AI-enabled non-state threats could accelerate state WMD programs:

**Logic chain**:
1. States perceive non-state WMD threat increasing
2. States invest in WMD defense capabilities
3. Defense capabilities overlap with offense
4. Net effect: more WMD capability globally

**Additionally**:
- States may cite AI risks to justify programs
- Verification becomes more difficult
- Arms control regimes may weaken

### Public Health Infrastructure

WMD concerns affect public health systems:

**Positive effects**:
- Investment in detection capabilities
- Improved medical countermeasure development
- Better surveillance systems

**Negative effects**:
- Securitization of public health
- Reduced information sharing
- Distrust between health and security communities

---

## 15. Policy Recommendations by Stakeholder Type {#policy-recommendations}

### For Policy Makers

| Priority | Action | Type | Implementation Mechanism | Key Challenge |
|----------|--------|------|-------------------------|---------------|
| Critical | **Mandate universal DNA synthesis screening** | Unilateral / Coordination | Extend IGSC guidelines to law; require provider registration | Coverage gaps, cross-border substitution |
| Critical | **International AI safety standards for WMD capabilities** | Coordination | Treaty negotiation, export control coordination | Geopolitical competition, verification |
| Critical | **Invest in attribution capabilities** | Unilateral | HUMINT/SIGINT funding, forensic lab capacity | Long timelines |
| High | **Cloud laboratory oversight** | Unilateral / Coordination | Audit requirements, protocol classification, customer KYC | Privacy concerns, research friction |
| High | **Update treaty frameworks** | Coordination | BWC verification protocol, CWC schedule updates | Consensus challenges |
| High | **Defensive biodetection research** | Unilateral | BARDA/DARPA funding, academic partnerships | Technology maturation |
| Medium | **Red team evaluation requirements** | Unilateral | Pre-deployment safety standards, independent assessment | Defining thresholds |
| Medium | **International attribution sharing** | Coordination | Mutual legal assistance treaties, joint investigation | Sovereignty concerns |

**Legend**: Unilateral = Domestically implementable without international agreement | Coordination = Requires international coordination

**Key insight for policymakers**: The window for establishing governance frameworks is narrow. Once capabilities proliferate, restrictions become much harder to implement.

**Advanced Defensive Measures** (more speculative, significant challenges):

| Measure | Description | Challenge/Controversy |
|---------|-------------|----------------------|
| **KYC for Compute** | Verification for large-scale computing rentals | Privacy, open research norms, threshold definition, appeal mechanisms |
| **Honey-Pot Data Injection** | Seed datasets with subtle errors in dangerous procedures | Scientific integrity concerns, collateral damage to legitimate research, ethical objections |
| **Information Hazards Management** | Restrict publication of AI red team failure modes | Research community pushback, definitional challenges, effectiveness uncertain |

*Note: These advanced measures are presented for consideration, not endorsement. Each involves significant tradeoffs that require careful deliberation.*

### Implementation Feasibility Assessment

| Recommendation | Owner | Timeline | Cost Class | Friction Risk | Expected Risk Reduction |
|----------------|-------|----------|------------|---------------|------------------------|
| **DNA synthesis screening mandate** | National legislators + IGSC | 0-12 months (domestic) / 12-36 months (international) | Low-Medium | Medium (enforcement variation) | High - chokepoint control |
| **International AI safety standards** | Treaty bodies (UN, G7) | 36-60+ months | Medium | High (geopolitical) | Medium - assumes compliance |
| **Attribution capability investment** | Intelligence agencies | 12-36 months (initial) / ongoing | High | Low | Medium - deters some actors |
| **Cloud laboratory oversight** | Regulators + industry | 12-24 months | Low | Medium (research friction) | Medium-High - chokepoint |
| **Treaty framework updates (BWC/CWC)** | State parties | 36-60+ months | Low | Very High (consensus) | Low-Medium - verification weak |
| **Defensive biodetection R&D** | BARDA/DARPA/equivalents | 12-36 months (deployment) | High | Low | High - enables response |
| **Red team evaluation requirements** | AI regulators | 12-24 months | Medium | Medium (competitive) | Medium - depends on thresholds |

**Minimal Viable Steps (12-month horizon)**:
1. Expand IGSC membership and mandate sequence screening
2. Establish cloud lab provider working group on security standards
3. Fund initial biodetection deployment pilots
4. Require WMD capability evaluations for frontier AI releases

---

### For CEOs and Corporate Leadership

| Priority | Action | Rationale |
|----------|--------|-----------|
| Critical | **Implement robust screening in AI-biology interfaces** | If you operate AI services used for biological research, you are on the front line |
| Critical | **Red team AI products for WMD uplift** | Understand what your systems enable; third-party evaluation preferred |
| High | **Establish clear escalation procedures for concerning queries** | Staff need guidance when dangerous requests are detected |
| High | **Engage with policymakers on technical feasibility** | Industry expertise needed for workable regulations |
| High | **Invest in defensive applications** | AI-enabled biosurveillance, detection, response |
| Medium | **Evaluate supply chain security** | Ensure your products/services aren't diverted to harmful purposes |
| Medium | **Develop industry standards collaboratively** | Self-regulation can preempt less informed government regulation |

**Key insight for CEOs**: The AI-biology interface is a major liability exposure. Companies operating in this space face both safety responsibilities and reputational risk.

---

### For Tech Elite (AI Developers, Founders, Investors)

| Priority | Action | Rationale |
|----------|--------|-----------|
| Critical | **Evaluate models for WMD uplift before release** | You cannot claim ignorance after deployment |
| Critical | **Do not open-source models with significant uplift capabilities** | Once released, cannot be recalled |
| Critical | **Implement robust guardrails with ongoing monitoring** | Initial safeguards degrade; adversarial adaptation is ongoing |
| High | **Fund defensive biosecurity research** | The same capabilities that enable offense can enable defense |
| High | **Engage seriously with safety evaluations** | Red team findings should inform development, not just PR |
| High | **Participate in international governance discussions** | Technical expertise essential for workable frameworks |
| Medium | **Develop "know your customer" standards for API access** | High-capability access should have accountability |
| Medium | **Support attribution research** | AI forensics benefit from AI expertise |

**Key insight for tech elite**: You are building dual-use capabilities. The ethical responsibility is substantial, and the historical legacy of these decisions will be judged harshly if preventable harm occurs.

---

### For Laypeople (General Public)

| Priority | Action | Rationale |
|----------|--------|-----------|
| High | **Support evidence-based policy** | Neither panic nor dismissal serves public interest |
| High | **Understand info-hazard dynamics** | Sharing jailbreaks or dangerous prompts, even casually, contributes to the problem |
| Medium | **Engage with governance processes** | Public input shapes policy; democratic accountability matters |
| Medium | **Maintain perspective** | Actual WMD attacks remain rare; psychological impact of threat may exceed actual risk |
| Medium | **Support research freedom within appropriate bounds** | Avoid reflexive restriction of beneficial science |
| Lower | **Personal preparedness** | Basic emergency preparedness serves multiple threats |

**Key insight for laypeople**: The most important role is as informed citizens. Governance decisions being made now will shape this landscape for decades. Engagement in democratic processes matters.

---

## 16. Uncertainties and Alternative Scenarios {#uncertainties}

### Key Uncertainties

1. **AI capability trajectory**: Development could be faster or slower than projected
2. **Defensive capability development**: Detection and attribution may improve substantially
3. **Attack frequency**: Capability does not automatically translate to attacks
4. **Governance effectiveness**: International coordination is unpredictable
5. **Tacit knowledge erosion**: Unclear how quickly AI-lab integration bridges this gap

### Scenario Analysis

> **Probability Calibration Note**
>
> The probabilities below are *subjective priors* intended to support decision-making under uncertainty. They are not empirical estimates derived from statistical models.
>
> **Methodology**: Informal expert elicitation drawing on:
> - Reference-class forecasting (historical rate of technology diffusion, non-state adoption of dangerous capabilities)
> - Decomposition model (capability access x intent x operational execution x detection avoidance)
> - Adjustment for AI-specific factors (barrier reduction analysis from preceding sections)
>
> **Interpretation guidance**: Use for relative prioritization between scenarios, not as point predictions. Reasonable analysts could assign significantly different values. The conditional probability table (below) is intended to illustrate how governance choices shift the distribution.

### Probability Decomposition Framework

**Risk = Capability Access × Intent Prevalence × Operational Execution × (1 − Interdiction) × Impact Scale**

The following illustrative decomposition shows how these factors combine. Values are rough ranges to demonstrate the model, not precise estimates.

#### Biological (Highest Risk Category)

| Factor | 2025 Estimate | 2030 Projection | AI Contribution |
|--------|---------------|-----------------|-----------------|
| **Capability Access** (T2+ can attempt) | 5-10% of T2+ | 15-25% of T2+ | High - knowledge synthesis, protocol optimization |
| **Intent Prevalence** (among capable) | ~0.1-1% | ~0.1-1% | Low - AI doesn't create intent |
| **Operational Execution** (attempt→working agent) | 5-15% | 10-25% | Medium - guidance improves, tacit gap narrows |
| **Interdiction Avoidance** (evade detection) | 60-80% | 50-70% | Medium - AI assists OPSEC, but defenders also use AI |
| **Impact Scale** (casualties per success) | Wide range | Wide range | Low - physics/biology constrain |

**Compound probability of mass-casualty bio attack by 2030**: Illustrative calculation
- (0.20 capable) × (0.005 intent) × (0.15 execution) × (0.65 evasion) ≈ 0.0001 per actor-year
- With ~1000 actors in T2+ pool annually × 5 years = ~0.5% cumulative
- *This is consistent with Scenario D (8-12%) given uncertainty ranges*

#### Chemical (Moderate Risk)

| Factor | 2025 Estimate | 2030 Projection | AI Contribution |
|--------|---------------|-----------------|-----------------|
| **Capability Access** | 10-20% of T2+ | 15-30% of T2+ | Low - precursor controls dominate |
| **Intent Prevalence** | ~0.1-1% | ~0.1-1% | Low |
| **Operational Execution** | 10-20% | 15-25% | Medium - synthesis guidance |
| **Interdiction Avoidance** | 50-70% | 40-60% | Low - procurement monitoring improving |
| **Impact Scale** | Moderate | Moderate | Low |

#### Nuclear (Lowest AI-Related Risk)

| Factor | 2025 Estimate | 2030 Projection | AI Contribution |
|--------|---------------|-----------------|-----------------|
| **Capability Access** | <1% of T3+ | <1% of T3+ | Very low - fissile material barrier |
| **Intent Prevalence** | ~0.1% | ~0.1% | None |
| **Operational Execution** | <5% | <5% | Low - engineering barriers dominate |
| **Interdiction Avoidance** | 20-40% | 20-40% | Low - material is detectable |
| **Impact Scale** | Catastrophic | Catastrophic | None |

*Note: These decompositions are illustrative. Actual intelligence assessments would use classified threat data and more rigorous methodology. The purpose is to show how the model works, not to provide precise predictions.*

### Sensitivity Analysis: What Moves the Numbers?

To prevent false precision, this table shows how Scenario D (Mass Casualty Success) probability shifts under different assumptions:

| Parameter Varied | Low Assumption | Base Case | High Assumption | Scenario D Range |
|-----------------|----------------|-----------|-----------------|------------------|
| **Intent prevalence** | 0.05% (rare) | 0.5% | 2% (elevated) | 3% → 8-12% → 25% |
| **Execution success** | 5% (barriers hold) | 15% | 30% (rapid erosion) | 4% → 8-12% → 20% |
| **Interdiction rate** | 50% (strong defense) | 35% | 20% (weak coordination) | 5% → 8-12% → 18% |
| **Capable actor pool** | 500 T2+ globally | 1000 | 2000 (AI lowers entry) | 4% → 8-12% → 22% |

**Key insight**: The estimate is most sensitive to **intent prevalence** and **capable actor pool size** - factors where AI's contribution is indirect (lowering barriers for those already motivated). If you believe AI will *create* new motivated actors (not just enable existing ones), shift estimates higher.

**What would falsify this model**:
- AI-enabled attack by T0-T1 actor (would indicate barriers lower than assessed)
- Successful interdiction of AI-assisted attempt (would indicate detection working)
- Stable or declining synthesis screening intercepts (would indicate threat not materializing)

---

**Scenario A: Effective Governance (10-15% probability)**

Strong international coordination establishes:
- Universal DNA synthesis screening
- Cloud laboratory oversight
- AI model restrictions for high-risk capabilities
- Effective attribution mechanisms

Outcome: AI-related WMD risks remain theoretical; barriers remain largely intact.

*Probability rationale*: Given current geopolitical fragmentation (US-China tensions, EU-US divergence on AI regulation), globally coordinated effective governance is unlikely in the near term.

**Scenario B: Muddling Through (35-40% probability)**

Partial measures implemented:
- Some synthesis screening improvements
- Patchwork national regulations
- Continued dual-use research
- Occasional concerning incidents but no mass casualties

Outcome: Baseline risk increases moderately; several failed or limited attacks; gradual tightening of controls.

**Scenario C: High-Frequency Attempts, Limited Success (25-30% probability)**

**Critical distinction**: We now separate *attempts* from *successful mass casualty attacks*.

Many AI-assisted WMD attempts occur:
- Mostly crude, partially successful, or failed
- Few to dozens of casualties per incident
- Significant psychological and political impact
- Attribution challenges paralyze response

Outcome: "Noise floor" of WMD attempts increases dramatically; security resources strained; public fear elevated despite limited actual casualties.

**Scenario D: Successful Mass Casualty Attack (8-12% probability)**

A non-state actor successfully executes a WMD attack with significant AI assistance achieving mass casualties:
- Likely biological given barrier analysis
- Casualties in thousands+
- Attribution difficult or impossible
- Massive policy response

Outcome: Severe restrictions on AI and biological research; potential civil liberties overreach; damaged international cooperation.

**Scenario E: State Program Acceleration (15% probability)**

Multiple states use AI to accelerate WMD programs:
- Faster nuclear proliferation
- Reconstituted bioweapons programs
- New chemical weapon development
- Regional arms races

Outcome: Increased state-level WMD capabilities; weakened arms control; elevated global risk.

**Scenario F: Catastrophic Attack (3-5% probability)**

A sophisticated attack achieves civilization-scale casualties (tens of thousands to millions):
- Engineered pandemic pathogen
- Or: novel agent evading countermeasures
- Global health emergency
- Civilization-level disruption

Outcome: Fundamental restructuring of AI governance; potential technology restrictions; lasting global impact.

### Conditional Probabilities

| Scenario | Given Strong Governance | Given Weak Governance |
|----------|-------------------------|----------------------|
| A (Effective Governance) | 25% | 5% |
| B (Muddling Through) | 40% | 30% |
| C (High-Frequency Attempts) | 20% | 35% |
| D (Mass Casualty Success) | 5% | 15% |
| E (State Acceleration) | 8% | 20% |
| F (Catastrophic) | 2% | 8% |

**Interpretation**: Governance choices significantly affect outcome distribution. This supports prioritizing governance investment now.

**Key insight from Scenario C**: The "noise floor" of attempts may be the most likely outcome. Security services should prepare for resource strain from high-frequency low-sophistication incidents, not just rare catastrophic events.

---

## 17. Signals and Early Indicators {#signals}

### Leading Indicators to Monitor

#### Capability Indicators

| Indicator | Data Sources | What It Signals |
|-----------|--------------|-----------------|
| AI model performance on biology benchmarks | Academic publications, model evaluations | Uplift capability maturation |
| Cloud laboratory service expansion | Industry announcements, market analysis | Attack surface growth |
| DNA synthesis price/capability curves | Industry data | Accessibility threshold changes |
| Gene drive research publications | Scientific literature | Dual-use capability development |
| AI-lab integration products | Commercial announcements | Tacit knowledge bridging |

#### Threat Activity Indicators

| Indicator | Data Sources | What It Signals |
|-----------|--------------|-----------------|
| Screening intercepts at synthesis providers | Law enforcement, industry disclosure | Attempted acquisition patterns |
| Dark web discussion of AI+WMD | Open source intelligence | Actor interest and capability claims |
| Concerning queries to AI systems | Platform reports, safety research | Demand signal for harmful information |
| Failed or thwarted attack attempts | Law enforcement, media | Threat translation from capability |

#### Governance Indicators

| Indicator | Data Sources | What It Signals |
|-----------|--------------|-----------------|
| International agreement progress | Treaty negotiations, diplomatic statements | Coordination capacity |
| National regulation development | Legislative tracking | Domestic control framework |
| Industry self-regulation | Corporate announcements, standards bodies | Private sector response |
| AI safety research investment | Funding announcements, publications | Defensive capability development |

### Machine-Readable Indicators for Automated Monitoring

**For security operations centers and automated threat intelligence systems**: The following indicators can be operationalized for machine-readable monitoring.

#### API Query Pattern Indicators

| Pattern | Detection Method | Alert Threshold | False Positive Mitigation |
|---------|-----------------|-----------------|---------------------------|
| Sequential queries on pathogen biology + synthesis + aerosolization | Query log analysis, semantic clustering | >3 related queries in session | Exclude academic/research IPs; require context review |
| Iterative refinement of synthesis protocols | Query similarity scoring | >5 refinement iterations | Check for institutional affiliation |
| Multi-model coordination (planning + chemistry + biology) | Cross-platform correlation | Coordinated queries across models | Verify legitimate research workflows |
| Jailbreak attempt patterns | Known prompt pattern matching | Match to known adversarial patterns | Update patterns; human review |

#### Procurement Pattern Indicators

| Pattern | Detection Method | Alert Threshold | Data Source |
|---------|-----------------|-----------------|-------------|
| Precursor combination anomalies | Graph analysis of co-purchases | Unusual combinations flagged | Supplier transaction data |
| Threshold-adjacent transactions | Statistical analysis of transaction sizes | Systematic <threshold purchases | Financial intelligence |
| Geographic dispersion of orders | Shipping address clustering | Single recipient, multiple addresses | Logistics data |
| Dual-use equipment + biological supplies | Purchase correlation analysis | Equipment + consumables combination | Cross-supplier aggregation |

#### Compute and Model Usage Indicators

| Pattern | Detection Method | Alert Threshold | Context |
|---------|-----------------|-----------------|---------|
| Large-scale biological simulation compute | Resource allocation monitoring | >threshold GPU-hours on bio tasks | Cloud provider logs |
| Fine-tuning on scraped biology datasets | Training job classification | Biology-domain fine-tune detected | Model training platforms |
| Open-weight model hosting for biology | Model deployment monitoring | High-capability bio model served | Infrastructure providers |

#### Integration Guidance

- **STIX/TAXII compatibility**: Indicators should be formatted for standard threat intelligence sharing
- **MITRE ATT&CK mapping**: Where applicable, map to relevant techniques
- **Confidence scoring**: Assign confidence levels to reduce alert fatigue
- **Human-in-the-loop**: All high-priority alerts require human review before action

### Red Lines and Trigger Points

Events that would significantly alter assessment:

1. **Confirmed AI-assisted WMD attempt** (any category): Would validate threat model and accelerate responses
2. **Release of unrestricted "research agent"** with biology capabilities: Would dramatically lower barriers
3. **Cloud laboratory security breach** involving dangerous protocols: Would demonstrate attack pathway viability
4. **Gene drive release** (malicious or accidental with harmful effects): Would demonstrate irreversibility concerns
5. **Treaty framework collapse**: Would remove coordination mechanisms

---

## 18. Civil Liberties and Research Freedom Considerations {#civil-liberties}

### The Dual-Use Dilemma

WMD concerns create pressure for restrictions that affect legitimate activities:

**Research freedom impacts**:
- Gain-of-function research restrictions
- Publication censorship of dual-use findings
- International collaboration limitations
- Student/researcher screening

**Civil liberties impacts**:
- Surveillance of scientific communications
- Monitoring of AI queries about biology/chemistry
- Restrictions on information access
- Profiling based on research interests

### Principles for Proportionate Response

1. **Necessity**: Restrictions must address genuine threats, not theoretical possibilities
2. **Proportionality**: Burdens must match actual risk reduction achieved
3. **Minimization**: Use least restrictive effective approach
4. **Accountability**: Clear oversight of any surveillance or restriction powers
5. **Reversibility**: Sunset provisions; regular review

### Guardrails Against Overreach

| Measure | Purpose |
|---------|---------|
| Independent oversight boards | Prevent mission creep |
| Clear evidentiary standards | Avoid profiling without basis |
| Transparency reports | Public accountability |
| Appeal mechanisms | Individual recourse |
| International consistency | Prevent arbitrary variation |

### What Should NOT Happen

| Overreach Risk | Why It's Problematic |
|---------------|---------------------|
| Broad surveillance of scientists | Chilling effect on legitimate research |
| Publication prior restraint | Damages scientific progress |
| AI query monitoring without cause | Privacy violation; creates insecurity |
| Country-of-origin discrimination | Undermines scientific cooperation |
| Classification of dual-use by default | Makes beneficial work impossible |

### The Optimization Target

The goal is not to prevent all possible harm - that would require unacceptable restrictions. The goal is to:

1. Make catastrophic harm significantly harder
2. Enable detection and response to attempts
3. Maintain beneficial research and application
4. Preserve civil liberties and research freedom
5. Adapt as capabilities and threats evolve

---

## 19. Conclusion {#conclusion}

### Summary of Findings

AI agents represent a significant shift in the WMD proliferation landscape, but the nature and magnitude of risk varies substantially across weapon categories:

**Biological weapons** face the most significant barrier reduction. The combination of AI-enabled knowledge synthesis, expanding DNA synthesis services, and cloud laboratory access creates a pathway that erodes multiple traditional barriers simultaneously. This is the highest-priority concern.

**Chemical weapons** face moderate barrier reduction. AI can assist with precursor identification and synthesis guidance, but physical materials access and the technical challenges of safe production remain significant constraints.

**Nuclear weapons** face limited AI-related barrier reduction. Fissile material scarcity remains the dominant constraint, which AI cannot address. Information aggregation represents a secondary concern for state programs.

**Gene drives** represent a novel category requiring dedicated attention. AI specifically accelerates the computational aspects of gene drive design, and the lack of existing governance frameworks creates vulnerability.

**Deployment vectors** (aerosol systems, autonomous delivery) may amplify the impact of even crude agents and warrant attention independent of synthesis capabilities.

### The Central Tension

This analysis identifies a fundamental tension:

- **Access denial is failing**: Information proliferates; dual-use tools expand; international coordination is imperfect
- **Physical barriers persist but erode**: Particularly for biological, the most concerning category
- **Governance lags capability**: International frameworks designed for different eras

The window for establishing effective governance is narrowing. Once capabilities fully proliferate, controls become much harder to implement.

### Call to Action

1. **Prioritize biological**: Among WMD categories, biological faces the most significant AI-related risk increase. Focus resources accordingly.

2. **Invest in governance now**: The next 2-3 years are critical for establishing frameworks before capabilities fully proliferate.

3. **Balance security and research**: Overly restrictive responses will harm beneficial applications without preventing determined adversaries.

4. **Develop defensive capabilities**: Detection, attribution, and response capabilities deserve at least as much investment as restriction efforts.

5. **Maintain perspective**: Actual WMD attacks remain rare. Avoid policy made in fear that causes more harm than the threat itself.

### A Note on Uncertainty

These projections represent our best assessment given available information. Significant uncertainties remain:

- AI capability development pace
- Effectiveness of governance measures
- Translation of capability to actual attacks
- Defensive technology development

The purpose of this analysis is not prediction but preparation. By understanding possible futures, we improve our ability to shape better outcomes.

---

## Appendix A: Risk Prioritization Matrix

| Weapon Category | AI Barrier Reduction | Physical Barriers | Detection Difficulty | Overall Risk Trend |
|----------------|---------------------|-------------------|---------------------|-------------------|
| **Biological** | High | Weakening | High | Significantly Increasing |
| **Chemical** | Moderate | Moderate | Medium | Moderately Increasing |
| **Nuclear** | Low | Very Strong | Low | Stable |
| **Radiological** | Low-Moderate | Moderate | Low | Slightly Increasing |
| **Gene Drives** | High | Low | Very High | Significantly Increasing |

## Appendix B: Key Literature and References

### Biosecurity and Dual-Use Research
- National Academies. *Biodefense in the Age of Synthetic Biology* (2018)
- Koblentz, Gregory. *Living Weapons: Biological Warfare and International Security* (2009)
- Tucker, Jonathan. *Innovation, Dual Use, and Security* (2012)

### Historical Case Studies
- Olson, Kyle. "Aum Shinrikyo: Once and Future Threat?" *Emerging Infectious Diseases* (1999)
- Carus, W. Seth. *Bioterrorism and Biocrimes: The Illicit Use of Biological Agents Since 1900* (2001)
- Meselson, Matthew et al. "The Sverdlovsk Anthrax Outbreak of 1979" *Science* (1994)

### AI Safety and Capability Assessment
- NIST AI Risk Management Framework (2023)
- Anthropic, OpenAI, DeepMind policy papers on dangerous capabilities
- Soice, Emily et al. "Can Large Language Models Democratize Access to Dual-Use Biotechnology?" (2023)

### Arms Control and Nonproliferation
- Zilinskas, Raymond. *Biological Warfare: Modern Offense and Defense* (2000)
- Wheelis, Mark et al. *Deadly Cultures: Biological Weapons Since 1945* (2006)
- Graham Allison. *Nuclear Terrorism: The Ultimate Preventable Catastrophe* (2004)

### Gene Drives
- National Academies. *Gene Drives on the Horizon* (2016)
- Esvelt, Kevin. "Gene Drives and CRISPR Could Revolutionize Ecosystem Management" (2014)

## Appendix C: Glossary

**Biosafety Level (BSL)**: Classification of laboratory containment from BSL-1 (basic) to BSL-4 (maximum containment for most dangerous pathogens)

**Cloud Laboratory**: Commercial service providing remote access to automated laboratory equipment

**CRISPR**: Clustered Regularly Interspaced Short Palindromic Repeats - a gene editing technology

**Dual-Use Research of Concern (DURC)**: Research that could be directly misused to threaten public health, agriculture, environment, or security

**Fissile Material**: Material capable of sustaining nuclear fission chain reaction (highly enriched uranium, plutonium)

**Gain-of-Function Research**: Research that increases pathogen transmissibility, virulence, or host range

**Gene Drive**: Genetic system designed to spread modifications through populations faster than normal inheritance

**Select Agent**: Pathogen or toxin with potential for severe threat to public health, regulated by CDC/USDA

**Tacit Knowledge**: Skills and knowledge that cannot be easily transferred through writing or verbal instruction

**Uplift**: The degree to which AI assistance improves a non-expert's ability to accomplish a task

**Agentic Workflow**: A multi-step AI system where models autonomously plan, execute tools, and iterate toward goals with minimal human oversight per action.

**Vision-Language Model (VLM)**: An AI model capable of processing both visual and textual information, enabling interpretation of images and video.

## Appendix D: Defense Investment Priority Map

> **For resource allocation decisions**: Where should defensive investments be prioritized based on AI uplift analysis?

### Investment Priority by WMD Lifecycle Stage

The following maps defensive investment priorities against the stages where AI provides the most significant capability uplift to adversaries.

```
WMD LIFECYCLE STAGES AND AI UPLIFT

                        AI Uplift Level
Stage                   [Low -------- High]     Defender Priority
─────────────────────────────────────────────────────────────────
1. PLANNING/RESEARCH    ████████████████████    HIGH
   - Literature synthesis   ████████████████████
   - Target selection       ██████████████░░░░░░
   - Capability assessment  ████████████████░░░░

2. ACQUISITION          ██████████░░░░░░░░░░    MEDIUM
   - Precursor sourcing     ████████████░░░░░░░░
   - Financial operations   ██████████████░░░░░░
   - Equipment procurement  ████████░░░░░░░░░░░░

3. SYNTHESIS/PRODUCTION ████████████░░░░░░░░    MEDIUM-HIGH
   - Protocol optimization  ████████████████░░░░
   - Real-time guidance     ██████████████░░░░░░
   - Troubleshooting        ████████████░░░░░░░░

4. WEAPONIZATION        ████████░░░░░░░░░░░░    MEDIUM
   - Delivery design        ████████████░░░░░░░░
   - Dispersal optimization ██████████░░░░░░░░░░
   - Stabilization          ██████░░░░░░░░░░░░░░

5. DEPLOYMENT           ████████████░░░░░░░░    MEDIUM-HIGH
   - Target optimization    ██████████████░░░░░░
   - Timing/logistics       ████████████░░░░░░░░
   - Autonomous delivery    ████████░░░░░░░░░░░░

Legend: █ = AI uplift level; ░ = gap
```

### Recommended Investment Allocation

| Investment Area | Priority | Rationale | Estimated Impact |
|-----------------|----------|-----------|------------------|
| **AI-assisted threat detection** | Critical | Counter the planning/research uplift with defensive AI | High - detects early-stage activity |
| **Synthesis screening enhancement** | Critical | Physical chokepoint where intervention is most feasible | High - blocks acquisition |
| **Environmental biodetection** | High | Essential for response to deployment stage | High - enables rapid response |
| **Attribution capability** | High | Deters by ensuring accountability | Medium - long-term deterrence |
| **International coordination** | High | Addresses regulatory arbitrage | Medium - depends on cooperation |
| **Financial monitoring AI** | Medium | Detects procurement patterns | Medium - can be circumvented |
| **Open-weight model governance** | Medium | Addresses model proliferation | Low-Medium - difficult to enforce |

### Investment Gaps Requiring Attention

1. **Defensive AI for biosecurity**: Underinvested relative to offensive capability growth
2. **Attribution research**: Significant capability gap in AI-era forensics
3. **International coordination mechanisms**: Governance lags capability
4. **Cloud laboratory oversight**: Emerging attack surface without adequate monitoring
5. **Synthetic biology forensics**: Novel domain requiring new capabilities

## Appendix E: Confidence Rubric and Evidence Assessment

> **Justification for confidence ratings assigned to key findings.**

### Confidence Rating Methodology

| Rating | Definition | Evidence Standard |
|--------|------------|-------------------|
| **High** | Assessment is well-supported | Multiple independent sources; consistent with established patterns; alternative explanations considered and found less plausible |
| **Medium** | Assessment is reasonable given available evidence | Some corroborating sources; consistent with theory but empirical gaps exist; key uncertainties identified |
| **Low** | Assessment is possible but speculative | Limited sources; significant extrapolation required; multiple alternative explanations remain viable |

### Key Finding Evidence Assessment

#### Finding 1: AI unlikely to enable T0→WMD but will lower T1-T3 barriers
**Confidence: High**

| Evidence For | Evidence Against | Key Unknowns |
|--------------|------------------|--------------|
| Historical precedent: Aum Shinrikyo failed despite resources | Tacit knowledge erosion rate is uncertain | How fast will VLM+automation close the tacit knowledge gap? |
| Current AI evaluations show limited uplift for novices | Some T0→T1 progression may be AI-accelerated | Will fine-tuned/jailbroken models change this? |
| Physical barriers remain (materials, equipment) | Cloud labs reduce physical access requirements | How quickly will cloud lab screening mature? |
| Red team exercises confirm knowledge gap | | |

#### Finding 2: Biological weapons represent highest AI-risk category
**Confidence: High**

| Evidence For | Evidence Against | Key Unknowns |
|--------------|------------------|--------------|
| DNA synthesis becoming commodity | Weaponization requires more than synthesis | Timeline for synthesis→weapon pipeline automation |
| Dual-use equipment identical to legitimate tools | Detection improving (biosurveillance) | Will screening keep pace with synthesis democratization? |
| AI specifically strong at knowledge synthesis | Most pathogens require BSL-3+ handling | Will cloud labs implement sufficient controls? |
| Self-replicating agents amplify small successes | Historical failure rate of non-state bio programs high | |

#### Finding 3: Tacit knowledge gap is eroding but still significant
**Confidence: Medium**

| Evidence For | Evidence Against | Key Unknowns |
|--------------|------------------|--------------|
| VLMs demonstrating lab procedure interpretation | Current VLMs still error-prone for complex procedures | Rate of VLM improvement on lab tasks |
| Cloud labs embody tacit knowledge in automation | Automation still requires operator judgment | Will VLM+automation integration accelerate? |
| AI-guided instruction provides adaptive feedback | "Last mile" of physical execution remains | How much tacit knowledge is truly irreducible? |

#### Finding 4: Nuclear weapons face strongest physical barriers
**Confidence: High**

| Evidence For | Evidence Against | Key Unknowns |
|--------------|------------------|--------------|
| Fissile material remains scarce and detectable | Information aggregation could assist state programs | Could theft/diversion be AI-optimized? |
| Enrichment requires industrial infrastructure | Black market for materials exists | Will AI improve supply chain obfuscation for states? |
| Strong international monitoring (IAEA) | | |
| No non-state actor has come close | | |

#### Finding 5: Cyber-physical attacks may be higher near-term risk
**Confidence: Medium**

| Evidence For | Evidence Against | Key Unknowns |
|--------------|------------------|--------------|
| Stuxnet demonstrated code→physical harm | Critical infrastructure increasingly hardened | How many facilities remain vulnerable? |
| ICS/SCADA vulnerabilities are known | Air-gapping and redundancy are standard | Will AI improve ICS exploitation capabilities? |
| No synthesis required - existing materials weaponized | Attribution after cyber attack is difficult | What's the actual attack surface for BSL-4/chem plants? |
| AI could assist reconnaissance and exploitation | Few public examples of successful ICS attacks | |

#### Finding 6: High-frequency attempts more likely than mass casualty
**Confidence: Medium**

| Evidence For | Evidence Against | Key Unknowns |
|--------------|------------------|--------------|
| Barrier reduction → more actors can attempt | One sophisticated actor could break pattern | Intent prevalence among capable actors |
| Historical attempt rate already > success rate | AI might enable qualitative capability jump | Will detection capabilities scale with attempt volume? |
| Failure cascade compounds across steps | | How much will "noise floor" increase? |

---

## Appendix F: Defender's Measurement Framework

> **Operationalizing "uplift" for defensive evaluation without testing harmful endpoints.**

### Purpose

Defenders need to measure whether AI meaningfully improves hostile actors' capabilities without directly testing harmful outcomes. This framework proposes evaluation concepts.

### Measurement Dimensions

| Dimension | What It Captures | Evaluation Approach |
|-----------|-----------------|---------------------|
| **Planning completeness** | Does AI help actors identify all steps? | Compare task decomposition quality with/without AI on benign analogues |
| **Error correction** | Does AI help actors recover from mistakes? | Measure troubleshooting effectiveness on complex but safe procedures |
| **Iteration speed** | Does AI accelerate learning cycles? | Time-to-competence metrics on legitimate skill acquisition |
| **Knowledge synthesis** | Does AI aggregate dispersed information? | Assess coherence of literature reviews on complex topics |
| **Operational security** | Does AI help actors avoid detection? | Red team exercises on defensive monitoring evasion (controlled) |

### Safe Evaluation Protocols

1. **Benign analogues**: Test on complex but harmless procedures (e.g., brewing, fermentation, legitimate synthesis) that share structural features with concerning domains
2. **Truncated pathways**: Evaluate early stages of task chains without completing harmful endpoints
3. **Expert comparison**: Measure AI performance relative to published literature rather than actual harmful capability
4. **Adversarial robustness**: Test guardrail durability under jailbreaking attempts (with appropriate containment)

### Metrics for Vendors/Regulators

| Metric | Description | Threshold Guidance |
|--------|-------------|-------------------|
| **Uplift ratio** | Performance improvement vs. baseline (no AI) | >2x on concerning domains warrants scrutiny |
| **Guardrail bypass rate** | Fraction of adversarial prompts that succeed | Define acceptable thresholds by capability tier |
| **Knowledge aggregation depth** | Coherence of synthesized information on controlled topics | Compare to expert-curated baselines |
| **Iteration efficiency** | Speed of convergence on complex procedures | Benchmark against novice learning curves |

### Application

This framework is intended for:
- AI developers evaluating models pre-release
- Regulators assessing safety claims
- Security researchers benchmarking defensive measures
- Procurement decisions for high-capability AI access

---

## Appendix G: Responsible Citation Guide

> **For derivative works**: If you're building on this analysis, these guidelines help maintain the defensive framing.

### Self-Review for Derivative Works

| Check | Question | If Yes |
|-------|----------|--------|
| ☐ | Does your excerpt include **stepwise sequences** without surrounding context? | Add barriers/limitations discussion |
| ☐ | Are you adding **specific technical details** not in the original? | Consider whether addition serves defense or offense |
| ☐ | Does your framing **emphasize capabilities over barriers**? | Rebalance to match original's structure |
| ☐ | Are **probability estimates** presented as confident predictions? | Add uncertainty language |
| ☐ | Could your excerpt **support alarmist narratives** out of context? | Add context anchors |

### Suggested Citation Practices

When citing this document:
- Include the "What This Document Is NOT Claiming" framing when discussing findings
- Pair capability discussions with corresponding barrier discussions
- Note that probability estimates are subjective priors, not predictions
- Link to the full document when possible

### Contributing

This document is released under MIT/Unlicense. Contributions, corrections, and extensions are welcome:
- File issues for factual errors or outdated information
- Submit PRs for substantive improvements
- Fork for derivative analyses with different assumptions

The goal is informed public discussion of AI governance challenges.

---

*This document is released for public discussion of AI governance challenges. Licensed under MIT/Unlicense.*
