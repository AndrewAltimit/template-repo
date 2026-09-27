# Projection Reports: Emerging Technology Risk Assessment

This directory contains scenario-based projection reports analyzing potential futures involving advanced AI systems and their societal impacts. These are independent analyses, not affiliated with any government agency, think tank, or official institution. The "ETRA" branding is a document formatting convention, not an organizational identity.

## Purpose

These projections serve defensive policy analysis:

1. **Threat anticipation** - Understanding risks before they fully materialize
2. **Institutional preparation** - Enabling proactive adaptation
3. **Policy development** - Informing regulatory and governance frameworks
4. **Research prioritization** - Identifying critical areas for further study

## Scope and Limitations

- All projections analyze capabilities and trends, not operational details
- Documents explicitly omit information that could enable harm
- Analysis draws on publicly available academic and policy literature
- Uncertainty is inherent; multiple scenarios are presented where appropriate
- Shared methodology and calibration conventions: [methodology.md](./methodology.md)

## Reports

| Report | Topic | Version | PDF | Source |
|--------|-------|---------|-----|--------|
| AI Agents Political Targeting | AI agents and political violence risk | 3.0 (Sep 2026) | [Download PDF](https://github.com/AndrewAltimit/template-repo/releases/latest) | [Markdown](./ai-agents-political-targeting.md) \| [LaTeX](./latex/ai-agents-political-targeting.tex) |
| AI Agents WMD Proliferation | AI agents and WMD proliferation risk | 3.0 (Sep 2026) | [Download PDF](https://github.com/AndrewAltimit/template-repo/releases/latest) | [Markdown](./ai-agents-wmd-proliferation.md) \| [LaTeX](./latex/ai-agents-wmd-proliferation.tex) |
| AI Agents Espionage Operations | AI agents and intelligence tradecraft | 3.0 (Sep 2026) | [Download PDF](https://github.com/AndrewAltimit/template-repo/releases/latest) | [Markdown](./ai-agents-espionage-operations.md) \| [LaTeX](./latex/ai-agents-espionage-operations.tex) |
| AI Agents Economic Actors | AI agents as autonomous economic actors | 3.0.1 (Sep 2026) | [Download PDF](https://github.com/AndrewAltimit/template-repo/releases/latest) | [Package](../../packages/economic_agents) \| [LaTeX](./latex/ai-agents-economic-actors.tex) |
| AI Agents Financial Integrity | AI agents and financial system integrity | 3.0 (Sep 2026) | [Download PDF](https://github.com/AndrewAltimit/template-repo/releases/latest) | [Markdown](./ai-agents-financial-integrity.md) \| [LaTeX](./latex/ai-agents-financial-integrity.tex) |
| AI Agents Institutional Erosion | AI agents eroding IC monopolies | 3.0 (Sep 2026) | [Download PDF](https://github.com/AndrewAltimit/template-repo/releases/latest) | [Markdown](./ai-agents-institutional-erosion.md) \| [LaTeX](./latex/ai-agents-institutional-erosion.tex) |

**Build Status**: [![Build Documentation](https://github.com/AndrewAltimit/template-repo/actions/workflows/build-docs.yml/badge.svg)](https://github.com/AndrewAltimit/template-repo/actions/workflows/build-docs.yml)

All six reports were revised to v3.0 in September 2026 (research refresh through mid-September 2026, rewritten analysis, updated scenario probabilities and indicator dashboards, and new figures). Each report's revision history lists the substantive changes.

PDFs are automatically compiled from LaTeX source and published with each [release](https://github.com/AndrewAltimit/template-repo/releases). Individual build artifacts are also available from the [Build Documentation workflow](https://github.com/AndrewAltimit/template-repo/actions/workflows/build-docs.yml).

## Methodology

The projection methodology draws on:

- **Trend extrapolation** from current AI capabilities
- **Historical case analysis** of technology-society interactions
- **Institutional behavior modeling** based on past adaptations
- **Synthesis of published expert analysis** across relevant domains
- **Published red-team and evaluation results** (frontier-lab system cards, public benchmark research)

These are independent, single-author analyses: they involve no first-party expert consultation and no red-team exercises conducted by or for the author.

These reports aim to be concrete and specific while acknowledging uncertainty. Probability estimates are provided where appropriate.

The conventions shared by all six reports (epistemic status markers, the calibration policy below, base-rate anchoring, actor tiers, and the series-wide non-claims) are collected in the [ETRA Shared Methodology](./methodology.md). Each report summarizes them briefly and keeps its domain-specific methodology in place.

### Probability Calibration Policy

- **What the numbers are.** Scenario probabilities are single-author subjective judgments. They are not model outputs, forecasting-tournament aggregates, or elicited expert estimates, and they are meant for relative prioritization.
- **Resolution.** Estimates are held on a coarse 5-percentage-point grid. Estimates at or above 10% are reported as ranges (typically the grid midpoint plus or minus 5 points, for example 35-45%); estimates below 10% are reported in tail bins (<1%, 1-5%, 5-10%).
- **When a number moves.** A revision records a change only when the author judges the evidence moves the estimate by at least one grid step (5 points at the range midpoint) or, for tail estimates, into a different bin. Smaller shifts are recorded as "unchanged (within calibration resolution)", and every recorded change states its reason.
- **Partitions.** Where a report's core scenarios are mutually exclusive, range midpoints sum to 100%. A report that computes its partition arithmetically may show points so the arithmetic can be checked, and says which moves are at resolution.
- **History.** Values from v2.1 and earlier are kept in revision tables as published; some of those revisions recorded moves smaller than one grid step.

The full policy is in [methodology.md](./methodology.md#3-probability-calibration-policy).

### Independence and Limits

- **Single author, no elicitation.** Each report is the work of one author. No outside experts were interviewed or surveyed, and "expert judgment" in the reports means the author's inference from published expert work.
- **AI-assisted drafting.** Drafting, editing, and consistency checks were assisted by AI systems; the author is responsible for every claim, estimate, and citation.
- **Public sources only.** No classified, proprietary, or non-public incident data was used.
- **Verify recent citations.** Citations to sources dated after 2025 describe a fast-moving record. Readers should independently verify any such citation before relying on it, and treat a claim whose source cannot be located as unsupported.

## Classification

These documents are for policy, security, and research audiences engaged in defensive analysis. They are intended for audiences with appropriate context.

## Disclaimer

These documents are published for defensive policy research and education. The author does not provide guidance, consultation, or briefings on any topic covered in these reports. Feature requests, topic suggestions, and engagement requests will not be accepted regardless of compensation. The author may ignore public comments, inquiries, and news coverage related to these reports to maintain neutrality and legal distance. See [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Related Resources

- `docs/agents/` - AI agent documentation for this repository
- `docs/philosophy/` - Philosophical explorations of AI minds and experience
- `packages/sleeper_agents/` - Defensive AI safety research (implementation-focused)
- External: AI safety research organizations, policy think tanks

---

*Independent research, not affiliated with any institution or committee*
