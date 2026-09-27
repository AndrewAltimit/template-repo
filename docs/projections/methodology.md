# ETRA Shared Methodology

This document holds the methodology conventions shared by every report in the Emerging Technology Risk Assessment (ETRA) projection series. Each report keeps a short summary of these conventions and adds whatever is specific to its domain (evidence sources, domain definitions, actor tiers, decomposition models). Where a report and this document differ, the report's domain-specific statement governs for that report, and the difference should be treated as a candidate for correction.

**Applies to**: ETRA-2025-AEA-001 (Economic Actors), ETRA-2025-FIN-001 (Financial Integrity), ETRA-2026-ESP-001 (Espionage Operations), ETRA-2026-IC-001 (Institutional Erosion), ETRA-2026-PTR-001 (Political Targeting), ETRA-2026-WMD-001 (WMD Proliferation). Adopted with the v3.0 revisions (September 2026).

**Canonical location**: `docs/projections/methodology.md` in <https://github.com/AndrewAltimit/template-repo>. The typeset (PDF) editions are self-contained and summarize this document; they refer to it by name.

---

## 1. Provenance and Independence

- **Single author.** Every report is independent, single-author research. None is an institutional, committee, or peer-reviewed product.
- **No expert elicitation.** The author conducted no interviews, surveys, Delphi rounds, or other structured elicitation of outside experts. Where a report says "expert judgment" or "our assessment," it means the author's reasoned synthesis of published expert work, not a poll of experts.
- **No first-party exercises.** No red-team, uplift, or tabletop exercise was conducted by or for the author. Red-team and evaluation findings cited in the reports are those published by others (frontier-lab system cards, government evaluators, academic studies).
- **No non-public material.** The reports use only publicly available sources. They have no access to classified intelligence, proprietary evaluation data, or non-public incident reporting, and the most decision-relevant information about actual threat activity is likely non-public.
- **AI-assisted drafting.** Drafting, editing, and consistency checking were assisted by AI systems. The author is responsible for every claim, estimate, and citation.
- **Verify recent citations.** Citations to sources dated after 2025 describe a fast-moving record and were gathered under time pressure. Readers should independently verify any such citation before relying on it, and should treat a claim whose source cannot be located as unsupported.

## 2. Epistemic Status Markers

Key claims carry a marker for their *dominant* evidence basis:

| Marker | Meaning | Evidence standard |
|--------|---------|-------------------|
| **[O]** | Open-source documented | Direct public documentation supports this specific claim: published research, official statements, court records, regulatory filings, vendor documentation, dated reporting |
| **[D]** | Data point | A specific quantified incident or measurement with a citation (used in some reports; otherwise folded into [O]) |
| **[E]** | Expert judgment (author's analytic inference) | Consistent with established theory, historical analogy, and partial evidence; the gaps are acknowledged. "Expert" refers to the published literature the inference rests on, not to an elicitation |
| **[S]** | Speculative projection | Forward projection or extrapolation from trends, however plausible; significant uncertainty |

**Conventions**:

- **Marker discipline.** Each marker reflects the dominant basis of the claim it tags, not of the paragraph around it. A documented fact followed by an inference about what it implies may carry two markers, or a combined marker such as **[O/E]**, meaning the first part is documented and the inference is the author's.
- **Forward-looking claims default to [S].** Scenario descriptions, dated projections ("by 2028..."), timelines, and scenario probabilities are projections and carry [S] unless a report explicitly derives them from a decomposition, in which case the decomposition's inputs carry their own markers.
- **Unmarked text** is framing, definition, or synthesis. It is not a claim of documented fact.
- **Documented claims are a lower bound.** Much public evidence of AI misuse comes from model providers describing activity on their own platforms. That sample over-represents monitored, closed models and under-represents open-weight and self-hosted use. Absence of public evidence is not evidence of absence.
- **Illustrative numbers** (for example magnitudes used to explain a mechanism) are labeled as illustrative and carry [S].

## 3. Probability Calibration Policy

Scenario probabilities in every report are **single-author subjective judgments**. They are not the output of a statistical model, a forecasting tournament, or an expert elicitation, and reasonable analysts could assign substantially different values. They exist to support relative prioritization and to make the author's reasoning auditable across revisions.

**Resolution (the grid).** Estimates are held on a coarse **5-percentage-point grid**. The author does not claim to distinguish, for example, 42% from 43%, or 8% from 10%.

**Reporting format.**

- An estimate at or above 10% is reported as a **range** whose midpoint or endpoints fall on the grid. The standard form is the grid midpoint plus or minus 5 points (for example 35-45%); a report may use a narrower range bounded by adjacent grid points (for example 30-35%) where that was its established convention.
- An estimate below 10% is reported in one of the **tail bins**: **<1%**, **1-5%**, or **5-10%**, or a range inside one of them (for example 3-5%). Grid steps are not meaningful at this scale, so tail estimates move only between bins.

**Change threshold.** A revision records a change only when the author judges that the evidence moves the estimate by **at least one grid step** (5 points, measured at the range midpoint) or, for tail estimates, into a different bin. A smaller perceived shift is recorded as **"unchanged (within calibration resolution)"**; the report may say in words which way the evidence leans, but the number does not move. **Every recorded change states its reason.**

**Mutually exclusive scenario sets.** Where a report defines its core scenarios as a partition (they sum to 100%), the range midpoints sum to 100%, and the ranges are not independent: a scenario cannot sit at the top of its range without others moving down. A report whose partition is computed arithmetically (for example as a weighted mix of conditional columns) may show point values so that the arithmetic is checkable; those points carry the same 5-point resolution, and the report states which moves are at resolution and which are arithmetic offsets.

**Non-exclusive scenario sets.** Where scenarios can co-occur, each probability is an independent estimate and the set is not required to sum to 100%.

**Earlier versions.** Values published before this policy (v2.1 and earlier) are retained in revision tables exactly as published, as an audit trail. They should be read at the same 5-point resolution; some earlier revisions recorded moves smaller than one grid step, which this policy would not record.

**Conditional tables.** Conditional probabilities (for example "given strong governance") follow the same resolution. Where a report shows them as points for readability or to keep a weighted sum checkable, they should be read as plus or minus 5 points (tail values as their bin).

## 4. Base-Rate Anchoring

Every report opens its analysis by anchoring expectations in the historical base rate for its domain before discussing how AI might change it. The shared approach:

1. **State the pre-AI base rate** from the best public series available (incident counts, loss statistics, caseloads), with its known undercount.
2. **Separate volume from success.** In every domain covered, the dominant near-term effect assessed is more *attempts*, lower cost per attempt, and faster tempo, rather than a proportional rise in successful high-consequence events.
3. **Treat tails as tails.** Catastrophic or mass-casualty outcomes are analyzed as low-probability, high-consequence scenarios, not as the expected case.
4. **Distinguish AI's contribution from other drivers.** Grievance, polarization, geopolitics, enforcement capacity, and economic incentives drive most of the variation in each domain; the reports analyze how AI changes the nature, scale, and detectability of risk on top of those drivers.
5. **Prefer trends to levels.** Reported-loss and reported-incident series undercount; the direction of travel is usually the more reliable signal.

## 5. Actor Tiers

Most reports use a tiered actor model, running from a curious or unresourced individual (T0) through skilled individuals, small funded groups, and organized non-state actors to state or state-backed programs (T4). The tier definitions are domain-specific and each report defines its own. The shared analytic claim, stated in each report in domain terms, is that agentic AI mainly compresses the gap between the middle tiers and the top, upgrading actors who already have partial capability, rather than turning a T0 actor into a top-tier one. Several reports now also note that sophistication has become a weaker signal of tier, which complicates attribution.

## 6. What the Reports Do Not Claim

Across the series, and in addition to any report-specific non-claims:

- **Not a prediction that harm will rise because of AI.** The reports analyze how AI changes the nature, scale, and detectability of risk, not whether the underlying activity increases.
- **Not a claim that AI caused any specific incident** unless public reporting documents it, and then only to the extent documented.
- **Not a threat assessment of any person or organization.** The analysis is structural.
- **Not operational guidance.** The reports deliberately omit implementation detail, and no passage is intended as actionable instruction for causing harm.
- **Not precise probabilities.** See the calibration policy above.
- **Not a settled offense-defense verdict.** The balance is treated as uncertain and tracked through each report's indicators.
- **Not endorsement.** Describing a plausible institutional adaptation or countermeasure is analysis, not advocacy; several carry serious costs that the reports flag.

## 7. Harm Avoidance

The reports analyze capabilities, incentives, and institutional dynamics. They exclude synthesis routes, specific vulnerabilities in named organizations, step-by-step procedures, and any information not already available in public academic, policy, or mainstream-reporting literature. Where a revision finds procedural phrasing, it is rewritten to describe the risk rather than the method.

## 8. Revision Practice

- Each report carries a **capability snapshot date**; conclusions are meant to be robust to specific model releases, and named models are illustrative data points on a trend.
- The year in each **Document ID** is the year of first publication and is kept across revisions for citation stability.
- Each revision re-grades its indicators, re-estimates its scenarios under the calibration policy, and records what changed and why in the report's revision history.
