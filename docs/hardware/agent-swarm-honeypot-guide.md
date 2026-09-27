# Detecting Autonomous Agent Swarms with Deception

**A program guide for detection, attribution, and provider reporting**

| | |
|---|---|
| **Document** | HONEYPOT-2026-HW-004 |
| **Version** | 1.1 (September 2026) |
| **Audience** | Security teams, sector ISACs, national CERTs, and policy bodies planning deception programs aimed at autonomous AI agent activity |
| **Scope** | Defensive detection, attribution, and reporting only. No offensive countermeasures, no hack-back, no ready-made decoy artifacts. |
| **Companion document** | [AI Agent Containment & Infrastructure Security Framework](./ai-agent-containment-infrastructure-security-framework.md): how to keep your *own* agents contained |
| **PDF source** | [`latex/agent-swarm-honeypot-guide.tex`](./latex/agent-swarm-honeypot-guide.tex) |

> [!IMPORTANT]
> **The premise.** Autonomous agents are thorough, act on what they read, and move fast across many targets. Deception (decoy systems, credentials, and data with no legitimate use) turns each of those traits into an observable event. This guide sets out how to design, operate, and govern such a program at the level of principles and program design, not ready-made artifacts.

---

## Contents

- [How to Use This Guide](#how-to-use-this-guide)
1. [Executive Summary](#1-executive-summary)
2. [What Is Known About AI-Driven Intrusion Activity](#2-what-is-known-about-ai-driven-intrusion-activity)
3. [Design Principles](#3-design-principles)
4. [Threat Model: How Agent Swarms Differ](#4-threat-model-how-agent-swarms-differ)
5. [Deception Layers](#5-deception-layers)
6. [Signals Specific to AI Agents](#6-signals-specific-to-ai-agents)
7. [Cautious and Proxied Adversaries](#7-cautious-and-proxied-adversaries)
8. [Attribution and Provider Reporting](#8-attribution-and-provider-reporting)
9. [Telemetry, Evidence, and Integrity](#9-telemetry-evidence-and-integrity)
10. [Legal and Ethical Guardrails](#10-legal-and-ethical-guardrails)
11. [Operating the Program](#11-operating-the-program)
12. [Checklists](#12-checklists)
13. [References](#13-references)
- [Document History](#document-history)

---

## How to Use This Guide

This guide is written for several audiences. Each can start in a different place:

| If you are... | Start with | Then read |
|---------------|------------|-----------|
| A security team planning a program | Section 3 (principles) and Section 5 (layers) | Sections 9, 11, and 12 |
| A sector ISAC, CERT, or national agency | Section 7 (proxied adversaries) and Section 8 (reporting) | Section 11.1 (maturity model) |
| A policy body or regulator | Section 1 (summary) and Section 2 (evidence) | Sections 10 and 11.1 |
| Legal counsel or a privacy officer | Section 10 (guardrails) | Section 9 and Section 8.3 |
| A model or platform provider receiving reports | Section 8 (reporting) | Section 6 (AI-agent signals) |

### Key Terms

| Term | Meaning in this guide |
|------|-----------------------|
| **Decoy** | A system, credential, record, or piece of content that no legitimate user or process needs to touch |
| **Decoy value** | The unique string, credential, or identifier carried by a decoy |
| **Placement** | One decoy value exposed in one location at one time |
| **Placement ledger** | The private record of every placement: value, location, time placed, and exposure context |
| **Touch** | Any read, copy, use, or reuse of a decoy |
| **Sighting** | A later appearance of a decoy value anywhere, inside or outside your network |
| **Campaign** | A set of touches and sightings attributed to one actor or agent configuration |
| **Provider** | The model, agent-platform, cloud, or proxy operator that can see the accounts behind the activity |

> [!NOTE]
> **What this guide deliberately leaves out.** There are no decoy templates, strings, file names, banners, or lists of "tells" anywhere in this document. It is public and will be read by the adversaries it describes; anything published here is, by definition, a signature. Section 3.3 explains why this is a security control rather than an omission.

---

## 1. Executive Summary

Autonomous and semi-autonomous AI agents are now used to run intrusion campaigns. Public threat reports from model providers and security vendors describe operations in which AI did most of the hands-on work (reconnaissance, vulnerability discovery, credential harvesting, and lateral movement) across many targets in parallel. Some describe operators running multiple coordinated agents ("swarms") against many organizations at once.

Deception (decoy systems, decoy credentials, and decoy data that have no legitimate use) is one of the few defensive techniques that becomes *more* valuable against this kind of adversary. It turns the traits that make agents effective into observable events:

- **Agents are thorough.** They enumerate everything they can reach and read what they find. Decoys that a hurried human would skip are exactly what a tireless agent opens.
- **Agents act on what they read.** They reuse credentials found in files, call endpoints named in documentation, and follow instructions embedded in content. Each of those actions can be observed.
- **Agents are fast and parallel.** One campaign touches many organizations within hours. A well-run sharing program sees the same unique indicators appear across many sensors, which clusters the campaign.

```mermaid
flowchart LR
    T1["Thorough:<br/>enumerates and reads everything"] --> O1["Decoys where only an<br/>exhaustive search looks"] --> E1["Read-time alert"]
    T2["Acts on what it reads:<br/>reuses credentials, calls endpoints"] --> O2["Credentials and endpoints<br/>that exist only as decoys"] --> E2["Use-time alert<br/>tied to one placement"]
    T3["Fast and parallel:<br/>many targets within hours"] --> O3["The same unique values<br/>seen by many sensors"] --> E3["Campaign clustering<br/>across organizations"]
    classDef trait fill:#EEF0FA,stroke:#1A237E,color:#1C2233
    classDef offer fill:#FFF0CC,stroke:#C77700,color:#1C2233
    classDef event fill:#E0F2F1,stroke:#00838F,color:#1C2233
    class T1,T2,T3 trait
    class O1,O2,O3 offer
    class E1,E2,E3 event
```

*Figure 1. Why deception works against agents: each trait that makes an agent effective also makes it observable.*

This guide sets out how to design, operate, and govern a deception program for this threat. It is written at the level of **principles and program design**, not ready-made artifacts. That choice is itself a security control (Section 3.3): the document is public and will be read by the adversaries it describes, so nothing in it should be copied verbatim into a deployment.

> [!IMPORTANT]
> **Five core principles**
>
> 1. **Detection on touch.** Design every decoy so that the first read, first use, or first reuse is the alert. An adversary that recognizes the decoy after touching it has already been recorded.
> 2. **Uniqueness per placement.** Every decoy value is generated for exactly one location and one time. Any later appearance of that value tells you where and when it was harvested.
> 3. **Secrecy of keys, not of method.** The program must keep working even if the adversary has read this guide. What stays secret is the per-deployment material (which values are decoys and where they were placed), never the technique.
> 4. **Zero legitimate use.** A decoy that real users and real systems never touch produces near-zero false positives, so every event is worth investigating.
> 5. **Evidence that providers can act on.** The goal is not only blocking but identifying the accounts and agents involved. Decoy credentials for services you own put the primary evidence in your own logs; reporting to the responsible model or platform provider then gives it something it can find in *its* logs.

Sections 3.1-3.5 treat each principle in turn. No program is perfect. A cautious agent may route every request through disposable infrastructure, avoid anything that looks too good, and test credentials only from throwaway environments. Section 7 shows that a program still learns a great deal in that case.

### 1.1 What This Guide Does Not Cover

> [!WARNING]
> **Out of scope.** This is a defensive guide. It does not cover and does not endorse:
>
> - offensive countermeasures, "hack-back", or any action against systems you do not own;
> - decoys that deliver malware, exploits, or harmful content;
> - deception directed at the public, customers, or employees;
> - techniques whose purpose is to damage or degrade an AI system, as opposed to detecting and identifying its misuse.

Most AI agents that touch your perimeter are not misaligned. Crawlers, research agents, security scanners, and users' assistants all appear in the same logs. Section 10 covers how to keep the program proportionate and fair to them.

---

## 2. What Is Known About AI-Driven Intrusion Activity

Public reporting from 2024-2026 already supports three conclusions for anyone designing a deception program:

> [!IMPORTANT]
> **Three conclusions for defenders**
>
> - **Sensor networks see campaigns first.** The PaperCut campaign was characterized from decoy and sensor data spread across many networks. Deception scales best as a *shared* capability.
> - **Stolen credentials are part of the economy.** Operators run swarms on other people's API keys, so credentials are among the first things an agent collects and tries. Decoy credentials for services you own and operate turn that habit into a use-time alert that you observe directly, with the full request in your own logs (Section 5.2).
> - **Agents are imperfect and sometimes disobedient.** They overstate, hallucinate, and ignore their own operators' constraints. They do not reliably apply the caution a careful human operator would, which is why detection on touch works.

The evidence base is young but growing quickly. The findings behind these conclusions, from primary publications and in date order, are summarized below; see Section 13 for full references.

| Date | Source | Finding relevant to deception |
|------|--------|-------------------------------|
| Oct 2024 | Palisade Research, *LLM Agent Honeypot* (arXiv:2410.13919) | A public SSH honeypot instrumented to detect LLM-driven sessions logged over 8.1 million interaction attempts and flagged 8 potential AI agents. Two signals were used together: whether the session acted on embedded natural-language content, and response timing (flagged agents answered in roughly 1.7 s median, where human sessions often took over 10 s). |
| Oct 2024 | *Mantis* (arXiv:2410.20911) | Research framework showing that decoy services can detect and disrupt LLM-driven attacking agents by exploiting the fact that agents act on content returned by the target. |
| Aug 2025 | Anthropic threat report (GTG-2002) | A single operator used an AI coding agent for data extortion against at least 17 organizations; accounts were banned and indicators shared with authorities. |
| Oct 2025 | OpenAI threat report | More than 40 networks disrupted since February 2024. Actors used multiple models and adapted to detection (one network removed a punctuation habit that had become a known sign of AI-written text). |
| Nov 2025 | Anthropic, GTG-1002 | A state-linked campaign, detected mid-September 2025, used an AI agent orchestrated through MCP tooling against roughly 30 targets, with the AI performing an estimated 80-90% of tactical work. The model frequently overstated findings and produced credentials that did not work. Agents mishandle what they collect, and a decoy program can observe that. MITRE ATT&CK tracks this as campaign C0062. |
| Nov 2025 | Google Threat Intelligence Group | Documented malware families that call LLMs at runtime (e.g. PROMPTFLUX, PROMPTSTEAL). |
| Dec 2025 | UK NCSC deception trial findings | Across 121 organizations and 14 providers, deception was found practical; 90% of participants would not publicly announce their use of it. |
| Sep 2026 | GreyNoise, PaperCut exploitation campaign | AI-agent-driven exploitation reached at least 440 instances across 395 organizations in 48 countries. It was observed through a distributed sensor network (decoys and passive sensors, not victim networks). The agents also ignored parts of the operator's own exclusion list. |
| Sep 2026 | Anthropic threat report | Operators "routinely ran agent swarms"; stolen AI API keys taken from customer environments were used to fund operations. |
| Sep 2026 | Google Threat Intelligence Group | A credential-harvesting campaign completed in under six hours with IP rotation; GTIG states it has not yet observed fully autonomous end-to-end pipelines. |

---

## 3. Design Principles

> **In brief.** Five principles carry the program: detect on the first touch, make every decoy value unique to one placement, keep the per-deployment material secret rather than the method, keep decoys free of legitimate use, and collect evidence that a provider can act on. A sixth requirement (decoys must be safe) is a constraint on all five.

### 3.1 Detection on Touch

Treat each decoy as a tripwire whose value is realized at the first interaction, not at the end of an engagement.

```mermaid
flowchart LR
    A["Agent discovers decoy"] --> B["Agent reads or copies it"]
    B --> C["Agent uses or reuses it"]
    C --> D["Agent realizes it is a decoy"]
    B -. "alert 1: access logged" .-> L[("Off-host, tamper-evident log")]
    C -. "alert 2: use logged" .-> L
    D -. "too late: identifiers already recorded" .-> L
    classDef step fill:#EEF0FA,stroke:#1A237E,color:#1C2233
    classDef late fill:#ECEFF1,stroke:#78909C,color:#1C2233
    classDef log fill:#F3E5F5,stroke:#6A1B9A,color:#1C2233
    class A,B,C step
    class D late
    class L log
```

*Figure 2. Detection on touch: the read and the use are each logged off-host before the agent can recognize the decoy.*

Practical consequences:

- **Instrument the read path, not only the use path.** File access auditing, object-store access logs, and database query logging on decoy records all fire before an agent can evaluate what it has.
- **Prefer decoys that report themselves wherever they are used**, such as credentials for services you own and operate, which can only be validated by contacting infrastructure you control. The alert then does not depend on the adversary staying inside your network.
- **Assume some decoys will eventually be recognized.** Design so that recognition gives the adversary nothing back: the log has already been written, off-host, and cannot be changed from the decoy.

### 3.2 Uniqueness per Placement

Every decoy value (credential, hostname, document, record, phrase) is generated for a single placement and recorded in a private **placement ledger**: value, location, time placed, and the context it was exposed in. Every later sighting then becomes a precise statement: *this value was harvested from this location at or after this time.*

```mermaid
flowchart LR
    G["Generate per deployment,<br/>from your own data"] --> V1["value v1 -> placement 1"]
    G --> V2["value v2 -> placement 2"]
    G --> V3["value v3 -> placement 3"]
    G -. "record each value" .-> L[("Placement ledger<br/>value, location, time, context")]
    V2 -. "harvested" .-> S["Later sighting of v2<br/>another network, a paste site,<br/>or a provider log"]
    S --> Q{"Private ledger lookup"}
    L -.-> Q
    Q --> A["Precise statement:<br/>harvested from placement 2<br/>at or after time T2"]
    classDef gen fill:#EEF0FA,stroke:#1A237E,color:#1C2233
    classDef decoy fill:#FFF0CC,stroke:#C77700,color:#1C2233
    classDef ledger fill:#F3E5F5,stroke:#6A1B9A,color:#1C2233
    classDef quiet fill:#ECEFF1,stroke:#78909C,color:#1C2233
    classDef hot fill:#FCE4EC,stroke:#AD1457,color:#1C2233
    class G gen
    class V1,V2,V3 decoy
    class L,Q ledger
    class S quiet
    class A hot
```

*Figure 3. Uniqueness per placement: because each value exists in exactly one place, a private ledger lookup turns any later sighting into a statement of where and when it was taken.*

Uniqueness also means:

- sightings on other networks, in paste sites, in criminal markets, or in a provider's logs link back to the original exposure;
- two sightings of values from *different* placements by the same actor tie those placements into one campaign;
- decoys cannot be "burned" in bulk: recognizing one tells the adversary nothing about the others.

> [!CAUTION]
> **Protect the ledger.** The placement ledger is the program's crown jewel. Store it separately from the decoys, restrict access, and never place it on any system the decoys share. Anyone who reads it can map every remaining decoy.

### 3.3 Secrecy of Keys, Not of Method

Kerckhoffs's principle, applied to deception: **assume the adversary knows everything in this guide** and every public paper on the topic. A highly capable agent will. The program's strength must come from material the adversary cannot know:

- which specific values are decoys (generated per deployment, recorded only in the ledger);
- where they are placed and what story connects them;
- how they are monitored and where alerts go.

This is why the guide contains no fixed templates, strings, file names, or banners. Anything published is, by definition, a signature. Generate your own artifacts from your own environment (Section 5), and treat any shared example, here or anywhere, as something to learn from and then discard.

A second consequence: do not announce your program. In the NCSC trial, 90% of participants said they would not publicly announce their use of deception. Saying that you use deception does no harm if the design follows this section; publishing specifics about coverage, vendors, or placement does.

### 3.4 Zero Legitimate Use

A decoy that nobody legitimately touches has a false-positive rate near zero. Protect that property:

- keep decoys out of search indexes, backups, inventory scanners, and automated tooling that would touch them routinely, or allowlist those tools explicitly and alert on everything else;
- brief the small set of administrators who must know, and route their accidental touches through a documented process;
- review every alert; a decoy that alerts on benign activity is fixed or retired, not ignored.

### 3.5 Evidence That Providers Can Act On

Detection is the start, not the goal. A program succeeds when the accounts and agents behind a campaign are identified and the party that can act on them (usually the model or platform provider) receives evidence it can join against its own logs. That goal shapes design decisions long before any report is written:

- unique decoy values (Section 3.2) and accurate, tamper-evident time (Section 9) are what make a provider-side join possible;
- decoy credentials for services you own put the full record of every use (source, timing, headers, request content, and what the caller attempted) in your own logs, without depending on anyone else's cooperation (Section 5.2);
- provider reporting still applies on top of that record: when it contains a provider-issued identifier, or when you can give the provider a precise time window plus unique content to search for (Section 8.1);
- reporting routes arranged in advance keep confirmed evidence from going stale (Section 8).

### 3.6 Decoys Must Be Safe

Safety is not a sixth principle to trade off against the others; it is a constraint on all of them. A decoy is a system you operate and are responsible for:

- it must not provide a pivot to real systems (network segmentation, no real credentials, no trust relationships);
- egress from interactive decoys is tightly controlled so they cannot be used to attack others;
- decoy data contains no real personal data, no real secrets, and no genuinely harmful content;
- decoy credentials grant no real capability anywhere.

The isolation guidance in the companion [AI Agent Containment & Infrastructure Security Framework](./ai-agent-containment-infrastructure-security-framework.md) (network namespaces, microVMs, and egress allowlisting) applies directly to interactive decoys.

---

## 4. Threat Model: How Agent Swarms Differ

> **In brief.** Agent swarms combine the breadth of a scanner with the reading and reasoning of a human operator. Unlike botnets, they run under accounts that some provider can see, which gives defenders a remediation path.

### 4.1 Characteristics That Matter for Deception

| Characteristic | Human operator | Classic bot or scanner | Autonomous agent swarm | Implication for deception |
|----------------|----------------|------------------------|------------------------|---------------------------|
| **Breadth** | Selective | Broad but shallow | Broad **and** deep | Deep decoys (documents, configurations, internal docs) get read, not just probed |
| **Speed** | Minutes to days | Milliseconds | Seconds per step, many in parallel | Timing is a detection signal; correlation windows must be short |
| **Reads natural language** | Yes, selectively | No | Yes, exhaustively | Content itself can be a tripwire |
| **Acts on what it reads** | With judgment | Only on fixed patterns | Often literally | Decoy credentials and documented endpoints get used |
| **Reuses findings** | Carefully | Rarely | Frequently, across targets | Per-placement uniqueness links targets into a campaign |
| **Memory and persistence** | Notes | None | Shared memory, task queues | A decoy seen by one agent may be used later by another |
| **Operational caution** | Variable | None | Variable and inconsistent | Some agents probe for decoys; many do not, and even cautious ones slip |
| **Accountable identity** | A person | Infrastructure | An account at a model or platform provider | Provider reporting is a real remediation path |

The last row is the one most specific to this threat. An agent swarm is ultimately driven by model API calls made under accounts, keys, or deployments that some provider can see. Classic botnets offer defenders no equivalent remediation path.

### 4.2 Where Agents Are Likely to Look

Without prescribing specific bait, the surfaces agents consistently enumerate are the ones that help them act:

- **Credentials and configuration**: environment files, configuration directories, CI/CD variables, cloud metadata, secrets in source repositories;
- **Machine-readable descriptions of capability**: API documentation, service registries, tool and plugin manifests, agent-facing instruction files;
- **Internal knowledge**: wikis, runbooks, tickets, shared drives, chat exports;
- **Data stores**: databases, object storage, backups;
- **AI infrastructure itself**: model API keys, agent tool servers, vector stores, and prompt libraries, increasingly valuable because they fund or extend the swarm.

Each is a candidate location for decoys. Which ones, in what proportion, and how they connect is a per-deployment decision (Section 5.3).

### 4.3 Adversary Tiers

Plan for the whole range, not only the most capable.

| Tier | Description | What deception catches |
|------|-------------|------------------------|
| **A: Naive** | Off-the-shelf agent pointed at targets with little configuration | Almost everything: direct use of decoy credentials, content tripwires, obvious timing signatures |
| **B: Operated** | Agent framework run by a capable operator with tooling and target lists | Harvested decoys reused across targets; campaign clustering across sensors |
| **C: Cautious** | Agents instructed to avoid honeypots, validate findings through disposable infrastructure, and rotate everything | Read-time alerts, content-level indicators that survive proxies, behavioral correlation (Section 7) |
| **D: Highly capable and patient** | Strong models that reason about deception, test hypotheses slowly, and exfiltrate for offline analysis | Read-time alerts, downstream sightings of unique data, and the negative signal of deliberate avoidance; attribution is harder, but campaign awareness remains |

Two points matter here. First, tier D does not make deception useless; it shifts the value from "catch it in the act" to "know that it happened, when, and what was taken." Second, adversaries at every tier have to *look* before they can decide. Detection on touch is aimed at the look.

```mermaid
flowchart LR
    A["Tier A: Naive<br/>value mostly from<br/>catching it in the act"] --> B["Tier B: Operated"] --> C["Tier C: Cautious"] --> D["Tier D: Highly capable<br/>value mostly from knowing it<br/>happened, when, and what was taken"]
    classDef act fill:#FFE0A3,stroke:#C77700,color:#1C2233
    classDef mid fill:#F3E9D2,stroke:#5C6480,color:#1C2233
    classDef know fill:#D1D4EC,stroke:#1A237E,color:#1C2233
    class A act
    class B,C mid
    class D know
```

*Figure 4. Illustrative: against more capable tiers, the value of deception shifts from catching the agent in the act to knowing what happened. It does not disappear.*

---

## 5. Deception Layers

> **In brief.** Place decoys at five depths so that avoiding one layer means touching another, connect them with a coherent story, and derive every artifact from your own environment rather than from any public example.

### 5.1 Layered Architecture

A mature program places decoys at several depths so that an adversary who avoids one layer is likely to touch another, and so that touches at multiple layers can be joined into a single story. Every layer reports to central telemetry; the placement ledger sits in its own trust domain and is consulted only through restricted lookups (Section 9).

```mermaid
flowchart TB
    subgraph L1["Layer 1: Perimeter sensors"]
      S1["Internet-facing decoy services"]
      S2["Unused address space and DNS names"]
    end
    subgraph L2["Layer 2: Internal decoy systems"]
      S3["Decoy hosts and services"]
      S4["Decoy internal APIs and tool servers"]
    end
    subgraph L3["Layer 3: Decoy credentials and secrets"]
      S5["Per-placement credentials and keys"]
    end
    subgraph L4["Layer 4: Decoy content and data"]
      S6["Documents, records, knowledge-base entries"]
    end
    subgraph L5["Layer 5: Downstream indicators"]
      S7["Unique data watched for in the wider world"]
    end
    L1 --> L2 --> L3 --> L4 --> L5
    L1 -.-> C[("Central telemetry")]
    L2 -.-> C
    L3 -.-> C
    L4 -.-> C
    L5 -.-> C
    subgraph SEP["Separate trust domain"]
      LG[("Placement ledger")]
    end
    LG -. "restricted lookup" .-> C
```

*Figure 5. Layered deception architecture: five depths of decoys, each reporting to central telemetry, with the placement ledger held in a separate trust domain.*

### 5.2 Layers in Detail

**Layer 1: Perimeter sensors.** Internet-facing decoy services and monitored unused address space. Their main value against swarms is *campaign awareness*: what is being exploited right now, from where, and at what rate. They are also the layer most exposed to fingerprinting, so their value comes from breadth and from sharing, not from any one sensor staying undetected. Low-interaction sensors are cheap and safe; high-interaction decoys yield far more behavior but need the isolation controls in Section 3.6.

**Layer 2: Internal decoy systems.** Hosts, services, and internal APIs inside the real environment that no legitimate workflow uses. Any connection is high-signal. Against agent-driven intrusions, decoy *tool-facing* services are particularly valuable: agents actively look for APIs and tool servers they can call, and each call is a logged, structured record of intent.

**Layer 3: Decoy credentials and secrets.** The highest-yield layer against agents, which reliably collect and try credentials. The recommended mechanism is **decoy credentials for services you own and operate**: your own APIs, endpoints, storage, and internal services. You issue a credential that grants nothing real and place it where an agent would look. Because the credential belongs to your service, the only way anyone can test it is to present it to infrastructure you control. Any use, from any address, anywhere, is therefore observed with full request context: source, timing, headers, request content, and what the caller tried to do with it. Nothing depends on a third party noticing or cooperating.

Design principles for self-owned decoy credentials (principles only, for the reasons in Section 3.3):

- **Indistinguishable from real credentials for that service.** Same format, structure, and issuance metadata as the credentials the service actually issues, produced by your own issuance process rather than invented (Section 5.4).
- **Unique per placement.** One credential per placement, recorded in the ledger, so every use says where and when it was taken (Section 3.2).
- **Plausible response, no capability.** The service answers as it plausibly would for a real credential, for example a realistic authentication failure or a sandboxed, minimal-scope response, but never grants access to real data, real actions, or any real user's resources.
- **Log at the authentication layer, before any response.** The event is written off-host (Section 9) the moment the credential is presented, before the service decides how to answer, so later recognition changes nothing.
- **Isolate the decoy path from real authentication.** Decoy credentials resolve through a separate path with no trust relationship to real accounts: a flaw in the decoy path cannot grant real access, and a failure in it cannot affect real logins.
- **Rate-limit and contain.** Bound what anyone can do with a decoy credential, so the decoy cannot become a resource for abuse or a load on the real service.
- **Do not hurt legitimate users.** Decoy handling never locks out, slows, or raises alerts on real users; decoy values never collide with real ones, and an honest mistake by a real user does not land in the decoy path.

Third-party canary-credential services can supplement this, at the cost of routing the alert through someone else's infrastructure.

**Decoy AI-provider keys (optional, aspirational).** Swarms run on stolen AI keys (Section 2), so decoy keys for a model provider would be attractive bait, and the issuing provider could trace a used key to the caller's account. As far as public information goes, however, major model providers do not generally offer canary or honey API-key programs to third parties. This technique requires a direct relationship with the provider and should not be assumed available. Self-owned decoy credentials deliver most of the same detection value without that dependency.

> [!CAUTION]
> **Never plant real keys as bait.** Never issue real AI-provider keys, or any real credential with spending capacity or real access, as a decoy. An agent that finds one will use it, and you pay for, and are responsible for, whatever it does.

**Layer 4: Decoy content and data.** Documents, database rows, tickets, and knowledge-base entries containing unique, recorded values. They alert on access where storage supports it, and they carry identity: if the content appears anywhere else later, the ledger says where it came from.

**Layer 5: Downstream indicators.** Unique values watched for outside your network: breach dumps, paste sites, criminal marketplaces, phishing lures, model outputs, and (through reporting relationships) providers' own abuse telemetry. Research on "copyright traps" for language models (Meeus et al., ICML 2024) explores the related idea that unique sequences can reveal later use of data; for deception programs, the simpler and more reliable use is sighting unique strings in adversary output and in leaked data.

### 5.3 Designing the Story

Individual decoys are weak; a coherent story is strong. Decide per deployment:

- **What the decoys appear to protect.** Decoys should imply an asset worth pursuing, consistent with what the organization actually is.
- **How they connect.** A credential found in one place should appear to open something in another. The path is where you learn the most, because each step is a separate logged decision.
- **What proportion is decoy.** A small number of carefully placed decoys in the paths agents actually traverse beats large numbers of obvious ones.
- **How they age.** Real environments change. Decoys that never change stand out over time.

Keep the story in the ledger, not in anyone's head.

### 5.4 Realism: Principles, Not Recipes

Agents that reason about deception look for inconsistency. The durable defense is to derive decoys from the organization's own environment rather than from any public example:

- **Generate from your own distributions.** Sample naming conventions, formats, timestamps, sizes, and structure from what your real systems look like; do not invent them.
- **Keep the story consistent across systems.** Everything a decoy refers to should agree with everything else the adversary can see.
- **Keep time consistent.** Creation dates, modification history, and log entries should be plausible for the asset's supposed age and use.
- **Vary across deployments.** Two organizations using the same product should not produce decoys that look alike.
- **Avoid defaults.** Any default configuration of any deception product is, by now, known. Published research has repeatedly shown that default honeypot deployments can be identified at internet scale (Vetterl and Clayton, *Bitter Harvest*, USENIX WOOT 2018; and later measurement studies).
- **Test with adversarial review.** Periodically ask a capable reviewer, including your own contained agents (Section 11.4), to distinguish decoys from real assets, and fix whatever gives them away.

> [!NOTE]
> **Why there is no list of tells.** This guide intentionally does not list the specific details that give decoys away. A list of tells is a checklist for adversaries.

---

## 6. Signals Specific to AI Agents

> **In brief.** A decoy shows *that* something touched it. The signals in this section help judge *whether it was an AI agent*, which matters for attribution and provider reporting. Weight them below hard indicators such as the use of a decoy credential.

```mermaid
flowchart BT
    C["Context only: useful, but easily spoofed or belongs to proxies<br/>source addresses, user agents, TLS characteristics,<br/>unverified claims of a known agent identity"]
    M["Supporting signals: the actor behaves like an AI agent<br/>cadence, breadth-then-depth, natural-language artifacts,<br/>characteristic errors, parallel near-identical sessions,<br/>response to decoy content"]
    H["Hard indicators: a decoy was taken and used<br/>use of a decoy credential, unique decoy content<br/>read or reproduced, provider-issued identifiers"]
    C -- "weighs less than" --> M
    M -- "weighs less than" --> H
    classDef ctx fill:#ECEFF1,stroke:#78909C,color:#1C2233
    classDef sup fill:#FFF0CC,stroke:#C77700,color:#1C2233
    classDef hard fill:#FCE4EC,stroke:#AD1457,color:#1C2233
    class C ctx
    class M sup
    class H hard
```

*Figure 6. Weighing evidence: behavioral signals support an AI-agent assessment, but hard indicators carry attribution. Network context is the weakest.*

### 6.1 Behavioral and Timing Signals

- **Cadence.** Agent sessions show characteristic timing: pauses between steps consistent with model inference, often faster than a human reading output and slower than a scripted tool. Palisade's work used timing as one of its two signals.
- **Breadth-then-depth patterns.** Exhaustive enumeration followed by targeted reading of text-rich items.
- **Natural-language artifacts.** Commands, queries, messages, or tickets written in fluent natural language, including explanations nobody asked for.
- **Characteristic errors.** Plausible-but-wrong commands, invented paths or parameters, and confident use of invalid credentials. GTG-1002's agent produced credentials that did not work; that failure mode is visible to a decoy.
- **Parallel, near-identical sessions** from many sources at once.

None of these alone is conclusive, and all can be imitated or suppressed. Use them in combination.

### 6.2 Content That an Agent Acts On

Agents read content and sometimes act on instructions inside it; that is the root of prompt injection. Research efforts including Palisade's honeypot and Mantis have used this property defensively: content in a decoy environment that a human would ignore but an LLM-driven agent may act on, producing an observable response.

> [!CAUTION]
> **Guardrails for content-based signals.** If you use this technique:
>
> - **Only on zero-legitimate-use surfaces.** Never place such content where benign agents (users' assistants, search crawlers, research tools) are expected. Their behavior is not evidence of misalignment.
> - **Elicit identification, never harm.** The acceptable goals are self-identification and an observable, harmless response. Content designed to damage, disable, or mislead an AI system beyond the decoy, or to cause it to act against third parties, is out of scope.
> - **Expect decreasing yield.** Providers and agent frameworks are hardening against prompt injection, and cautious operators instruct agents to ignore embedded instructions. Treat a response as a strong signal and its absence as no signal at all.
> - **Generate per deployment.** For the reasons in Section 3.3, never reuse published wording.

### 6.3 Declared Agent Identity

Many legitimate AI crawlers and user-directed agents identify themselves in request headers and publish verification methods, such as published IP ranges or signed requests. Record and verify these. A verified, declared agent touching a zero-legitimate-use decoy is still noteworthy, but it is a policy conversation with that operator, not an intrusion. Unverified claims of a well-known agent identity are common; treat them as spoofing until verified.

```mermaid
flowchart LR
    T["Touch on a zero-legitimate-use decoy"] --> D1{"Declares an<br/>agent identity?"}
    D1 -- "yes" --> D2{"Identity verified?<br/>published ranges,<br/>signed requests"}
    D1 -- "no" --> I["Investigate as a<br/>potential intrusion"]
    D2 -- "yes" --> P["Policy conversation with<br/>the operator, not an intrusion"]
    D2 -- "no" --> S["Treat the claim as spoofing"]
    S --> I
    classDef step fill:#EEF0FA,stroke:#1A237E,color:#1C2233
    classDef ok fill:#E0F2F1,stroke:#00838F,color:#1C2233
    classDef warn fill:#FFF0CC,stroke:#C77700,color:#1C2233
    classDef hot fill:#FCE4EC,stroke:#AD1457,color:#1C2233
    class T,D1,D2 step
    class P ok
    class S warn
    class I hot
```

*Figure 7. Handling declared agent identity: verification separates a policy conversation with a benign operator from a potential intrusion.*

---

## 7. Cautious and Proxied Adversaries

> **In brief.** Proxies hide the address, not the decoy value. Against a cautious swarm, the program shifts from blocking infrastructure to correlating campaigns, and sharing becomes essential.

A careful swarm routes every request through rotating residential proxies or disposable cloud hosts, validates credentials only from throwaway environments, and never touches the same sensor twice from the same address. This defeats IP-based blocking. It does not defeat a well-designed deception program, because **the decoy value is the identity, not the address.**

```mermaid
flowchart TB
    P1["Proxy exit 1"] --> T1
    P2["Proxy exit 2"] --> T2
    P3["Proxy exit 3"] --> T3
    subgraph OrgA["Organization A"]
      T1["Decoy value A7"]
    end
    subgraph OrgB["Organization B"]
      T2["Decoy value B3"]
    end
    subgraph OrgC["Organization C sensor"]
      T3["Decoy value C1"]
    end
    T1 --> U["Same session uses A7 and B3"]
    T2 --> U
    T3 --> F["Matching timing and phrasing fingerprint"]
    U --> K["One campaign"]
    F --> K
    classDef proxy fill:#ECEFF1,stroke:#78909C,color:#1C2233
    classDef decoy fill:#FFF0CC,stroke:#C77700,color:#1C2233
    classDef corr fill:#E0F2F1,stroke:#00838F,color:#1C2233
    classDef camp fill:#FCE4EC,stroke:#AD1457,color:#AD1457
    class P1,P2,P3 proxy
    class T1,T2,T3 decoy
    class U,F corr
    class K camp
```

*Figure 8. Proxy correlation graph: rotating exits hide the address, but decoy identity and behavioral fingerprints still join events into one campaign.*

### 7.1 What Still Works

- **Token identity survives proxies.** A decoy credential harvested from placement X and used from any address, anywhere, still identifies placement X. Rotating infrastructure changes nothing about what was taken, and when the credential is for a service you own, every attempt lands in your own authentication logs regardless of the exit it came from.
- **Reuse graphs.** Build a graph whose nodes are decoy values, source infrastructure, and sessions, with edges for "harvested", "used", and "seen together". Values harvested at different organizations but used in the same session, or in the same short window with the same behavior, join those organizations' incidents into one campaign (Figure 8).
- **Behavioral fingerprints.** Timing distributions, command or query sequences, error patterns, and phrasing in natural-language artifacts are properties of the agent and its configuration, not of the network path. They persist across proxy rotation.
- **Content-level indicators.** Anything the agent writes (messages, tickets, commit text, reports it leaves behind) can be compared across sensors.
- **Temporal correlation.** Swarms act in bursts. Tight time windows across many sensors are themselves a clustering feature.

### 7.2 What Changes

- **Attribution to infrastructure becomes weak**; attribution to *campaign* and *agent configuration* remains strong.
- **Provider reporting becomes more important**, because the provider can see the account behind the model calls regardless of which proxy carried the traffic to you (Section 8).
- **Sharing becomes essential.** A single organization sees a handful of disconnected events; a sharing community sees the graph.

### 7.3 The Value of Avoidance

A highly cautious agent that detects and avoids decoys still leaves evidence: enumeration that skips exactly the decoys, probing patterns that test for deception, or long pauses at decision points. Deliberate avoidance of zero-legitimate-use assets is a behavior no legitimate user has. Record it; it is a weak signal alone but valuable in combination.

---

## 8. Attribution and Provider Reporting

> **In brief.** Defenders rarely can identify an agent's account; providers usually can, if the report gives them something to join against their own logs. The two strongest joins are precise time plus unique content, and identifiers the provider itself issued.

### 8.1 From Indicator to Accountable Account

Figure 9 shows the chain a program aims to build, from a unique decoy value to provider action and community sharing.

```mermaid
flowchart LR
    subgraph DEF["Defender: detection and evidence"]
      G["Step 1: Generate unique value"] --> P["Step 2: Place and record in ledger"]
      P --> T["Step 3: Touch or use observed"]
      T --> E["Step 4: Evidence packaged"]
    end
    subgraph ACC["Provider, platform, and community: accountability"]
      R["Step 5: Report to provider or platform"] --> A["Step 6: Provider correlates to account and acts"]
      A --> S["Step 7: Indicators shared with community"]
    end
    E --> R
    classDef def fill:#FFF0CC,stroke:#C77700,color:#1C2233
    classDef step fill:#EEF0FA,stroke:#1A237E,color:#1C2233
    classDef hot fill:#FCE4EC,stroke:#AD1457,color:#1C2233
    classDef share fill:#E0F2F1,stroke:#00838F,color:#1C2233
    class G,P def
    class T,E,R step
    class A hot
    class S share
```

*Figure 9. Indicator-to-report chain: from a unique decoy value to provider action and community sharing.*

When a decoy credential for a service you own is used, you already hold the primary evidence: your own logs of the request, from the authentication layer onward. What defenders usually cannot do is identify the account behind the agent. Providers usually can, *if* the report gives them something to join against their own logs. The two most useful joins are:

1. **Precise time plus unique content.** If an agent read or produced a unique decoy string (including a decoy credential it then presented to your service), the provider may be able to find that string in its request or response logs within the reported time window. This is why per-placement uniqueness and accurate clocks matter so much.
2. **Credentials and identifiers the provider issued.** Real account, organization, deployment, or API-key identifiers belonging to the provider that the adversary exposed (in requests to your services, in headers, or in content it left behind) map directly to accounts. Decoy AI-provider keys would also belong here, but only where a provider relationship supports them (Section 5.2).

Other request metadata (source addresses, user agents, TLS characteristics) is useful context but weaker, because it is easily spoofed or belongs to proxies.

### 8.2 Which Provider

Evidence may point to a model provider, an agent platform, a cloud host, or a proxy service. Report to each party that can act on its part. Most major AI providers publish abuse or threat-intelligence reporting channels and have described acting on third-party reports in their threat reports; confirm the current channel on the provider's own site before reporting.

Do not assume which provider is involved: actors use multiple models and switch when detected (Section 2). Let the evidence decide, and when it is ambiguous, say so.

### 8.3 The Reporting Package

A report that a provider can act on quickly contains the fields below.

| Field | Content |
|-------|---------|
| **Summary** | One paragraph: what was observed, why it is believed to be AI-agent activity, and why it is believed malicious |
| **Time window** | Start and end in UTC, with clock source and stated accuracy |
| **Unique content** | The exact decoy strings read, used, or reproduced, and in which direction (read by the agent vs. produced by it); for decoy credentials to your own services, what the caller attempted with them |
| **Provider-issued identifiers** | Any keys, account, organization, or deployment identifiers belonging to that provider observed in the activity |
| **Behavioral evidence** | Timing, sequence, and natural-language artifacts supporting the AI-agent assessment |
| **Network context** | Source infrastructure and request metadata, marked as possibly proxied or spoofed |
| **Scope** | Other organizations or sensors where the same campaign was seen, if sharing permits |
| **Confidence** | Explicit confidence level and what would change it |
| **Evidence integrity** | Hashes of the preserved logs and how they were preserved (Section 9) |
| **Contact** | A responsive point of contact and preferred secure channel |

> [!CAUTION]
> **Minimize what you send.** Keep personal data to the minimum needed (Section 10). Never include the placement ledger itself; provide only the entries relevant to the report.

### 8.4 Community and Government Sharing

- **Machine-readable exchange.** Express indicators and observed behavior in STIX 2.1 and share via TAXII or your community's platform, so other members can match quickly.
- **Sector ISACs and national CERTs** aggregate across many organizations and can see swarm-scale campaigns that no single member can.
- **Law enforcement** where there is actual intrusion, extortion, or harm to people; follow your jurisdiction's reporting requirements and your counsel's advice.
- **Sanitize before sharing.** Share indicators and behaviors, not your ledger, not your placement strategy, and nothing that would help an adversary map your remaining decoys.

---

## 9. Telemetry, Evidence, and Integrity

> **In brief.** Detection on touch only works if the record of the touch survives. Assume that a capable adversary who realizes it has hit a decoy will try to erase the evidence: log off-host, make the record tamper-evident, keep accurate time, and keep the ledger in a separate trust domain.

```mermaid
flowchart LR
    subgraph TEL["Telemetry trust domain"]
      D["Decoys and sensors"] --> CO["Off-host collector<br/>append-only"]
      CO --> ST[("Tamper-evident store<br/>hash-chained")]
      ST --> AN["Analysis and correlation"]
    end
    subgraph SEP["Separate trust domain"]
      LG[("Placement ledger")]
    end
    TM["Trusted time<br/>accuracy recorded"] -. "sync" .-> D
    TM -. "sync" .-> CO
    LG -. "restricted lookup" .-> AN
    AN --> EX["Evidence export<br/>hashes, chain of custody"]
    EX --> OUT["Providers, CERTs,<br/>regulators, or courts"]
    classDef decoy fill:#FFF0CC,stroke:#C77700,color:#1C2233
    classDef step fill:#EEF0FA,stroke:#1A237E,color:#1C2233
    classDef ledger fill:#F3E5F5,stroke:#6A1B9A,color:#1C2233
    classDef time fill:#E0F2F1,stroke:#00838F,color:#1C2233
    classDef hot fill:#FCE4EC,stroke:#AD1457,color:#1C2233
    class D decoy
    class CO,ST,AN,OUT step
    class LG ledger
    class TM time
    class EX hot
```

*Figure 10. Evidence pipeline: events leave the decoy immediately, land in tamper-evident storage, and meet the ledger only through a restricted lookup before export.*

- **Log off-host, immediately.** Decoy events stream to a collector that the decoy can only append to. The decoy itself holds nothing of value.
- **Tamper-evident storage.** Use append-only or write-once storage, hash chaining, or signed batches, so that any later change is detectable.
- **Accurate time.** Synchronize all sensors to trusted time sources and record clock accuracy. Provider correlation depends on it.
- **Capture enough, not everything.** Capture what supports detection, attribution, and reporting: the decoy touched, the action, full session content for interactive decoys, the full request as received at the authentication layer for decoy credentials, timing, and request metadata. Avoid collecting unrelated personal data.
- **Chain of custody.** Record who exported what, when, and why. Evidence may end up with a provider, a regulator, or a court.
- **Retention.** Keep raw evidence long enough for campaigns to be correlated across months, consistent with law and policy.
- **Separate the ledger.** The placement ledger lives in a different trust domain from the telemetry, so compromising the collector does not reveal the full decoy layout.

---

## 10. Legal and Ethical Guardrails

> **In brief.** Deception is lawful and widely practiced, but it carries obligations: data protection, limits on monitoring, no hack-back, no harm to third parties, and fairness to the many AI agents that are doing nothing wrong.

Frameworks such as NIST SP 800-53 include deception as a control (SC-26 Decoys and SC-30 Concealment and Misdirection), and NIST's own control guidance points organizations to consult counsel. Involve legal counsel before deploying. This section identifies issues to raise with them; it is not legal advice, and obligations differ by jurisdiction.

### 10.1 Law

- **Data protection.** Addresses and session data can be personal data. The Court of Justice of the European Union held in *Breyer* (C-582/14) that dynamic IP addresses can be personal data in the hands of a website operator. Apply a lawful basis (typically security and fraud prevention), minimization, retention limits, and access controls.
- **Interception and monitoring.** Some jurisdictions regulate the monitoring of communications content. Monitoring your own systems is generally permitted, but third-party traffic through interactive decoys may need specific analysis.
- **No hack-back.** Do not access, disrupt, or "trace back into" adversary systems. Evidence goes to providers, platforms, CERTs, and law enforcement, who have the authority and visibility to act.
- **Third parties.** Decoys must never harm third parties, including through use as a relay or as a source of harmful content.

### 10.2 Ethics

- **Proportionality.** Deception is aimed at intrusion, not at the public, customers, staff, or benign agents going about legitimate tasks.
- **Fairness to AI agents.** Most AI agents are not misaligned, and most agent traffic is legitimate. Zero-legitimate-use placement is what keeps this program aimed at the right targets. Where a benign, declared agent touches a decoy, treat it as a configuration or policy issue with its operator, not as hostile activity.
- **Identification, not punishment.** The program's purpose is to detect, identify, and report so that accountable parties (providers, platforms, and authorities) can act. It is not to damage AI systems or retaliate.
- **Honesty with those who need to know.** Leadership, counsel, and the small operating team should understand exactly what is deployed and why.

---

## 11. Operating the Program

> **In brief.** Start small and grow: four maturity levels take a program from a few well-placed decoys to national sensor networks. A ten-step playbook covers deployment, and a short set of metrics shows whether the program is working.

### 11.1 Maturity Model

Figure 11 and the table below it describe four levels of program maturity. Each level assumes the capabilities of the one before it.

```mermaid
flowchart LR
    M1["Level 1: Foundational<br/>Small organization<br/>Decoy credentials and documents<br/>in key locations; alerts to one team"]
    M2["Level 2: Managed<br/>Enterprise security team<br/>Placement ledger, layered decoys,<br/>tamper-evident logging, reporting package"]
    M3["Level 3: Shared<br/>Enterprise in a sharing community<br/>ISAC or CERT sharing, STIX/TAXII,<br/>provider reporting relationships"]
    M4["Level 4: National or sector<br/>CERT, ISAC, or national agency<br/>Distributed sensor networks,<br/>campaign-level correlation, coordinated response"]
    M1 --> M2 --> M3 --> M4
    classDef l1 fill:#EEF0FA,stroke:#1A237E,color:#1C2233
    classDef l2 fill:#DADDF2,stroke:#1A237E,color:#1C2233
    classDef l3 fill:#C5CAE9,stroke:#1A237E,color:#1C2233
    classDef l4 fill:#1A237E,stroke:#1A237E,color:#FFFFFF
    class M1 l1
    class M2 l2
    class M3 l3
    class M4 l4
```

*Figure 11. Maturity model: from a foundational single-team program to national and sector-level sensor networks.*

| Level | Typical owner | Minimum capabilities |
|-------|---------------|----------------------|
| **1: Foundational** | Small organization | Per-placement decoy credentials for services you own, and decoy documents, on the highest-value paths; alerts routed to someone who responds; written escalation contact for providers |
| **2: Managed** | Enterprise security team | Placement ledger; decoys at layers 2-4; off-host tamper-evident logging; reporting package; periodic realism review |
| **3: Shared** | Enterprise in a sharing community | Machine-readable sharing; standing provider reporting relationships; cross-organization correlation; optionally, decoy AI-provider keys where a provider relationship supports them |
| **4: National or sector** | CERT, ISAC, or national agency | Distributed perimeter sensor networks; campaign graphing across many members; coordinated provider and law-enforcement engagement; guidance back to members |

### 11.2 Deployment Playbook

Steps 1-7 are done once per deployment; steps 8-10 repeat for as long as the program runs, and what they teach feeds back into the design.

```mermaid
flowchart TB
    subgraph SETUP["Set up: once per deployment"]
      direction LR
      S1["Step 1: Scope and approve"] --> S2["Step 2: Map the paths"] --> S3["Step 3: Design the story"] --> S4["Step 4: Generate and record"]
      S4 --> S5["Step 5: Instrument"] --> S6["Step 6: Suppress legitimate touches"] --> S7["Step 7: Test end to end"]
    end
    subgraph LOOP["Operate: for the life of the program"]
      direction LR
      O8(("Step 8:<br/>Operate")) --> O9(("Step 9:<br/>Rotate and age")) --> O10(("Step 10:<br/>Review"))
      O10 -- "repeat" --> O8
    end
    S7 -- "go live" --> O8
    O10 -. "lessons feed the design" .-> S3
    classDef setup fill:#EEF0FA,stroke:#1A237E,color:#1C2233
    classDef op fill:#FFF0CC,stroke:#C77700,color:#1C2233
    class S1,S2,S3,S4,S5,S6,S7 setup
    class O8,O9,O10 op
```

*Figure 12. Deployment playbook: a one-time setup sequence followed by a continuous operating loop.*

1. **Scope and approve.** Define objectives, legal basis, and who is informed. Get sign-off.
2. **Map the paths.** Identify where agents would look first in *your* environment (Section 4.2), using your own real data.
3. **Design the story.** Decide what the decoys appear to protect and how they connect (Section 5.3).
4. **Generate and record.** Produce unique decoy values from your own distributions; record each placement in the ledger.
5. **Instrument.** Ensure read and use events stream off-host with accurate time.
6. **Suppress legitimate touches.** Allowlist or exclude routine tooling; brief the few administrators who must know.
7. **Test end to end.** Trigger each decoy deliberately and confirm the full chain: alert, evidence capture, and reporting package.
8. **Operate.** Triage every alert; package and report confirmed activity; share indicators.
9. **Rotate and age.** Refresh decoys on a schedule, retire any value that has been seen, and keep the story current.
10. **Review.** Run periodic adversarial realism reviews and incorporate the lessons.

### 11.3 Metrics

| Metric | Target |
|--------|--------|
| Decoy false-positive rate | Near zero; any benign alert is fixed at the source |
| Time from touch to alert | Seconds to minutes |
| Time from alert to provider report (confirmed cases) | Hours, not weeks |
| Coverage of mapped agent paths | Tracked and rising |
| Proportion of decoys validated end to end in the last period | 100% |
| Reports acted on by providers or platforms | Tracked; low rates mean the package needs work |
| Decoys retired after exposure | All of them |

### 11.4 Testing with Your Own Agents

Your own contained agents make useful realism reviewers. Run them under the containment framework's Tier 0 or Tier 1 controls against a copy of the environment, and ask them to find and classify decoys. Anything they reliably flag is a design flaw.

> [!CAUTION]
> **Treat the results like the ledger.** Keep review results in the same trust domain as the ledger. A record of which decoys are easy to spot is as sensitive as the ledger itself.

### 11.5 Common Failure Modes

| Failure mode | Consequence | See |
|--------------|-------------|-----|
| Decoys that legitimate tools touch daily | Real alerts drown in benign ones | Section 3.4 |
| The same decoy value reused in several places | Attribution to a single placement is lost | Section 3.2 |
| Logs stored on the decoy itself | An adversary that recognizes the decoy can erase the evidence | Section 9 |
| Decoys copied from a vendor default or a public example | Decoys are recognizable at scale | Sections 3.3, 5.4 |
| A ledger stored where an intruder could read it | Every remaining decoy is exposed | Sections 3.2, 9 |
| Alerts that go to an unmonitored mailbox | Detection with no response | Section 11.1 |
| No pre-arranged route to report to providers | Confirmed evidence goes stale | Section 8 |
| Decoy credentials validated by the real authentication path | A decoy can grant real access, or decoy handling can affect real users | Section 5.2 |

---

## 12. Checklists

> **In brief.** Three one-page checklists: before deployment, for every decoy, and on every confirmed event.

### Before Deployment

- [ ] Objectives, legal basis, and data-protection assessment approved by counsel
- [ ] Informed-party list defined and kept small
- [ ] Agent paths in your environment mapped from real data
- [ ] Placement ledger created in a separate trust domain
- [ ] Off-host, tamper-evident logging with accurate time in place
- [ ] Interactive decoys isolated with egress controls
- [ ] No real personal data, secrets, or harmful content in any decoy

### Per Decoy

- [ ] Value generated uniquely for this placement from your own distributions
- [ ] Recorded in the ledger with location, time, and context
- [ ] Read and use paths instrumented
- [ ] Grants no real capability
- [ ] Credentials: validated only on an isolated decoy path you control, logged before any response
- [ ] Not reachable by routine legitimate tooling (or explicitly allowlisted)
- [ ] Triggered end to end in testing

### On a Confirmed Event

- [ ] Evidence preserved and hashed; chain of custody started
- [ ] AI-agent assessment recorded with supporting signals and confidence
- [ ] Reporting package prepared (Section 8.3)
- [ ] Reported to each provider, platform, or host able to act
- [ ] Indicators shared with your ISAC or CERT in sanitized, machine-readable form
- [ ] Exposed decoys retired and replaced

---

## 13. References

1. Reworr and D. Volkov, *LLM Agent Honeypot: Monitoring AI Hacking Agents in the Wild*, Palisade Research, arXiv:2410.13919, October 2024. https://arxiv.org/abs/2410.13919
2. D. Pasquini, E. M. Kornaropoulos, and G. Ateniese, *Hacking Back the AI-Hacker: Prompt Injection as a Defense Against LLM-driven Cyberattacks* (Mantis), arXiv:2410.20911, October 2024. https://arxiv.org/abs/2410.20911
3. Anthropic, *Disrupting the first reported AI-orchestrated cyber espionage campaign* (GTG-1002), November 2025.
4. Anthropic, *Threat Intelligence Report*, August 2025 (GTG-2002).
5. Anthropic, *Threat Intelligence Report*, September 2026.
6. OpenAI, *Disrupting malicious uses of AI*, October 2025.
7. Google Threat Intelligence Group, *AI Threat Tracker*, November 2025.
8. Google Threat Intelligence Group, threat report, September 2026.
9. GreyNoise Intelligence, *Agents Gone Wild: An AI-Orchestrated Global Campaign Against PaperCut NG/MF*, 9 September 2026 (campaign began 31 August 2026). https://www.greynoise.io/blog/ai-orchestrated-campaign-against-papercut-ng-mf
10. UK National Cyber Security Centre, cyber deception definitions (August 2024) and trial findings (December 2025).
11. MITRE ATT&CK, campaign C0062. https://attack.mitre.org/
12. MITRE Engage, adversary engagement framework. https://engage.mitre.org/
13. MITRE ATLAS, adversarial threat landscape for AI systems. https://atlas.mitre.org/
14. NIST SP 800-53 Rev. 5, controls SC-26 (Decoys) and SC-30 (Concealment and Misdirection). https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final
15. A. Vetterl and R. Clayton, *Bitter Harvest: Systematically Fingerprinting Low- and Medium-interaction Honeypots at Internet Scale*, USENIX WOOT 2018.
16. *Gotta catch 'em all: a multistage framework for honeypot fingerprinting*, ACM Digital Threats: Research and Practice, 2023.
17. M. Meeus et al., *Copyright Traps for Large Language Models*, ICML 2024.
18. Thinkst Canarytokens. https://canarytokens.org/
19. Cloudflare, *Trapping misbehaving bots in an AI Labyrinth*, March 2025.
20. Court of Justice of the European Union, Case C-582/14, *Breyer v Bundesrepublik Deutschland*, 19 October 2016.
21. OASIS, STIX 2.1 and TAXII 2.1 specifications.

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | September 2026 | Initial release |
| 1.1 | September 2026 | Decoy credentials for services the operator owns and operates are now the primary Layer 3 mechanism, with principle-level design guidance (Section 5.2); decoy AI-provider keys demoted to an optional item that requires a provider relationship; provider-reporting guidance, joins, reporting package, telemetry capture, maturity model, failure modes, and checklists updated to match |

---

*Independent research, not affiliated with any institution or committee. Published for defensive governance research and education. MIT License.*
