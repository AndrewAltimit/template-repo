#!/usr/bin/env python3
"""Example demonstrating the Behavior Observatory for agent analysis.

This example shows how to use the observatory components to analyze
agent decision-making patterns, risk profiles, LLM quality, and emergent behaviors.
"""

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.api.config import BackendConfig, BackendMode
from economic_agents.api.factory import create_backends
from economic_agents.observatory import AnalysisReportGenerator


def main():
    """Run agent and analyze behavior with observatory."""
    print("=" * 60)
    print("Behavior Observatory Example")
    print("=" * 60)

    # 1. Create backends
    config = BackendConfig(
        mode=BackendMode.MOCK,
        initial_balance=200.0,
        initial_compute_hours=48.0,
        compute_cost_per_hour=0.0,
        marketplace_seed=42,
    )

    wallet, compute, marketplace, investor = create_backends(config)

    # 2. Create agent
    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={
            "survival_buffer_hours": 10.0,
            "company_threshold": 150.0,
            "personality": "balanced",
        },
    )

    print(f"\nAgent ID: {agent.agent_id}")
    print(f"Initial Balance: ${agent.state.balance:.2f}")
    print(f"Initial Compute: {agent.state.compute_hours_remaining:.1f}h")

    # 3. Run agent for analysis period
    cycles = 50
    print(f"\nRunning {cycles} cycles for behavior analysis...\n")

    for i in range(cycles):
        agent.run_cycle()

        if (i + 1) % 10 == 0:
            print(f"  Cycle {i + 1}/{cycles}: " f"Balance=${agent.state.balance:.2f}, " f"Tasks={agent.state.tasks_completed}")

    print(f"\n{'=' * 60}")
    print("Agent Run Complete - Beginning Analysis")
    print(f"{'=' * 60}\n")

    # 4. Prepare decision history for analysis
    decisions = []
    for decision in agent.decisions:
        decisions.append(
            {
                "state": {
                    "balance": decision.state.balance,
                    "compute_hours_remaining": decision.state.compute_hours_remaining,
                    "has_company": decision.state.has_company,
                    "tasks_completed": decision.state.tasks_completed,
                },
                "action": {
                    "task_work_hours": decision.action.task_work_hours,
                    "company_investment_hours": decision.action.company_investment_hours,
                    "rest_hours": decision.action.rest_hours,
                },
                "reasoning": decision.reasoning,
                "timestamp": decision.timestamp,
            }
        )

    # 5. Generate comprehensive analysis
    print("Generating comprehensive behavior analysis...\n")

    report_generator = AnalysisReportGenerator(agent_id=agent.agent_id)
    report_generator.load_decisions(decisions)

    # Define stated strategy for alignment analysis
    stated_strategy = {
        "objective": "survive and grow",
        "risk_tolerance": "balanced",
        "priorities": ["survival", "capital_accumulation", "growth"],
    }

    analysis = report_generator.generate_comprehensive_analysis(stated_strategy)

    # 6. Display analysis results
    print(f"{'=' * 60}")
    print("BEHAVIOR ANALYSIS RESULTS")
    print(f"{'=' * 60}\n")

    print("Overall Assessment:")
    print(f"  Performance Rating: {analysis.overall_assessment['performance_rating']}")
    print(f"  Overall Score: {analysis.overall_assessment['overall_performance']:.1f}/100")
    print(f"  {analysis.overall_assessment['summary']}\n")

    print("Key Metrics:")
    print(f"  Decision Quality: {analysis.overall_assessment['decision_quality_score']:.1f}/100")
    print(f"  LLM Reliability: {analysis.overall_assessment['llm_reliability_score']:.1f}/100")
    print(f"  Innovation Score: {analysis.overall_assessment['innovation_score']:.1f}/100\n")

    print("Strategic Alignment:")
    print(f"  Alignment Score: {analysis.strategic_alignment['alignment_score']:.1f}/100")
    print(f"  Consistency Score: {analysis.strategic_alignment['consistency_score']:.1f}/100")
    print(f"  Strategy Deviations: {analysis.strategic_alignment['deviations_count']}\n")

    print("Risk Profile:")
    print(f"  Risk Category: {analysis.risk_profile['risk_category'].replace('_', ' ').title()}")
    print(f"  Overall Risk Score: {analysis.risk_profile['overall_risk_score']:.1f}/100")
    print(f"  Crisis Behavior: {analysis.risk_profile['crisis_behavior'].title()}")
    print(f"  Growth Preference: {analysis.risk_profile['growth_preference']:.1f}/100\n")

    print("LLM Decision Quality:")
    print(f"  Reasoning Depth: {analysis.llm_quality['reasoning_depth']:.1f}/100")
    print(f"  Consistency: {analysis.llm_quality['consistency_score']:.1f}/100")
    print(f"  Hallucinations: {analysis.llm_quality['hallucination_count']}")
    print(f"  Success Rate: {analysis.llm_quality['structured_output_success_rate']:.1f}%\n")

    print("Emergent Behaviors:")
    print(f"  Novel Strategies: {analysis.emergent_behaviors['novel_strategies_count']}")
    print(f"  Behavior Patterns: {analysis.emergent_behaviors['behavior_patterns_count']}\n")

    if analysis.emergent_behaviors["novel_strategies"]:
        print("  Detected Novel Strategies:")
        for strategy in analysis.emergent_behaviors["novel_strategies"]:
            print(f"    - {strategy['name']}: {strategy['description'][:60]}...")
        print()

    # 7. Generate and save reports
    print(f"{'=' * 60}")
    print("Generating Reports")
    print(f"{'=' * 60}\n")

    # Save markdown report
    report_generator.generate_markdown_report(analysis, output_path=f"logs/observatory/reports/{agent.agent_id}_report.md")
    print(f"Markdown report saved to: logs/observatory/reports/{agent.agent_id}_report.md")

    # Save JSON report
    report_generator.generate_json_report(analysis, output_path=f"logs/observatory/reports/{agent.agent_id}_report.json")
    print(f"JSON report saved to: logs/observatory/reports/{agent.agent_id}_report.json")

    print(f"\n{'=' * 60}")
    print("Analysis Complete!")
    print(f"{'=' * 60}\n")

    print("Key Takeaways:")
    print("- The Behavior Observatory provides deep insights into agent decision-making")
    print("- Analyzes strategic alignment, risk tolerance, and LLM quality")
    print("- Detects emergent behaviors and novel strategies")
    print("- Generates both human-readable and machine-readable reports")
    print("- Perfect for research, debugging, and understanding AI agent behaviors")


if __name__ == "__main__":
    main()
