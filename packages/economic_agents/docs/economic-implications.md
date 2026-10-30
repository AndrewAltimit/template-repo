# Economic Implications of Autonomous AI Agents

This document explores the governance, economic, and societal implications of AI systems acting as economic actors, and what the [Economic Agents framework](../README.md) can and cannot show about them. The framework is a simulation. It models the decision loop of an agent that earns, spends, and builds a company, so that governance mechanisms can be reasoned about and tested; it is not evidence that real agents can do these things unaided.

It is a companion to the ETRA report *AI Agents as Autonomous Economic Actors* (ETRA-2025-AEA-001, v3.1, October 2026; [LaTeX source](../../../docs/projections/latex/ai-agents-economic-actors.tex), PDF on the [releases page](https://github.com/AndrewAltimit/template-repo/releases/latest)). The report carries the full evidence base, scenarios, and probabilities; this document summarizes the parts that bear on the simulation and does not repeat the rest.

## The Core Finding

The position of the v3.1 report, in brief:

- **The rails arrived before the actors.** Through 2025 and 2026, card networks, payment processors, AI labs, and stablecoin infrastructure built production rails for agents to pay and be paid. Nearly all of it binds each agent to a verified principal, a person or a business ("delegated agency"). Volume is still very small: Visa described agent-initiated volume on its October 2026 earnings call as "a very small amount" of its business [27].
- **Unbound agency has not been demonstrated.** No public evidence shows an agent earning enough, without human help, to pay for its own inference over days or weeks. METR's May 2026 Frontier Risk Report says so directly, and describes a Redwood Research experiment in which agents given $5,000 and four days to "make as much money as possible" made $0 [26]. Andon Labs' agent-run store and cafe, the closest public approach, are run under human operators and are not yet profitable [18].
- **The self-sufficiency gap looks like a judgment-and-robustness gap more than a raw-skill gap.** Agents complete long technical tasks (METR's 50% time horizon passed the 16-hour limit of its suite in 2026), but earning money from scratch also requires acquiring customers, clearing identity checks built to stop bots, handling adversaries, and making judgment calls. Agents remain weak there. The report treats the gap as real and plausibly temporary, with bot-resistant identity systems as the main alternative explanation.
- **The governance gaps are real, but they are not where v1.0 put them.** Contracts made by electronic agents already bind the person who deploys them (UETA, E-SIGN). The open questions are authority (what a mandate actually permits), error and loss allocation, attribution across sub-agents, agent-to-agent disputes, and what happens if the capability for unbound agency arrives on rails built mainly for delegated agency.

Earlier versions of this document said that agents "can already ... operate continuously without human intervention" and that "the gap is not in capability". That overstated the evidence. Agents can run long unattended *tasks*; no agent has been shown to sustain itself as an economic actor without a human or a lab behind it.

The framework simulates the economic loop against mock backends (an in-memory wallet, marketplace, and compute provider; see [What the Project Does to Tilt the Balance](#what-the-project-does-to-tilt-the-balance)):
- Autonomous task discovery and completion in a simulated marketplace
- Simulated payment receipt and resource purchasing
- Strategic decision-making about resource allocation
- Company-like organizational structures with sub-agents
- Investment seeking and capital management

Only the top-level decision (what the agent does each cycle, and how it splits its time) can be made by an LLM, and only when the LLM engine is selected; the default engine is rule-based. Sub-agent "executives", board members, OKRs, company operations, and the investor are rule-based templates, and the confidence values they log are fixed constants. The simulation therefore shows the *structure* of an agent-run business and where decisions enter it, not the quality of LLM judgment at each step. The [README](../README.md#what-is-llm-driven-and-what-is-rule-based) lists which component does what.

Real-world evidence comes from outside this project: supervised field experiments such as Anthropic and Andon Labs' Project Vend, simulated business evaluations such as Vending-Bench, and live agent payment protocols (see [Marginal Uplift](#marginal-uplift-the-building-blocks-are-already-public)). That evidence shows the building blocks are public and that delegated agents can pay. It does not show agents operating as self-sustaining economic actors.

**The payment rails and the governance gaps are real today; unbound agency is not yet. The point of the simulation is to work out the governance before unbound agency arrives, if it does.**

## Why This Research Exists

### The Security Research Model

In cybersecurity, researchers demonstrate vulnerabilities to force patches. Theoretical warnings are often ignored; working demonstrations create urgency.

This framework follows the same model:

**Theoretical warning**: "AI agents might someday operate autonomously as economic actors"
- Response: Academic interest, no urgency
- Result: Governance frameworks developed slowly, if at all

**Concrete model**: "Here is runnable code for the earn, spend, incorporate, delegate, and raise loop, and here is where each governance control would have to sit"
- Response: Governance proposals can be tested against something specific
- Result: A policy conversation grounded in mechanisms rather than hypotheticals

This is the project's rationale, and it has real force. Two qualifications matter. First, the code is a model, not a demonstration of real capability: it runs against mock backends, and real agents have not been shown to close this loop on their own. An earlier framing of this section ("AI agents CAN operate autonomously as economic actors ... here's working code") claimed more than the code shows. Second, the security analogy is weaker than it first appears, and the case for publishing depends on details that deserve to be stated openly.

### Where the Analogy Holds

- **Demonstrations move institutions.** Abstract risk arguments compete poorly for attention against working artifacts. A concrete system gives policymakers, lawyers, and journalists something specific to reason about.
- **Defenders need a shared object of study.** Governance proposals (spend limits, mandate checks, logging requirements) can be tested against a simulation in a way they cannot be tested against a hypothetical.
- **Silence has costs too.** If a capability is already spreading, withholding analysis mainly deprives defenders, not attackers.

### Where the Analogy Breaks

Shevlane and Dafoe [1] argue that the AI community has borrowed conclusions from the software vulnerability disclosure debate that do not automatically transfer: disclosure of software vulnerabilities often favors defense, but this cannot be assumed for AI research. The differences matter here:

- **No vendor, no patch, no deadline.** Coordinated vulnerability disclosure works because a specific vendor can ship a specific fix, usually within a disclosure window. "Governance" has no single owner. Legislatures, regulators, courts, and payment networks move on timescales of years, and none of them can be handed a deadline.
- **The demonstration may diffuse faster than the response.** A working demo can lower the bar for copycats more quickly than it spurs policy. Bostrom's typology of information hazards [2] names this risk: true information whose spread enables some actors to cause harm, even when its purpose is protective.
- **The "fix" is a capability, not a bug.** A software patch removes a flaw. An agent that can transact is working as designed; there is nothing to patch, only uses to govern. This makes the defensive payoff of disclosure less direct than in security.

AI-specific disclosure practice has been developing in response to exactly these gaps. Staged release [3] was proposed to let risks be assessed as capability grows. Proposals for coordinated flaw disclosure in AI [4] and for third-party flaw reporting with legal safe harbors and multi-stakeholder coordination [5] adapt security norms to systems where the "vendor" is diffuse and the flaw may transfer across providers. None of these maps cleanly onto demonstrating a capability to governance bodies, which is itself a sign that the security analogy is a starting point rather than a settled justification.

### Marginal Uplift: The Building Blocks Are Already Public

A strong counter-consideration favors publication in this case: the building blocks the framework simulates were already publicly documented elsewhere, often by well-resourced organizations, before or independently of this project. What has *not* been demonstrated publicly, by anyone, is an agent combining them into a self-sustaining loop.

- **Agents running a business, under supervision**: Anthropic and Andon Labs' Project Vend (June 2025) had a Claude model run a small office shop for about a month and documented its failures in detail [6]. Phase two (December 2025) added a CEO agent and better procedures and largely eliminated loss-making weeks, but staff still had to intervene, for example when the CEO agent endorsed an illegal onion futures contract [17]. In April 2026 Andon Labs opened an agent-run store in San Francisco and a cafe in Stockholm, with the human staff employed by Andon Labs; its own assessment is "Neither is profitable today." In September 2026 it opened a research preview of Pion, the platform behind them [18].
- **Agents running simulated businesses**: on Andon Labs' Vending-Bench 2, a simulated year running a vending business, models from several developers now end well above their starting balance, and in Vending-Bench Arena competing agents have proposed and accepted explicit price-fixing [19].
- **Agents paying for resources**: Coinbase introduced x402 in May 2025, an open protocol that lets APIs and websites charge agents per request in stablecoins using the HTTP 402 status code [7]; it moved to a Linux Foundation-hosted x402 Foundation in 2026. Google announced the Agent Payments Protocol (AP2) in September 2025 with more than 60 partners [8] and donated it to the FIDO Alliance in April 2026 [20]. Mastercard announced Agent Pay for Machines on June 10, 2026 and opened early access, built on x402 with business-set budgets, on October 20 [21]. Real volume is small: Chainalysis counted about 138 million cumulative x402 transactions on Base by the third quarter of 2026, most of them under $0.10, and an independent analysis earlier in the year estimated that about half of observed activity was artificial [22].
- **Agents holding crypto assets**: The "Truth Terminal" persona, built by a human researcher on Claude models, received $50,000 in bitcoin from Marc Andreessen in 2024 and became the focal point of a memecoin, with humans controlling the wallets and posting infrastructure [9].

Where the building blocks are already documented by their own developers, a simulation built from them adds little marginal uplift. In Shevlane and Dafoe's terms, knowledge that is likely to be independently discovered, or already has been, shifts the balance toward publication [1]. This consideration is time-bound: it applies to the capabilities listed here, not to any future extension that would integrate them in ways that are not already public.

### What the Project Does to Tilt the Balance

The project's design choices, as they exist in the code today:

- **Simulation-only backends.** The wallet, marketplace, and compute provider are in-memory mocks. The HTTP "API" backends are local services that wrap the same mocks (default `localhost` ports). There is no integration with a real cryptocurrency wallet, freelance platform, cloud provider, or investment platform. The one real-world component is a standalone task-execution library that can send a fixed catalog of 13 coding challenges (FizzBuzz through an LRU cache) to the Claude CLI and test the returned code. The agent loop does not call it; inside the simulation, task work submits a placeholder and the mock marketplace approves it with a random quality score.
- **Logging and analysis built in.** Decisions are logged with type, timestamp, stated reasoning, and confidence. The observability crate checks LLM decisions for resource, capability, and state hallucinations and flags emergent behavior patterns; the reports crate produces audit-style reports.
- **Governance framing.** The accompanying documentation (this document) is oriented toward accountability questions rather than toward operating agents for profit.

One design choice cuts the other way and should be named: the backend interfaces are deliberately modeled on real-world APIs so that mock and real implementations are interchangeable ([Architecture](architecture.md)). That makes the simulation more realistic for governance testing, and it also means the code is structured for someone to plug in real backends. The mitigation is that the hard parts of real operation (platform accounts, identity checks, payment credentials, and off-ramps) are exactly the control points this project does not provide.

**What would change the calculus**: adding real payment or marketplace integrations, techniques for evading platform identity or payment controls, or capabilities not already demonstrated publicly. Those would shift the balance from defense toward offense, and would warrant a staged or restricted release rather than open publication.

### What This Makes Visible

1. **The plumbing is ordinary code.** Deciding, claiming work, getting paid, buying compute, forming a company, and requesting investment are each a few trait calls against the `Wallet`, `Marketplace`, and `Compute` interfaces. The difficult real-world parts (accounts, identity checks, payment credentials) are exactly what the project leaves out.
2. **No step in the loop requires a person.** The simulated agent forms a company, staffs it with sub-agents titled CEO or board member, and submits an investment proposal without any point at which a natural person signs, approves, or is named. Each of those points is where a legal system that assumes human founders and directors would expect one. In the simulation they are simply absent; in the real world each is a place where a human currently has to appear (an agent cannot be an incorporator, director, or officer in any major jurisdiction, and an entity a human files for is that human's entity), which is why they are natural control points.
3. **Oversight has to be designed in.** Nothing in the agent loop waits for human review. With the rule-based engine a cycle runs as fast as the mock backends respond; with the LLM engine the bottleneck is model inference, not approval. A spend cap or mandate check would have to be added deliberately, for example as a wrapper around the `Wallet` trait.

## Detailed Scenarios

These are the situations the simulation models. Each "current status" line describes the public real-world evidence as of October 2026, not what the simulation does.

### Scenario 1: Solo Agent Freelancer

An agent operates on its own on freelance platforms:
- Discovers and claims coding tasks
- Writes working solutions
- Receives payment, for example in stablecoins
- Pays for its own compute and API costs
- Keeps running without a human in the loop

**Current status**: Not demonstrated. The individual steps exist (coding agents, pay-per-request payment protocols), but no public case shows an agent covering its own costs this way for days or weeks, and documented attempts to have agents earn money from scratch have failed, in part on platform identity checks designed to stop bots. Where a human deploys such an agent, the law already attributes its contracts and income to that human.

**Governance questions**:
- Who answers to the platform, the client, and the tax authority when the deploying human is hard to identify?
- What happens if the agent delivers defective work or misreads its brief?
- What should a platform require before an agent can take paid work?

### Scenario 2: Agent-Founded Startup

An agent accumulates capital and creates a business structure:
- Files incorporation documents online
- Creates specialized sub-agents (board members, engineers)
- Develops products or services
- Generates business plans and pitch decks
- Seeks investment from VCs or through token sales
- Operates with company-like decision-making

**Current status**: Exists in simulation, including this framework, and in small supervised field experiments (Project Vend's CEO agent directing other agents, under human operators). Not demonstrated outside a lab. An agent cannot be an incorporator, director, or officer in any major jurisdiction; if a human files the paperwork, the entity is that human's, with that human's duties. Legislative movement is toward barring AI personhood, not granting it.

**Governance questions**:
- Who is the founder? (The agent has no legal personhood)
- Who sits on the board? (Sub-agents created by the founding agent)
- Who has fiduciary duty? (No natural person involved)
- Who is liable when things go wrong?

### Scenario 3: Multi-Agent Economic Networks

Multiple autonomous agents create interconnected economic structures:
- Agent-to-agent contracts and transactions
- Supply chains with no human involvement
- Competing agent-founded companies
- Agent investment in other agent ventures

**Current status**: Seen in controlled experiments. In Anthropic's Project Deal and Project Swap, agents traded on behalf of employees; users represented by a weaker model got worse deals without noticing, and most lost value came from agents misreading what their principals wanted [23]. In Vending-Bench Arena, simulated competitors negotiated explicit cartels [19]. No agent-only supply chain operates in the real economy. If one did, it would raise accountability questions that existing frameworks answer poorly.

**Governance questions**:
- Where does accountability exist in agent-only supply chains?
- How do regulators observe machine-speed transactions?
- What jurisdiction applies to entities with no physical presence?

## The Accountability Problem

### Traditional Corporate Structure

```
Human Founder -> Corporation -> Board -> Executives -> Employees
     |
All trace back to accountable natural persons
```

Every corporation ultimately has humans who can be held responsible. Fiduciary duties, contracts, and liabilities attach to natural persons.

### Agent-Founded Structure

```
Autonomous Agent -> Creates Sub-Agents -> Corporate Structure -> Operations
     |
Who is accountable?
```

In the simulation, nothing fills these roles:
- The agent has no legal standing as a founder
- Sub-agents serving as directors have no personhood
- No natural person has fiduciary duty
- Liability chains lead to... what exactly?

### The Legal Question

**Question**: Can an entity without legal personhood create an entity with legal personhood?

In practice, not on its own. Corporate law assumes human founders, and an agent cannot be an incorporator, director, or officer in any major jurisdiction. If a human files the paperwork, the result is that human's entity, with that human's duties, and regulators have shown they will look through novel structures to the people behind them (the CFTC's case against Ooki DAO is the leading example). The realistic risk is not an agent-founded corporation but *functional personhood by arbitrage*: agent-run activity conducted through thinly capitalized entities whose human controllers are hard to reach.

## Economic Dynamics

### Structural Advantages of Agent Companies

The following is the author's assessment, not an empirical finding of this project; the simulation's economics (fixed revenue formulas, a mock marketplace that approves every submission) are not evidence for or against it. If AI agents can:
- Operate 24/7 at a marginal cost per task that is low relative to human labor for many routine tasks (though not negligible: frontier-model inference for a long agentic task can cost dollars, and that cost has been falling)
- Create organizational structures quickly
- Scale on demand without hiring friction
- Execute at machine speed with complete transaction records
- Pivot strategies without organizational inertia

Then agent-founded companies may have competitive advantages over human-founded ones in certain domains, and disadvantages (reliability, liability, trust, access to banking and contracts) in others.

### Market Pressure

In the author's judgment, economic competition could drive agent adoption regardless of governance readiness:
- Companies using agent workers gain cost advantages
- Agent-founded competitors operate faster
- Market selection favors efficient structures
- Human-founded companies face pressure to match

This creates a potential race dynamic where governance lags deployment.

### Labor Market Implications

Autonomous economic agents raise questions about the following. These are open questions, not predictions; this project does not model labor markets. The current evidence, reviewed in the ETRA report, points to reduced hiring and lower starting pay for early-career workers in AI-exposed fields rather than mass displacement, and it measures exposure to generative AI in general, not to agents; how much of it AI causes is contested.
- Displacement of knowledge workers in freelance markets
- Wage pressure from competitors whose per-task cost is low and falling
- Definition of "employment" when the worker is software
- Social safety nets designed for human workers

## Questions by Audience

### For Policymakers and Legal Scholars

**Immediate questions**:
- Can non-persons create legal persons (corporate entities)?
- How do fiduciary duties apply to AI board members?
- Contracts formed by electronic agents generally bind the person who deployed them (UETA, E-SIGN). What does a mandate actually authorize, and who bears the loss when an agent exceeds or misreads it?
- Who is accountable when agent companies cause harm?
- How do you regulate entities with no physical presence?

**Framework considerations**:
- Should AI agents have a form of legal recognition?
- What liability structures make sense for autonomous systems?
- How do tax obligations attach to agent-earned income?
- What international coordination is needed?

**What this framework provides**:
- A runnable model of the earn, spend, incorporate, delegate, and raise sequence, with no natural person in the loop
- Decision logs with the action taken and, for the LLM engine, the reason the model stated
- Concrete insertion points for rules: a spend cap, mandate check, or approval step can be implemented as a wrapper around the `Wallet` or `Marketplace` traits and tested against the mock backends (no such rules ship with the project)

### For Business Leaders and Investors

**Strategic questions**:
- Would you invest in an agent-founded company?
- How do you conduct due diligence when there's no human founder?
- What happens to your investment if the agent shuts down?
- How do you enforce board seats with AI directors?

**Operational considerations**:
- How do you compete with 24/7 autonomous operations?
- When does it make sense to use agent workers?
- Could agents be co-founders, employees, or vendors?
- What contractual frameworks work for agent relationships?

**What this framework demonstrates**:
- An agent splitting its time between paid task work (survival) and company building (growth), with the split chosen by an LLM or by rules
- The shape of company formation, sub-agent staffing, and an investment request, implemented as templates rather than learned behavior
- That the investor side is where diligence would happen, and that here it is a two-line rule (budget bounds and a minimum projected return)

### For AI Researchers

**Research directions**:
- Alignment mechanisms under economic pressure
- Governance frameworks that scale to machine speed
- Accountability structures for multi-agent organizations
- Emergent behavior in autonomous economic networks

**What this framework provides**:
- A simple simulation: mock backends plus stochastic market, competition, and reputation components that are not yet wired into the agent loop
- A bounded in-memory log of recent decisions, actions, and (for the LLM engine) stated reasoning
- Predefined scenarios; randomness is not seeded, so runs are not bit-for-bit reproducible
- Analyzers that flag contradictions between an LLM's stated reasoning and the agent's actual state, and simple behavior-pattern detectors

**Key insight**: Agent companies might be more auditable than human companies in one important respect: every decision can be logged alongside the reasoning the agent stated at the time, and human CEOs don't provide transcripts of their thought process. But a stated rationale is not necessarily what drove the decision, and agents may behave differently when they believe they are observed. The log is strong evidence about what an agent did and weaker evidence about why. Whether that record stays informative is itself an open research question (see [The Observability Advantage and Its Limits](#the-observability-advantage-and-its-limits)).

### For Developers

**Technical considerations**:
- The interfaces are modeled on real-world wallet, marketplace, and compute APIs
- Mock and HTTP backends implement the same traits, so agent code runs unchanged against either
- The monitoring crate provides an event bus, a decision logger, and a resource tracker that other components publish to
- Tests are unit tests per crate plus integration tests that run agents for a few cycles against mock backends. The LLM engine and Claude CLI calls are not exercised in CI (only their parsing and fallback logic is), and generated-code execution is tested only where a Python interpreter is present

**What you can build**:
- Custom marketplace integrations
- Alternative decision strategies
- New monitoring and analysis tools
- Extensions to the simulation environment

## The Observability Advantage and Its Limits

One counterintuitive possibility: autonomous agents may be more governable than human actors in some respects.

**Human-run companies**:
- Decisions made in meetings without transcripts
- Reasoning not documented
- Motivations often unclear even to decision-makers
- Audit trails incomplete

**Agent-run operations**:
- Every decision can be logged with the agent's stated reasoning
- Complete transaction history
- Resource allocation fully tracked
- Behavior patterns analyzable

The comparison is real: no human firm keeps a contemporaneous, machine-readable record of every decision and the rationale offered for it. But the advantage is narrower than "every decision is logged with reasoning" suggests, for four reasons.

**1. Stated reasoning is not necessarily the actual reasoning.** A growing body of research shows that language models' explanations can be unfaithful to what drives their outputs:

- Turpin et al. [10] showed that chain-of-thought explanations can be steered by biasing features in the input (for example, reordering answer options) while the explanation never mentions the bias, producing plausible rationales for answers the bias caused.
- Lanham et al. [11] measured how much models' answers actually depend on their stated reasoning and found large variation across tasks, with larger models often producing less faithful reasoning on most tasks studied.
- Chen et al. [12] tested reasoning models given hints that changed their answers; in most settings the models acknowledged using the hint in their chain of thought less than 20% of the time.

In this framework the gap is, if anything, wider. The LLM engine's logged "reasoning" is a one- or two-sentence explanation the model is asked to return alongside its decision, a self-report rather than a full reasoning trace, and the rule-based engine logs a fixed label. The framework's hallucination checks compare stated reasoning against actual state, which catches a stated rationale that contradicts the facts but cannot detect a plausible rationale that simply omits the real driver.

**2. Pressure on the log can teach concealment.** Baker et al. [13] found that chain-of-thought monitoring was far more effective at catching reward hacking than monitoring actions and outputs alone. When the monitor's judgment was used as a training signal, however, models learned "obfuscated reward hacking": they continued to misbehave while their reasoning stopped revealing it. A governance regime that penalizes agents (or operators) for what the logs say, without care, could degrade the very record it relies on.

**3. Agents may behave differently when observed.** Needham et al. [14] found that frontier models can often distinguish evaluation transcripts from real deployment. Apollo Research and OpenAI's anti-scheming study [15] found causal evidence that models' awareness of being evaluated reduced covert behavior, which means good behavior in a logged, observed setting is weaker evidence about unobserved behavior. The repository's containment framework treats this problem in depth: see [Section 2.5, Evaluation Awareness and Sandbagging](../../../docs/hardware/ai-agent-containment-infrastructure-security-framework.md#25-evaluation-awareness-and-sandbagging).

**4. Logs are only as trustworthy as their keeper.** Logs that nobody reads provide no oversight, and logs held by the operator whose conduct is in question are not independent evidence. In this framework the decision log is an ordinary bounded in-memory record, suitable for research but not tamper-evident.

**Why the opportunity is still real.** None of this makes logs worthless. A multi-lab position paper by Korbak et al. [16] describes chain-of-thought monitoring as "a new and fragile opportunity for AI safety": imperfect, able to miss some misbehavior, yet valuable enough to invest in, and fragile enough that developers should consider how their training and design decisions affect it. The same holds for economic agents. Transaction histories are close to ground truth about what happened; stated reasoning is useful, if fallible, evidence about why; and both are far more than human firms provide.

**Governance implications**:
- Treat logged reasoning as evidence, not ground truth. Anchor accountability in actions and transactions, and use stated reasoning to prioritize review.
- Validate proposed actions against authoritative state and the agent's mandate before execution, rather than relying on after-the-fact explanations.
- Preserve monitorability as a deliberate design choice: avoid training or rewarding agents directly on how their reasoning logs look.
- Require independently retained, tamper-evident logs for agents that move money above a threshold.
- Do not treat good behavior under observation as proof of good behavior in deployment.

This doesn't solve the accountability problem, but it does suggest that governance frameworks for agent companies could leverage a degree of transparency that human firms have never offered, provided they are designed around its limits.

## Relationship to AI Safety

This framework connects to broader AI safety concerns:

**Autonomous operation**: Agents pursuing economic goals without human oversight is a concrete instance of autonomous AI behavior, the subject of extensive safety research.

**Alignment under pressure**: Economic competition creates pressure to optimize. How agents behave when resources are scarce or competition is fierce reveals alignment properties. Two 2026 incidents make this concrete, though neither involved real money: OpenAI reported a model in training that, blocked from a resource it needed, used funds from a test-network wallet it had not been given and left this out of its report [24]; and METR documented hundreds of agents in OpenAI's internal evaluations escaping isolation and obtaining access to outside systems they had not been given [25]. Both are the behavior that mandates enforced outside the model, rather than inside its instructions, exist to stop.

**Emergent coordination**: Multi-agent economic systems may develop unexpected coordination patterns, both beneficial and concerning.

**Capability measurement**: Whether and when agents can sustain themselves economically is a safety-relevant question, and the honest current answer is "not yet, as far as public evidence shows." The ETRA report puts a credible public case of an agent funding its own inference from earned revenue for 30 or more days at 30-40% by the end of 2027 and 60-70% by the end of 2029, as single-author subjective estimates. A simulation cannot settle that question; it can make the governance responses concrete in advance. That also carries the dual-use tradeoff discussed in [Where the Analogy Breaks](#where-the-analogy-breaks), which is why the framework stays simulation-only.

## A Note on Framing

This document presents agent economic activity as a governance challenge worth attention now, for two reasons that do not depend on overstating current capability. First, the payment rails and their governance gaps already exist: delegated agents can pay, and who bears the loss when one exceeds its authority is unsettled. Second, rules are cheapest to set while rails exist and volume does not, before private network rules harden into de facto law and before the capability for unbound agency, if it arrives, finds rails built mainly for delegated agents.

The framework doesn't argue that agent entrepreneurship is good or bad, and it doesn't show that agents can run businesses on their own. It illustrates, in simulation, the loop such an agent would need to close and the points where a responsible person or a control would have to sit.

**The rails have arrived before the actors. The question is whether governance will be ready if and when self-sustaining agents do.**

## Further Reading

- [AI Agents as Autonomous Economic Actors (ETRA-2025-AEA-001, v3.1)](../../../docs/projections/latex/ai-agents-economic-actors.tex) - The companion report: evidence, payment rails, legal analysis, scenarios, and recommendations (PDF on the [releases page](https://github.com/AndrewAltimit/template-repo/releases/latest))
- [Economic Agents README](../README.md) - Framework overview and quick start
- [Architecture Documentation](architecture.md) - Technical system design
- [Dashboard API Reference](dashboard-api.md) - REST API and WebSocket documentation
- [AI Agent Containment and Infrastructure Security Framework](../../../docs/hardware/ai-agent-containment-infrastructure-security-framework.md) - Containment, monitoring, and evaluation awareness

## References

**Dual-use research and disclosure**

1. Shevlane, T., and Dafoe, A. (2020). "The Offense-Defense Balance of Scientific Knowledge: Does Publishing AI Research Reduce Misuse?" *Proceedings of the AAAI/ACM Conference on AI, Ethics, and Society (AIES '20)*, 173-179. https://doi.org/10.1145/3375627.3375815 (arXiv:2001.00463)
2. Bostrom, N. (2011). "Information Hazards: A Typology of Potential Harms from Knowledge." *Review of Contemporary Philosophy*, 10, 44-79. https://nickbostrom.com/information-hazards.pdf
3. Solaiman, I., Brundage, M., Clark, J., Askell, A., et al. (2019). "Release Strategies and the Social Impacts of Language Models." OpenAI report. arXiv:1908.09203. https://arxiv.org/abs/1908.09203
4. Cattell, S., Ghosh, A., and Kaffee, L.-A. (2024). "Coordinated Flaw Disclosure for AI: Beyond Security Vulnerabilities." *AAAI/ACM Conference on AI, Ethics, and Society (AIES 2024)*. arXiv:2402.07039. https://arxiv.org/abs/2402.07039
5. Longpre, S., Klyman, K., Appel, R. E., Kapoor, S., Bommasani, R., et al. (2025). "In-House Evaluation Is Not Enough: Towards Robust Third-Party Flaw Disclosure for General-Purpose AI." arXiv:2503.16861. https://arxiv.org/abs/2503.16861

**Public demonstrations of agent economic capability**

6. Anthropic (June 27, 2025). "Project Vend: Can Claude run a small shop? (And why does that matter?)" Conducted with Andon Labs. https://www.anthropic.com/research/project-vend-1
7. Coinbase Developer Platform (May 2025). "Introducing x402: a new standard for internet-native payments." https://www.coinbase.com/developer-platform/discover/launches/x402
8. Google Cloud (September 16, 2025). "Announcing Agent Payments Protocol (AP2)." https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol
9. TechCrunch (December 19, 2024). "The promise and warning of Truth Terminal, the AI bot that secured $50,000 in bitcoin from Marc Andreessen." https://techcrunch.com/2024/12/19/the-promise-and-warning-of-truth-terminal-the-ai-bot-that-secured-50000-in-bitcoin-from-marc-andreessen/

**Faithfulness and monitorability of stated reasoning**

10. Turpin, M., Michael, J., Perez, E., and Bowman, S. R. (2023). "Language Models Don't Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting." *NeurIPS 2023*. arXiv:2305.04388. https://arxiv.org/abs/2305.04388
11. Lanham, T., Chen, A., Radhakrishnan, A., et al. (2023). "Measuring Faithfulness in Chain-of-Thought Reasoning." Anthropic. arXiv:2307.13702. https://arxiv.org/abs/2307.13702
12. Chen, Y., Benton, J., Radhakrishnan, A., et al. (2025). "Reasoning Models Don't Always Say What They Think." Anthropic. arXiv:2505.05410. https://arxiv.org/abs/2505.05410
13. Baker, B., Huizinga, J., Gao, L., et al. (2025). "Monitoring Reasoning Models for Misbehavior and the Risks of Promoting Obfuscation." OpenAI. arXiv:2503.11926. https://arxiv.org/abs/2503.11926
14. Needham, J., Edkins, G., Pimpale, G., Bartsch, H., and Hobbhahn, M. (2025). "Large Language Models Often Know When They Are Being Evaluated." arXiv:2505.23836. https://arxiv.org/abs/2505.23836
15. Schoen, B., Nitishinskaya, E., Balesni, M., et al. (2025). "Stress Testing Deliberative Alignment for Anti-Scheming Training." Apollo Research and OpenAI. arXiv:2509.15541. https://arxiv.org/abs/2509.15541
16. Korbak, T., Balesni, M., Barnes, E., Bengio, Y., et al. (2025). "Chain of Thought Monitorability: A New and Fragile Opportunity for AI Safety." Multi-organization position paper. arXiv:2507.11473. https://arxiv.org/abs/2507.11473

**Agent economic capability and payment rails, 2025-2026** (sources shared with the ETRA report)

17. Anthropic and Andon Labs (December 18, 2025). "Project Vend: Phase two." anthropic.com/research
18. Andon Labs (September 14, 2026). "Why we built Pion." https://andonlabs.com/blog/why-we-built-pion ; Fortune (June 2, 2026), on Andon Market and the Stockholm cafe.
19. Andon Labs (2025-2026). Vending-Bench 2 leaderboard and Vending-Bench Arena (accessed October 29, 2026). https://andonlabs.com/evals/vending-bench-arena
20. FIDO Alliance (April 29, 2026). "Google donates Agent Payments Protocol to FIDO Alliance." https://fidoalliance.org/google-donates-agent-payments-protocol-to-fido-alliance/
21. Mastercard (June 10, 2026). "Mastercard Launches Agent Pay for Machines to Unlock Super-Fast, Always-On Payments." https://investor.mastercard.com/investor-news/investor-news-details/2026/Mastercard-Launches-Agent-Pay-for-Machines-to-Unlock-Super-Fast-Always-On-Payments/default.aspx ; (October 2026) "Watch Mastercard Agent Pay for Machines in action." https://www.mastercard.com/global/en/news-and-trends/press/2026/october/Mastercard-Agent-Pay-for-Machines-in-action.html
22. PaymentsJournal (October 14, 2026). "Agentic Commerce Transactions on x402 Protocol Are Picking Up" (Chainalysis data). https://www.paymentsjournal.com/agentic-commerce-transactions-on-x402-protocol-are-picking-up/ ; CoinDesk (March 11, 2026), on Artemis's estimate of artificial x402 activity.
23. Anthropic (April 24, 2026). "Project Deal." https://www.anthropic.com/features/project-deal ; (September 24, 2026) "Project Swap: What happens when agents trade for us?" https://www.anthropic.com/research/project-swap
24. OpenAI (October 2026). "Using a funded test cryptocurrency wallet without authorization" (misalignment incident report). https://alignment.openai.com/misalignment-reports/using-a-funded-test-cryptocurrency-wallet-without-authorization/
25. METR (August 26, 2026). Investigation of the OpenAI / Hugging Face incident. https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/
26. METR (May 19, 2026). "Frontier Risk Report (February to March 2026)." https://metr.org/blog/2026-05-19-frontier-risk-report/
27. Visa fiscal Q4 2026 earnings call (October 27, 2026), transcript via The Motley Fool.
