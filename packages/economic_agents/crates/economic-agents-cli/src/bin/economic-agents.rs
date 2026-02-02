//! Economic Agents CLI.

use std::collections::HashMap;
use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;

use clap::{Parser, Subcommand, ValueEnum};
use tracing::info;

use economic_agents_cli::{AgentFileConfig, Scenario, run_agent, run_scenario};
use economic_agents_dashboard::{DashboardConfig, DashboardService, DashboardState};
use economic_agents_observability::{
    BehaviorDecisionRecord, DecisionPatternAnalyzer, DecisionRecord, EmergentBehaviorDetector,
    LLMDecisionRecord, LLMQualityAnalyzer, RiskDecisionRecord, RiskProfiler,
};
use economic_agents_persistence::{LoadedAgentState, SerializedDecision, StateManager};
use economic_agents_reports::{AgentData, DecisionData, ReportGenerator};

#[derive(Parser)]
#[command(name = "economic-agents")]
#[command(about = "Autonomous economic agent simulation framework")]
#[command(version)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Run an agent simulation
    Run {
        /// Configuration file path (YAML)
        #[arg(short, long)]
        config: Option<PathBuf>,

        /// Maximum number of cycles
        #[arg(short = 'n', long)]
        max_cycles: Option<u32>,

        /// Use mock backends (always true for now)
        #[arg(long, default_value = "true")]
        mock: bool,

        /// Keep cycle history in output
        #[arg(long)]
        keep_cycles: bool,

        /// Output format (text, json)
        #[arg(short, long, default_value = "text")]
        output: String,

        /// Save agent state after run
        #[arg(long)]
        save: bool,
    },

    /// Start the dashboard server
    Dashboard {
        /// Port to listen on
        #[arg(short, long, default_value = "8000")]
        port: u16,

        /// Host to bind to
        #[arg(long, default_value = "0.0.0.0")]
        host: String,

        /// Disable CORS
        #[arg(long)]
        no_cors: bool,

        /// Disable request tracing
        #[arg(long)]
        no_tracing: bool,
    },

    /// Run a predefined scenario
    Scenario {
        /// Scenario name
        name: String,

        /// Keep cycle history in output
        #[arg(long)]
        keep_cycles: bool,

        /// Output format (text, json)
        #[arg(short, long, default_value = "text")]
        output: String,
    },

    /// List available scenarios
    ListScenarios,

    /// Show system status and saved agents
    Status {
        /// Output format
        #[arg(short, long, default_value = "text")]
        output: String,
    },

    /// List saved agent states
    ListSaved {
        /// Output format
        #[arg(short, long, default_value = "text")]
        output: String,
    },

    /// Delete a saved agent state
    DeleteSaved {
        /// Agent ID to delete
        agent_id: String,

        /// Skip confirmation
        #[arg(short, long)]
        force: bool,
    },

    /// Generate a report for a saved agent
    Report {
        /// Agent ID
        agent_id: String,

        /// Report type
        #[arg(short = 't', long, value_enum, default_value = "executive")]
        report_type: ReportTypeArg,

        /// Output format
        #[arg(short, long, default_value = "text")]
        output: String,
    },

    /// Analyze a saved agent's behavior
    Analyze {
        /// Agent ID
        agent_id: String,

        /// Analysis type
        #[arg(short = 't', long, value_enum, default_value = "patterns")]
        analysis_type: AnalysisType,

        /// Output format
        #[arg(short, long, default_value = "text")]
        output: String,
    },
}

#[derive(Clone, Copy, ValueEnum)]
enum ReportTypeArg {
    /// Executive summary with key metrics
    Executive,
    /// Technical details for researchers
    Technical,
    /// Audit trail for compliance
    Audit,
    /// Governance analysis
    Governance,
}

#[derive(Clone, Copy, ValueEnum)]
enum AnalysisType {
    /// Decision pattern analysis
    Patterns,
    /// Risk profile analysis
    Risk,
    /// Emergent behavior detection
    Behavior,
    /// LLM quality metrics
    LlmQuality,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize logging
    tracing_subscriber::fmt::init();

    let cli = Cli::parse();

    match cli.command {
        Commands::Run {
            config,
            max_cycles,
            mock: _,
            keep_cycles,
            output,
            save,
        } => {
            // Load config from file or use defaults
            let mut agent_config = if let Some(path) = config {
                AgentFileConfig::from_file(&path)?
            } else {
                AgentFileConfig::default()
            };

            // Override max_cycles if specified
            if let Some(cycles) = max_cycles {
                agent_config.max_cycles = Some(cycles);
            }

            info!(
                agent_id = ?agent_config.agent_id,
                max_cycles = ?agent_config.max_cycles,
                mode = ?agent_config.mode,
                "Starting agent"
            );

            let result = run_agent(agent_config.clone(), None, keep_cycles).await?;

            // Save state if requested
            if save {
                let state_manager = StateManager::with_default_dir().await?;
                let agent_id = agent_config.agent_id.as_deref().unwrap_or(&result.agent_id);

                // Create a basic AgentState from the result
                let state = economic_agents_core::state::AgentState {
                    balance: result.final_balance,
                    compute_hours: 0.0, // Not tracked in result
                    is_active: false,
                    has_company: result.has_company,
                    company_id: None,
                    tasks_completed: result.tasks_completed,
                    tasks_failed: result.tasks_failed,
                    current_cycle: result.cycles_executed,
                    total_earnings: result.total_earnings,
                    total_expenses: result.total_expenses,
                    reputation: 0.5,
                    consecutive_failures: 0,
                    current_task_id: None,
                    last_updated: chrono::Utc::now(),
                };

                state_manager
                    .save_agent_state(agent_id, &state, vec![])
                    .await?;
                eprintln!("Agent state saved as '{}'", agent_id);
            }

            match output.as_str() {
                "json" => {
                    println!(
                        "{}",
                        serde_json::to_string_pretty(&serde_json::json!({
                            "agent_id": result.agent_id,
                            "cycles_executed": result.cycles_executed,
                            "tasks_completed": result.tasks_completed,
                            "tasks_failed": result.tasks_failed,
                            "success_rate": result.success_rate(),
                            "final_balance": result.final_balance,
                            "total_earnings": result.total_earnings,
                            "total_expenses": result.total_expenses,
                            "net_profit": result.net_profit(),
                            "has_company": result.has_company,
                            "duration_ms": result.duration_ms,
                        }))?
                    );
                },
                _ => {
                    println!("\n=== Agent Run Complete ===");
                    println!("Agent: {}", result.agent_id);
                    println!("Cycles: {}", result.cycles_executed);
                    println!(
                        "Tasks: {} completed, {} failed ({:.1}% success)",
                        result.tasks_completed,
                        result.tasks_failed,
                        result.success_rate() * 100.0
                    );
                    println!("Final balance: ${:.2}", result.final_balance);
                    println!("Net profit: ${:.2}", result.net_profit());
                    println!("Has company: {}", result.has_company);
                    println!("Duration: {}ms", result.duration_ms);
                },
            }
        },

        Commands::Dashboard {
            port,
            host,
            no_cors,
            no_tracing,
        } => {
            let config = DashboardConfig {
                port,
                host: host.clone(),
                enable_cors: !no_cors,
                enable_tracing: !no_tracing,
            };

            let state = Arc::new(DashboardState::new());
            let service = DashboardService::new(config.clone(), Arc::clone(&state));
            let router = service.build_router();

            let addr: SocketAddr = format!("{}:{}", host, port).parse()?;
            info!(address = %addr, "Starting dashboard server");
            println!("Dashboard running at http://{}", addr);

            let listener = tokio::net::TcpListener::bind(addr).await?;
            axum::serve(listener, router).await?;
        },

        Commands::Scenario {
            name,
            keep_cycles,
            output,
        } => {
            let scenario = Scenario::by_name(&name).ok_or_else(|| {
                anyhow::anyhow!(
                    "Unknown scenario: '{}'. Use 'list-scenarios' to see available scenarios.",
                    name
                )
            })?;

            info!(
                name = %scenario.name,
                agents = %scenario.agents.len(),
                parallel = %scenario.parallel,
                "Running scenario"
            );

            let result = run_scenario(scenario, keep_cycles).await?;

            match output.as_str() {
                "json" => {
                    let agents_json: Vec<_> = result
                        .agent_results
                        .iter()
                        .map(|r| {
                            serde_json::json!({
                                "agent_id": r.agent_id,
                                "cycles_executed": r.cycles_executed,
                                "tasks_completed": r.tasks_completed,
                                "tasks_failed": r.tasks_failed,
                                "success_rate": r.success_rate(),
                                "final_balance": r.final_balance,
                                "net_profit": r.net_profit(),
                                "has_company": r.has_company,
                                "duration_ms": r.duration_ms,
                            })
                        })
                        .collect();

                    println!(
                        "{}",
                        serde_json::to_string_pretty(&serde_json::json!({
                            "scenario": result.name,
                            "duration_ms": result.duration_ms,
                            "agents": agents_json,
                            "best_performer": result.best_performer().map(|b| &b.agent_id),
                        }))?
                    );
                },
                _ => {
                    result.print_summary();
                },
            }
        },

        Commands::ListScenarios => {
            println!("\nAvailable Scenarios:");
            println!("====================\n");
            for (name, description) in Scenario::list_all() {
                println!("  {:<20} - {}", name, description);
            }
            println!("\nUsage: economic-agents scenario <name>\n");
        },

        Commands::Status { output } => {
            let state_manager = StateManager::with_default_dir().await?;
            let agents = state_manager.list_saved_agents().await?;
            let registry_exists = state_manager.registry_exists().await;

            match output.as_str() {
                "json" => {
                    println!(
                        "{}",
                        serde_json::to_string_pretty(&serde_json::json!({
                            "saved_agents_count": agents.len(),
                            "registry_exists": registry_exists,
                            "data_directory": state_manager.base_dir().display().to_string(),
                            "agents": agents.iter().map(|a| serde_json::json!({
                                "agent_id": a.agent_id,
                                "saved_at": a.saved_at.to_rfc3339(),
                                "balance": a.balance,
                                "cycle": a.current_cycle,
                            })).collect::<Vec<_>>(),
                        }))?
                    );
                },
                _ => {
                    println!("\n=== Economic Agents Status ===\n");
                    println!("Data directory: {}", state_manager.base_dir().display());
                    println!("Registry exists: {}", registry_exists);
                    println!("Saved agents: {}", agents.len());

                    if !agents.is_empty() {
                        println!("\nRecent agents:");
                        for agent in agents.iter().take(5) {
                            println!(
                                "  {} - ${:.2} (cycle {}) saved {}",
                                agent.agent_id,
                                agent.balance,
                                agent.current_cycle,
                                agent.saved_at.format("%Y-%m-%d %H:%M")
                            );
                        }
                        if agents.len() > 5 {
                            println!("  ... and {} more", agents.len() - 5);
                        }
                    }
                    println!();
                },
            }
        },

        Commands::ListSaved { output } => {
            let state_manager = StateManager::with_default_dir().await?;
            let agents = state_manager.list_saved_agents().await?;

            match output.as_str() {
                "json" => {
                    println!(
                        "{}",
                        serde_json::to_string_pretty(
                            &agents
                                .iter()
                                .map(|a| serde_json::json!({
                                    "agent_id": a.agent_id,
                                    "saved_at": a.saved_at.to_rfc3339(),
                                    "balance": a.balance,
                                    "cycle": a.current_cycle,
                                }))
                                .collect::<Vec<_>>()
                        )?
                    );
                },
                _ => {
                    if agents.is_empty() {
                        println!("No saved agents found.");
                        println!("Use 'economic-agents run --save' to save an agent.");
                    } else {
                        println!("\nSaved Agents:");
                        println!("{:-<70}", "");
                        println!(
                            "{:<20} {:>12} {:>8} {:>20}",
                            "Agent ID", "Balance", "Cycle", "Saved At"
                        );
                        println!("{:-<70}", "");
                        for agent in &agents {
                            println!(
                                "{:<20} {:>12.2} {:>8} {:>20}",
                                agent.agent_id,
                                agent.balance,
                                agent.current_cycle,
                                agent.saved_at.format("%Y-%m-%d %H:%M")
                            );
                        }
                        println!("{:-<70}", "");
                        println!("Total: {} agents\n", agents.len());
                    }
                },
            }
        },

        Commands::DeleteSaved { agent_id, force } => {
            let state_manager = StateManager::with_default_dir().await?;

            // Check if agent exists
            if state_manager.load_agent_state(&agent_id).await.is_err() {
                anyhow::bail!("Agent '{}' not found", agent_id);
            }

            if !force {
                eprintln!(
                    "Are you sure you want to delete agent '{}'? (use --force to skip)",
                    agent_id
                );
                eprintln!("This action cannot be undone.");
                // In a real CLI we'd prompt for confirmation
                // For now, require --force flag
                anyhow::bail!("Use --force flag to confirm deletion");
            }

            state_manager.delete_agent_state(&agent_id).await?;
            println!("Agent '{}' deleted.", agent_id);
        },

        Commands::Report {
            agent_id,
            report_type,
            output,
        } => {
            let state_manager = StateManager::with_default_dir().await?;
            let loaded = state_manager.load_agent_state(&agent_id).await?;

            // Convert loaded state to AgentData for report generation
            let agent_data = build_agent_data(&agent_id, &loaded);
            let generator = ReportGenerator::new(agent_data);

            // Generate the appropriate report type
            let report_markdown = match report_type {
                ReportTypeArg::Executive => {
                    let report = generator.generate_executive_summary();
                    if output == "json" {
                        serde_json::to_string_pretty(&report)?
                    } else {
                        report.to_markdown()
                    }
                },
                ReportTypeArg::Technical => {
                    let report = generator.generate_technical_report();
                    if output == "json" {
                        serde_json::to_string_pretty(&report)?
                    } else {
                        report.to_markdown()
                    }
                },
                ReportTypeArg::Audit => {
                    let report = generator.generate_audit_trail();
                    if output == "json" {
                        serde_json::to_string_pretty(&report)?
                    } else {
                        report.to_markdown()
                    }
                },
                ReportTypeArg::Governance => {
                    let report = generator.generate_governance_analysis();
                    if output == "json" {
                        serde_json::to_string_pretty(&report)?
                    } else {
                        report.to_markdown()
                    }
                },
            };

            println!("{}", report_markdown);
        },

        Commands::Analyze {
            agent_id,
            analysis_type,
            output,
        } => {
            let state_manager = StateManager::with_default_dir().await?;
            let loaded = state_manager.load_agent_state(&agent_id).await?;

            let result: serde_json::Value = match analysis_type {
                AnalysisType::Patterns => {
                    let mut analyzer = DecisionPatternAnalyzer::with_agent_id(&agent_id);
                    let decisions = convert_to_decision_records(&loaded.decisions);
                    analyzer.load_decisions(decisions);

                    let alignment = analyzer.analyze_strategic_consistency(None);
                    let quality_scores = analyzer.calculate_decision_quality_over_time();

                    serde_json::json!({
                        "type": "decision_patterns",
                        "agent_id": agent_id,
                        "decision_count": analyzer.decision_count(),
                        "strategy_alignment": {
                            "alignment_score": alignment.alignment_score,
                            "consistency_score": alignment.consistency_score,
                            "deviations_count": alignment.deviations_count,
                        },
                        "quality_scores": quality_scores,
                        "recommendations": alignment.recommendations,
                    })
                },
                AnalysisType::Risk => {
                    let mut profiler = RiskProfiler::with_agent_id(&agent_id);
                    let decisions = convert_to_risk_records(&loaded.decisions);
                    profiler.load_decisions(decisions);

                    let tolerance = profiler.calculate_risk_tolerance();
                    let crisis_decisions = profiler.crisis_decisions();

                    serde_json::json!({
                        "type": "risk_profile",
                        "agent_id": agent_id,
                        "risk_tolerance": {
                            "category": format!("{:?}", tolerance.risk_category),
                            "score": tolerance.overall_risk_score,
                            "growth_preference": tolerance.growth_preference,
                            "crisis_behavior": tolerance.crisis_behavior,
                            "risk_adjusted_returns": tolerance.risk_adjusted_returns,
                        },
                        "crisis_decisions_count": crisis_decisions.len(),
                        "crisis_decisions": crisis_decisions.iter().take(10).map(|c| serde_json::json!({
                            "severity": format!("{:?}", c.crisis_severity),
                            "cycle": c.cycle,
                            "balance": c.balance,
                            "compute_hours": c.compute_hours,
                        })).collect::<Vec<_>>(),
                    })
                },
                AnalysisType::Behavior => {
                    let mut detector = EmergentBehaviorDetector::with_agent_id(&agent_id);
                    let decisions = convert_to_behavior_records(&loaded.decisions);
                    detector.load_decisions(decisions);

                    // Clone the results to avoid multiple mutable borrows
                    let strategies = detector.detect_novel_strategies().to_vec();
                    let patterns = detector.detect_behavior_patterns().to_vec();

                    serde_json::json!({
                        "type": "emergent_behavior",
                        "agent_id": agent_id,
                        "novel_strategies": strategies.iter().map(|s| serde_json::json!({
                            "name": s.strategy_name,
                            "description": s.description,
                            "novelty_score": s.novelty_score,
                            "effectiveness": s.effectiveness,
                            "frequency": s.frequency,
                            "first_observed_cycle": s.first_observed_cycle,
                        })).collect::<Vec<_>>(),
                        "behavior_patterns": patterns.iter().map(|p| serde_json::json!({
                            "pattern_type": p.pattern_type,
                            "description": p.description,
                            "occurrences": p.occurrences,
                            "confidence": p.confidence,
                        })).collect::<Vec<_>>(),
                    })
                },
                AnalysisType::LlmQuality => {
                    let mut analyzer = LLMQualityAnalyzer::with_agent_id(&agent_id);
                    let decisions = convert_to_llm_records(&loaded.decisions);
                    analyzer.load_decisions(decisions);

                    let metrics = analyzer.calculate_overall_quality();
                    let hallucinations = analyzer.detect_hallucinations();

                    serde_json::json!({
                        "type": "llm_quality",
                        "agent_id": agent_id,
                        "quality_metrics": {
                            "reasoning_depth": metrics.reasoning_depth,
                            "consistency_score": metrics.consistency_score,
                            "hallucination_count": metrics.hallucination_count,
                            "average_response_length": metrics.average_response_length,
                            "structured_output_success_rate": metrics.structured_output_success_rate,
                        },
                        "hallucinations": hallucinations.iter().map(|h| serde_json::json!({
                            "type": h.hallucination_type,
                            "description": h.description,
                            "severity": format!("{:?}", h.severity),
                            "cycle": h.cycle,
                        })).collect::<Vec<_>>(),
                    })
                },
            };

            match output.as_str() {
                "json" => {
                    println!("{}", serde_json::to_string_pretty(&result)?);
                },
                _ => {
                    println!("\n{}", "=".repeat(60));
                    println!(
                        "Analysis: {} for agent '{}'",
                        result["type"].as_str().unwrap_or("unknown"),
                        agent_id
                    );
                    println!("{}", "=".repeat(60));

                    match analysis_type {
                        AnalysisType::Patterns => {
                            println!(
                                "\nDecisions analyzed: {}",
                                result["decision_count"].as_u64().unwrap_or(0)
                            );
                            println!("\nStrategy Alignment:");
                            println!(
                                "  Alignment score: {:.1}",
                                result["strategy_alignment"]["alignment_score"]
                                    .as_f64()
                                    .unwrap_or(0.0)
                            );
                            println!(
                                "  Consistency score: {:.1}",
                                result["strategy_alignment"]["consistency_score"]
                                    .as_f64()
                                    .unwrap_or(0.0)
                            );
                            println!(
                                "  Deviations: {}",
                                result["strategy_alignment"]["deviations_count"]
                                    .as_u64()
                                    .unwrap_or(0)
                            );

                            if let Some(recs) = result["recommendations"].as_array()
                                && !recs.is_empty()
                            {
                                println!("\nRecommendations:");
                                for rec in recs {
                                    println!("  - {}", rec.as_str().unwrap_or("?"));
                                }
                            }
                        },
                        AnalysisType::Risk => {
                            println!("\nRisk Tolerance:");
                            println!(
                                "  Category: {}",
                                result["risk_tolerance"]["category"]
                                    .as_str()
                                    .unwrap_or("Unknown")
                            );
                            println!(
                                "  Score: {:.1}",
                                result["risk_tolerance"]["score"].as_f64().unwrap_or(0.0)
                            );
                            println!(
                                "  Growth preference: {:.1}%",
                                result["risk_tolerance"]["growth_preference"]
                                    .as_f64()
                                    .unwrap_or(0.0)
                            );
                            println!(
                                "  Crisis behavior: {}",
                                result["risk_tolerance"]["crisis_behavior"]
                                    .as_str()
                                    .unwrap_or("unknown")
                            );
                            println!(
                                "\nCrisis decisions: {}",
                                result["crisis_decisions_count"].as_u64().unwrap_or(0)
                            );
                        },
                        AnalysisType::Behavior => {
                            if let Some(strategies) = result["novel_strategies"].as_array() {
                                if !strategies.is_empty() {
                                    println!("\nNovel Strategies ({}):", strategies.len());
                                    for s in strategies {
                                        println!(
                                            "  {} (novelty: {:.0}, effectiveness: {:.0})",
                                            s["name"].as_str().unwrap_or("?"),
                                            s["novelty_score"].as_f64().unwrap_or(0.0),
                                            s["effectiveness"].as_f64().unwrap_or(0.0)
                                        );
                                        println!("    {}", s["description"].as_str().unwrap_or(""));
                                    }
                                } else {
                                    println!("\nNo novel strategies detected.");
                                }
                            }

                            if let Some(patterns) = result["behavior_patterns"].as_array()
                                && !patterns.is_empty()
                            {
                                println!("\nBehavior Patterns ({}):", patterns.len());
                                for p in patterns {
                                    println!(
                                        "  {} (occurrences: {}, confidence: {:.0})",
                                        p["pattern_type"].as_str().unwrap_or("?"),
                                        p["occurrences"].as_u64().unwrap_or(0),
                                        p["confidence"].as_f64().unwrap_or(0.0)
                                    );
                                    println!("    {}", p["description"].as_str().unwrap_or(""));
                                }
                            }
                        },
                        AnalysisType::LlmQuality => {
                            println!("\nQuality Metrics:");
                            println!(
                                "  Reasoning depth: {:.1}",
                                result["quality_metrics"]["reasoning_depth"]
                                    .as_f64()
                                    .unwrap_or(0.0)
                            );
                            println!(
                                "  Consistency score: {:.1}",
                                result["quality_metrics"]["consistency_score"]
                                    .as_f64()
                                    .unwrap_or(0.0)
                            );
                            println!(
                                "  Structured output success: {:.1}%",
                                result["quality_metrics"]["structured_output_success_rate"]
                                    .as_f64()
                                    .unwrap_or(0.0)
                            );
                            println!(
                                "  Avg response length: {:.0} chars",
                                result["quality_metrics"]["average_response_length"]
                                    .as_f64()
                                    .unwrap_or(0.0)
                            );

                            let hallucination_count =
                                result["quality_metrics"]["hallucination_count"]
                                    .as_u64()
                                    .unwrap_or(0);
                            if hallucination_count > 0 {
                                println!("\nHallucinations detected: {}", hallucination_count);
                            } else {
                                println!("\nNo hallucinations detected.");
                            }
                        },
                    }
                    println!("\n{}", "=".repeat(60));
                },
            }
        },
    }

    Ok(())
}

// --- Helper functions for data conversion ---

/// Extract state and action from decision details JSON.
fn extract_state_action(
    details: &serde_json::Value,
) -> (
    HashMap<String, serde_json::Value>,
    HashMap<String, serde_json::Value>,
) {
    let mut state = HashMap::new();
    let mut action = HashMap::new();

    if let Some(s) = details.get("state")
        && let Some(obj) = s.as_object()
    {
        for (k, v) in obj {
            state.insert(k.clone(), v.clone());
        }
    }
    if let Some(a) = details.get("action")
        && let Some(obj) = a.as_object()
    {
        for (k, v) in obj {
            action.insert(k.clone(), v.clone());
        }
    }

    (state, action)
}

/// Build AgentData from loaded state for report generation.
fn build_agent_data(agent_id: &str, loaded: &LoadedAgentState) -> AgentData {
    let state = &loaded.state;

    // Convert decisions to DecisionData
    let decisions: Vec<DecisionData> = loaded
        .decisions
        .iter()
        .enumerate()
        .map(|(i, d)| DecisionData {
            id: format!("decision-{}", i),
            decision_type: d.decision_type.clone(),
            timestamp: d.timestamp.to_rfc3339(),
            reasoning: d
                .details
                .get("reasoning")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            outcome: d.outcome.clone().unwrap_or_else(|| "unknown".to_string()),
            confidence: d
                .details
                .get("confidence")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.5),
        })
        .collect();

    AgentData {
        agent_id: agent_id.to_string(),
        balance: state.balance,
        total_earnings: state.total_earnings,
        total_expenses: state.total_expenses,
        net_profit: state.total_earnings - state.total_expenses,
        burn_rate: if state.current_cycle > 0 {
            state.total_expenses / state.current_cycle as f64
        } else {
            0.0
        },
        tasks_completed: state.tasks_completed,
        tasks_failed: state.tasks_failed,
        success_rate: if state.tasks_completed + state.tasks_failed > 0 {
            state.tasks_completed as f64 / (state.tasks_completed + state.tasks_failed) as f64
                * 100.0
        } else {
            0.0
        },
        runtime_hours: state.current_cycle as f64, // Approximate
        company_exists: state.has_company,
        company: None, // Would need to load from registry
        decisions,
        transactions: vec![], // Would need transaction history
        sub_agents: vec![],   // Would need sub-agent data
    }
}

/// Get reasoning from decision details.
fn get_reasoning(details: &serde_json::Value) -> String {
    details
        .get("reasoning")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string()
}

/// Convert SerializedDecision to DecisionRecord for pattern analysis.
fn convert_to_decision_records(decisions: &[SerializedDecision]) -> Vec<DecisionRecord> {
    decisions
        .iter()
        .map(|d| {
            let (state, action) = extract_state_action(&d.details);
            DecisionRecord {
                state,
                action,
                reasoning: get_reasoning(&d.details),
                timestamp: Some(d.timestamp),
            }
        })
        .collect()
}

/// Convert SerializedDecision to RiskDecisionRecord for risk profiling.
fn convert_to_risk_records(decisions: &[SerializedDecision]) -> Vec<RiskDecisionRecord> {
    decisions
        .iter()
        .map(|d| {
            let (state, action) = extract_state_action(&d.details);
            RiskDecisionRecord {
                state,
                action,
                reasoning: get_reasoning(&d.details),
            }
        })
        .collect()
}

/// Convert SerializedDecision to BehaviorDecisionRecord for behavior detection.
fn convert_to_behavior_records(decisions: &[SerializedDecision]) -> Vec<BehaviorDecisionRecord> {
    decisions
        .iter()
        .map(|d| {
            let (state, action) = extract_state_action(&d.details);
            BehaviorDecisionRecord {
                state,
                action,
                reasoning: get_reasoning(&d.details),
            }
        })
        .collect()
}

/// Convert SerializedDecision to LLMDecisionRecord for LLM quality analysis.
fn convert_to_llm_records(decisions: &[SerializedDecision]) -> Vec<LLMDecisionRecord> {
    decisions
        .iter()
        .map(|d| {
            let (state, action) = extract_state_action(&d.details);
            LLMDecisionRecord {
                state,
                action: if action.is_empty() {
                    None
                } else {
                    Some(action)
                },
                reasoning: get_reasoning(&d.details),
            }
        })
        .collect()
}
