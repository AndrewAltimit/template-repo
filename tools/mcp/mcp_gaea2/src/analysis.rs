//! Workflow analysis and property optimization.
//!
//! Heuristics are derived from the reference-project analysis documented in
//! `docs/GAEA2_KNOWLEDGE_BASE.md` (most common node chains, typical costs).

use std::collections::{HashMap, HashSet};

use serde::Serialize;
use serde_json::{json, Value};

use crate::schema::{get_node_category, is_valid_node_type, COLORIZE_NODES, OUTPUT_NODES};
use crate::types::{AnalysisType, Node, OptimizationMode, Workflow};
use crate::validation::{find_cycle_nodes, topological_order};

/// Relative build cost of expensive node types (1.0 = a cheap filter).
fn node_cost(node_type: &str) -> f64 {
    match node_type {
        "Erosion2" | "Erosion" => 8.0,
        "Rivers" | "Lake" | "Sea" | "Glacier" => 6.0,
        "Snow" | "Snowfield" | "Thermal" | "Thermal2" | "Wizard" | "Wizard2" => 4.0,
        "FlowMap" | "FlowMapClassic" | "Sediment" | "Sediments" | "Debris" | "Crumble" => 3.0,
        "EasyErosion" | "Anastomosis" | "Scree" | "Dusting" | "Trees" | "Shrubs" => 2.5,
        _ => 1.0,
    }
}

/// Known node chains from reference projects: (name, chain).
static KNOWN_PATTERNS: &[(&str, &[&str])] = &[
    ("Classic erosion pipeline", &["Mountain", "Erosion2"]),
    ("Mountain water workflow", &["Erosion2", "Rivers"]),
    ("Texture colorization", &["TextureBase", "SatMap"]),
    ("Slump terraces", &["Slump", "FractalTerraces"]),
    ("Canyon strata", &["Canyon", "Stratify"]),
    ("Canyon sandstone", &["Canyon", "Sandstone"]),
    ("Stratified rock", &["Sandstone", "Stratify"]),
    ("Crumble before erosion", &["Crumble", "Erosion2"]),
    ("Volcanic weathering", &["Volcano", "Thermal2"]),
    ("Debris flow", &["Debris", "Debris"]),
];

/// Analysis report returned by `analyze_workflow_patterns`.
#[derive(Debug, Serialize)]
pub struct AnalysisReport {
    pub analysis_type: AnalysisType,
    pub node_count: usize,
    pub connection_count: usize,
    pub complexity_score: f64,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub patterns: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub performance: Option<Value>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub quality_issues: Vec<String>,
    pub suggestions: Vec<String>,
}

/// Analyse a workflow.
pub fn analyze(
    workflow: &Workflow,
    analysis_type: AnalysisType,
    workflow_type: &str,
) -> AnalysisReport {
    let nodes = &workflow.nodes;
    let conns = &workflow.connections;
    let types: Vec<&str> = nodes.iter().map(|n| n.node_type.as_str()).collect();
    let has = |t: &str| types.contains(&t);
    let by_id: HashMap<i32, &Node> = nodes.iter().map(|n| (n.id, n)).collect();

    let want = |t: AnalysisType| analysis_type == AnalysisType::All || analysis_type == t;
    let mut patterns = Vec::new();
    let mut suggestions: Vec<String> = Vec::new();
    let mut quality_issues = Vec::new();
    let mut performance = None;

    let depth = longest_chain(workflow);
    let complexity =
        (nodes.len() as f64 * 0.3 + conns.len() as f64 * 0.2 + depth as f64 * 0.5).min(100.0);

    if want(AnalysisType::Patterns) {
        let edges: HashSet<(&str, &str)> = conns
            .iter()
            .filter_map(|c| {
                Some((
                    by_id.get(&c.from_node)?.node_type.as_str(),
                    by_id.get(&c.to_node)?.node_type.as_str(),
                ))
            })
            .collect();
        for (name, chain) in KNOWN_PATTERNS {
            if chain.windows(2).all(|w| edges.contains(&(w[0], w[1]))) {
                patterns.push(format!("{name}: {}", chain.join(" -> ")));
            }
        }
        let erosion_count = types
            .iter()
            .filter(|t| matches!(**t, "Erosion" | "Erosion2"))
            .count();
        if erosion_count > 1 {
            patterns.push(format!(
                "Multi-stage erosion ({erosion_count} erosion nodes)"
            ));
        }
        if has("PortalTransmit") && has("PortalReceive") {
            patterns.push("Modular portal workflow".to_string());
        }
        if patterns.is_empty() {
            patterns.push("No well-known reference patterns detected".to_string());
        }
    }

    if want(AnalysisType::Performance) {
        let total: f64 = types.iter().map(|t| node_cost(t)).sum();
        let mut heavy: Vec<Value> = nodes
            .iter()
            .filter(|n| node_cost(&n.node_type) >= 3.0)
            .map(|n| json!({"id": n.id, "type": n.node_type, "relative_cost": node_cost(&n.node_type)}))
            .collect();
        heavy.sort_by(|a, b| {
            b["relative_cost"]
                .as_f64()
                .partial_cmp(&a["relative_cost"].as_f64())
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        let erosion_nodes = types
            .iter()
            .filter(|t| matches!(**t, "Erosion" | "Erosion2"))
            .count();
        if erosion_nodes > 3 {
            suggestions.push(format!(
                "{erosion_nodes} erosion nodes: reference projects rarely chain more than 3; consider merging passes"
            ));
        }
        for n in nodes.iter().filter(|n| n.node_type == "Erosion2") {
            if let Some(d) = n.properties.get("Duration").and_then(Value::as_f64) {
                if d > 1.0 {
                    suggestions.push(format!(
                        "Node {} Erosion2 Duration {d} is very long; 0.1-0.3 is typical, use optimize_gaea2_properties with mode=performance for previews",
                        n.id
                    ));
                }
            }
        }
        let recommended_resolution = if total > 40.0 { 1024 } else { 2048 };
        performance = Some(json!({
            "estimated_relative_cost": total,
            "heavy_nodes": heavy,
            "longest_chain": depth,
            "recommended_preview_resolution": recommended_resolution
        }));
    }

    if want(AnalysisType::Quality) {
        if !types
            .iter()
            .any(|t| matches!(*t, "Export" | "Output" | "Unity" | "Unreal"))
        {
            quality_issues.push("No Export node: builds will not write any files".to_string());
            suggestions.push("Add an Export node with a save_definition".to_string());
        }
        let has_base = nodes.iter().any(|n| {
            matches!(
                get_node_category(&n.node_type),
                Some("Terrain") | Some("Primitive")
            )
        });
        if !has_base {
            quality_issues.push("No terrain or primitive generator node".to_string());
        }
        if has_base
            && !types
                .iter()
                .any(|t| matches!(*t, "Erosion" | "Erosion2" | "EasyErosion"))
        {
            suggestions.push("Add Erosion2 after the base shape for realistic detail".to_string());
        }
        if !types.iter().any(|t| COLORIZE_NODES.contains(t)) {
            suggestions.push("Add TextureBase -> SatMap for colorization".to_string());
        }
        for n in nodes.iter().filter(|n| !is_valid_node_type(&n.node_type)) {
            quality_issues.push(format!("Node {} has invalid type '{}'", n.id, n.node_type));
        }
        if find_cycle_nodes(nodes, conns).is_some() {
            quality_issues.push("Graph contains a cycle".to_string());
        }
        // Dead ends: nodes whose output goes nowhere and that are not outputs.
        let sources: HashSet<i32> = conns.iter().map(|c| c.from_node).collect();
        for n in nodes {
            let terminal_ok = OUTPUT_NODES.contains(&n.node_type.as_str())
                || COLORIZE_NODES.contains(&n.node_type.as_str())
                || n.node_type.starts_with("Portal");
            if !sources.contains(&n.id) && !terminal_ok && nodes.len() > 1 {
                quality_issues.push(format!(
                    "Node {} ({}) output is not used by any other node",
                    n.id, n.node_type
                ));
            }
        }
    }

    // Terrain-type specific suggestions.
    let lacks_all = |list: &[&str]| !list.iter().any(|t| has(t));
    let specific: &[(&[&str], &str)] = match workflow_type {
        "mountain" | "alpine" => &[
            (&["Snow", "Snowfield"], "Consider Snow for alpine peaks"),
            (
                &["Stones", "RockNoise", "Outcrops"],
                "Add rock detail with Outcrops or RockNoise",
            ),
        ],
        "volcanic" => &[
            (
                &["Thermal", "Thermal2"],
                "Add Thermal2 for volcanic weathering",
            ),
            (
                &["Stratify"],
                "Stratify adds the rock layering typical of volcanic terrain",
            ),
        ],
        "canyon" => &[
            (&["Stratify"], "Add Stratify for canyon rock layers"),
            (
                &["FractalTerraces", "Terraces"],
                "FractalTerraces creates canyon shelf formations",
            ),
        ],
        "coastal" => &[
            (
                &["Coast", "Sea"],
                "Add Sea or Coast for water and shorelines",
            ),
            (&["Beach"], "Beach creates realistic shorelines"),
        ],
        "arctic" => &[
            (&["Glacier", "IceFloe"], "Add Glacier for ice features"),
            (
                &["Snow", "Snowfield"],
                "Snow is essential for arctic terrain",
            ),
        ],
        "desert" => &[
            (
                &["Sand", "DuneSea"],
                "Add Sand or DuneSea for desert terrain",
            ),
            (
                &["Sandstone"],
                "Sandstone adds characteristic desert erosion",
            ),
        ],
        "river" => &[
            (&["Rivers"], "Rivers is essential for river terrain"),
            (
                &["Sediment", "Sediments", "Fluvial"],
                "Add Sediment for river deposits",
            ),
        ],
        _ => &[],
    };
    for (nodes_needed, msg) in specific {
        if lacks_all(nodes_needed) {
            suggestions.push((*msg).to_string());
        }
    }
    suggestions.dedup();

    AnalysisReport {
        analysis_type,
        node_count: nodes.len(),
        connection_count: conns.len(),
        complexity_score: (complexity * 10.0).round() / 10.0,
        patterns,
        performance,
        quality_issues,
        suggestions,
    }
}

/// Number of nodes on the longest dependency chain.
fn longest_chain(workflow: &Workflow) -> usize {
    let order = topological_order(&workflow.nodes, &workflow.connections);
    let mut depth: HashMap<i32, usize> = HashMap::new();
    for id in &order {
        let d = workflow
            .connections
            .iter()
            .filter(|c| c.to_node == *id)
            .filter_map(|c| depth.get(&c.from_node))
            .max()
            .map_or(1, |d| d + 1);
        depth.insert(*id, d);
    }
    depth.values().copied().max().unwrap_or(0)
}

/// One property change made by the optimizer.
#[derive(Debug, Serialize, PartialEq)]
pub struct PropertyChange {
    pub node_id: i32,
    pub node_name: String,
    pub property: String,
    pub old: Option<Value>,
    pub new: Value,
    pub reason: String,
}

/// Cost-driving properties: (node type, property, performance, balanced, quality).
///
/// Performance mode lowers values above the performance target; quality mode
/// raises values below the quality target; balanced only fills in missing
/// values with the balanced default.
static COST_PROPERTIES: &[(&str, &str, f64, f64, f64)] = &[
    ("Erosion2", "Duration", 0.07, 0.15, 0.3),
    ("Erosion", "Duration", 0.02, 0.04, 0.1),
    ("Snow", "Duration", 0.3, 0.5, 0.7),
    ("Thermal", "Iterations", 8.0, 15.0, 30.0),
    ("FlowMap", "Iterations", 50.0, 100.0, 200.0),
];

/// Optimize cost-driving node properties for the given mode.
pub fn optimize(nodes: &mut [Node], mode: OptimizationMode) -> Vec<PropertyChange> {
    let mut changes = Vec::new();
    for node in nodes.iter_mut() {
        for (ty, prop, perf, bal, qual) in COST_PROPERTIES {
            if node.node_type != *ty {
                continue;
            }
            let is_int = *prop == "Iterations";
            let current = node.properties.get(*prop).and_then(Value::as_f64);
            let target = match (mode, current) {
                (_, None) => Some(match mode {
                    OptimizationMode::Performance => *perf,
                    OptimizationMode::Balanced => *bal,
                    OptimizationMode::Quality => *qual,
                }),
                (OptimizationMode::Performance, Some(c)) if c > *perf => Some(*perf),
                (OptimizationMode::Quality, Some(c)) if c < *qual => Some(*qual),
                _ => None,
            };
            let Some(target) = target else { continue };
            let new = if is_int {
                json!(target.round() as i64)
            } else {
                json!(target)
            };
            let reason = match (mode, current) {
                (_, None) => format!("{prop} was unset; using the {mode:?} default").to_lowercase(),
                (OptimizationMode::Performance, _) => {
                    format!("lowered {prop} to cut build time")
                },
                _ => format!("raised {prop} for more detail"),
            };
            changes.push(PropertyChange {
                node_id: node.id,
                node_name: node.name.clone(),
                property: (*prop).to_string(),
                old: node.properties.get(*prop).cloned(),
                new: new.clone(),
                reason,
            });
            node.properties.insert((*prop).to_string(), new);
        }
    }
    changes
}

/// Recommended build resolution for a mode.
pub fn recommended_resolution(mode: OptimizationMode) -> u32 {
    match mode {
        OptimizationMode::Performance => 1024,
        OptimizationMode::Balanced => 2048,
        OptimizationMode::Quality => 4096,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::Connection;

    fn wf() -> Workflow {
        Workflow {
            nodes: vec![
                Node::new(1, "Mountain"),
                Node::new(2, "Erosion2"),
                Node::new(3, "Rivers"),
                Node::new(4, "Export"),
            ],
            connections: vec![
                Connection::new(1, "Out", 2, "In"),
                Connection::new(2, "Out", 3, "In"),
                Connection::new(3, "Out", 4, "In"),
            ],
        }
    }

    #[test]
    fn detects_patterns_from_edges_not_just_presence() {
        let r = analyze(&wf(), AnalysisType::Patterns, "general");
        assert!(r.patterns.iter().any(|p| p.contains("Classic erosion")));
        assert!(r.patterns.iter().any(|p| p.contains("Mountain water")));
        assert!(r.performance.is_none());

        // Same node types, but not connected in that order -> no pattern.
        let mut w = wf();
        w.connections.clear();
        let r = analyze(&w, AnalysisType::Patterns, "general");
        assert!(!r.patterns.iter().any(|p| p.contains("Classic erosion")));
    }

    #[test]
    fn analysis_type_selects_sections() {
        let r = analyze(&wf(), AnalysisType::Performance, "general");
        assert!(r.patterns.is_empty());
        let perf = r.performance.unwrap();
        assert_eq!(perf["longest_chain"], 4);
        assert!(perf["heavy_nodes"].as_array().unwrap().len() >= 2);

        let r = analyze(&wf(), AnalysisType::Quality, "desert");
        assert!(r.performance.is_none());
        assert!(r.suggestions.iter().any(|s| s.contains("Sand")));
        assert!(r.suggestions.iter().any(|s| s.contains("SatMap")));
    }

    #[test]
    fn quality_flags_dead_ends_and_missing_export() {
        let mut w = wf();
        w.nodes.pop();
        w.connections.pop();
        let r = analyze(&w, AnalysisType::Quality, "general");
        assert!(r.quality_issues.iter().any(|q| q.contains("No Export")));
        assert!(r.quality_issues.iter().any(|q| q.contains("not used")));
    }

    #[test]
    fn optimize_modes() {
        let mut nodes = wf().nodes;
        nodes[1].properties.insert("Duration".into(), json!(1.5));
        let changes = optimize(&mut nodes, OptimizationMode::Performance);
        assert_eq!(changes.len(), 1);
        assert_eq!(nodes[1].properties["Duration"], json!(0.07));
        assert_eq!(changes[0].old, Some(json!(1.5)));

        let mut nodes = wf().nodes;
        nodes[1].properties.insert("Duration".into(), json!(0.1));
        let changes = optimize(&mut nodes, OptimizationMode::Quality);
        assert_eq!(nodes[1].properties["Duration"], json!(0.3));
        assert_eq!(changes.len(), 1);

        // Balanced leaves explicit values alone and fills gaps.
        let mut nodes = wf().nodes;
        nodes[1].properties.insert("Duration".into(), json!(0.9));
        assert!(optimize(&mut nodes, OptimizationMode::Balanced).is_empty());
        let mut nodes = wf().nodes;
        assert_eq!(optimize(&mut nodes, OptimizationMode::Balanced).len(), 1);
        assert_eq!(nodes[1].properties["Duration"], json!(0.15));
    }

    #[test]
    fn optimizer_values_pass_schema_ranges() {
        use crate::schema::{property_spec, PropKind};
        for (ty, prop, a, b, c) in COST_PROPERTIES {
            if let Some(spec) = property_spec(ty, prop) {
                for v in [a, b, c] {
                    match spec.kind {
                        PropKind::Float { min, max } => assert!((min..=max).contains(v)),
                        PropKind::Int { min, max } => {
                            assert!((min as f64..=max as f64).contains(v))
                        },
                        _ => panic!("unexpected kind for {ty}.{prop}"),
                    }
                }
            }
        }
    }
}
