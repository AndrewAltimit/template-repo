"""Command-line interface for economic agents."""

import click
from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Autonomous Economic Agents simulation framework."""


@main.command()
@click.option("--balance", default=50.0, help="Initial wallet balance")
@click.option("--compute-hours", default=24.0, help="Initial compute hours")
@click.option("--cost-per-hour", default=2.0, help="Compute cost per hour")
@click.option("--cycles", default=5, help="Number of cycles to run")
@click.option("--seed", default=42, help="Random seed for reproducibility")
@click.option("--company-threshold", default=100.0, help="Balance needed to form company")
@click.option(
    "--personality", default="balanced", type=click.Choice(["risk_averse", "balanced", "aggressive"]), help="Agent personality"
)
def run(
    balance: float,
    compute_hours: float,
    cost_per_hour: float,
    cycles: int,
    seed: int,
    company_threshold: float,
    personality: str,
):
    """Run autonomous agent simulation."""
    click.echo("Initializing autonomous agent...")

    # Create mock implementations
    wallet = MockWallet(initial_balance=balance)
    compute = MockCompute(initial_hours=compute_hours, cost_per_hour=cost_per_hour)
    marketplace = MockMarketplace(seed=seed)

    # Create agent
    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={
            "survival_buffer_hours": 24.0,
            "personality": personality,
            "company_threshold": company_threshold,
        },
    )

    click.echo(f"Starting balance: ${balance:.2f}")
    click.echo(f"Starting compute: {compute_hours:.2f} hours")
    click.echo(f"Running {cycles} cycles...\n")

    # Run simulation
    decisions = agent.run(max_cycles=cycles)

    # Display results
    click.echo(f"\nCompleted {len(decisions)} cycles")
    click.echo(f"Final balance: ${agent.state.balance:.2f}")
    click.echo(f"Final compute: {agent.state.compute_hours_remaining:.2f} hours")
    click.echo(f"Tasks completed: {agent.state.tasks_completed}")
    click.echo(f"Tasks failed: {agent.state.tasks_failed}")
    click.echo(f"Total earned: ${agent.state.total_earned:.2f}")
    click.echo(f"Total spent: ${agent.state.total_spent:.2f}")

    # Display company info if formed
    if agent.state.has_company and agent.company:
        click.echo(f"\n{'='*60}")
        click.echo("COMPANY FORMED!")
        click.echo(f"{'='*60}")
        click.echo(f"Name: {agent.company.name}")
        click.echo(f"Mission: {agent.company.mission}")
        click.echo(f"Stage: {agent.company.stage}")
        click.echo(f"Capital: ${agent.company.capital:.2f}")
        click.echo("\nTeam:")
        click.echo(f"  Board Members: {len(agent.company.board_member_ids)}")
        click.echo(f"  Executives: {len(agent.company.executive_ids)}")
        click.echo(f"  Employees: {len(agent.company.employee_ids)}")
        click.echo(f"  Total: {len(agent.company.get_all_sub_agent_ids())}")

        if agent.company.products:
            click.echo(f"\nProducts: {len(agent.company.products)}")
            for i, product in enumerate(agent.company.products, 1):
                click.echo(f"  {i}. {product.spec.name} ({product.status}) - {product.completion_percentage:.0f}% complete")

        if agent.company.business_plan:
            click.echo("\nBusiness Plan:")
            click.echo(f"  Target Market: {agent.company.business_plan.target_market}")
            click.echo(f"  Funding Requested: ${agent.company.business_plan.funding_requested:,.0f}")
            projections = ", ".join(f"${r:,.0f}" for r in agent.company.business_plan.revenue_projections)
            click.echo(f"  Revenue Projections (Yr 1-3): {projections}")

    if decisions:
        click.echo(f"\n{'='*60}")
        click.echo("Recent decisions:")
        for i, decision in enumerate(decisions[-3:], 1):
            allocation = decision["allocation"]
            click.echo(f"  {i}. {allocation['reasoning']}")
            click.echo(
                f"     Task work: {allocation['task_work_hours']:.2f}h, "
                f"Company work: {allocation['company_work_hours']:.2f}h"
            )


@main.command()
def status():
    """Show current agent status (placeholder)."""
    click.echo("Status command not yet implemented")


@main.command()
def init():
    """Initialize simulation environment (placeholder)."""
    click.echo("Init command not yet implemented")


if __name__ == "__main__":
    main()
