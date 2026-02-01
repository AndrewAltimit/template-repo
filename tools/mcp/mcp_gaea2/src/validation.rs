//! Workflow validation for Gaea2 projects.
//!
//! Provides validation and auto-fixing of node types, connections, and properties.

use std::collections::{HashMap, HashSet};

use crate::schema::{is_generator_node, is_valid_node_type};
use crate::types::{Connection, Node, ValidationResult, Workflow};

/// Validator for Gaea2 workflows.
pub struct Validator;

impl Validator {
    /// Validate a workflow and optionally fix issues.
    pub async fn validate_and_fix(workflow: &Workflow, strict_mode: bool) -> ValidationResult {
        let mut errors = Vec::new();
        let mut fixes_applied = Vec::new();
        let mut fixed_nodes = workflow.nodes.clone();
        let mut fixed_connections = workflow.connections.clone();
        let mut is_valid = true;

        // Validate node types
        for node in fixed_nodes.iter_mut() {
            if !is_valid_node_type(&node.node_type) {
                let err = format!(
                    "Node {} has invalid type '{}' - not in Gaea2 schema",
                    node.id, node.node_type
                );
                errors.push(err);
                is_valid = false;

                // Try to find similar valid type
                if let Some(suggestion) = find_similar_node_type(&node.node_type) {
                    fixes_applied.push(format!(
                        "Node {} type '{}' -> '{}'",
                        node.id, node.node_type, suggestion
                    ));
                    node.node_type = suggestion.to_string();
                }
            }

            // Set default name if empty
            if node.name.is_empty() {
                node.name = node.node_type.clone();
                fixes_applied.push(format!("Node {} name set to '{}'", node.id, node.name));
            }

            // Ensure generator nodes have a seed
            if is_generator_node(&node.node_type) && !node.properties.contains_key("Seed") {
                let seed = rand::random::<u32>() % 90000 + 10000;
                node.properties
                    .insert("Seed".to_string(), serde_json::Value::from(seed));
                fixes_applied.push(format!("Node {} assigned Seed {}", node.id, seed));
            }

            // Validate position
            if node.position.x < 0.0 || node.position.y < 0.0 {
                node.position.x = node.position.x.max(0.0);
                node.position.y = node.position.y.max(0.0);
                fixes_applied.push(format!("Node {} position corrected", node.id));
            }
        }

        // Collect valid node IDs
        let valid_ids: HashSet<i32> = fixed_nodes.iter().map(|n| n.id).collect();

        // Validate connections
        let mut connections_to_remove = Vec::new();
        for (i, conn) in fixed_connections.iter().enumerate() {
            if !valid_ids.contains(&conn.from_node) {
                errors.push(format!(
                    "Connection references invalid source node {}",
                    conn.from_node
                ));
                connections_to_remove.push(i);
                is_valid = false;
            }
            if !valid_ids.contains(&conn.to_node) {
                errors.push(format!(
                    "Connection references invalid target node {}",
                    conn.to_node
                ));
                if !connections_to_remove.contains(&i) {
                    connections_to_remove.push(i);
                }
                is_valid = false;
            }

            // Check for self-connections
            if conn.from_node == conn.to_node {
                errors.push(format!(
                    "Self-connection detected on node {}",
                    conn.from_node
                ));
                if !connections_to_remove.contains(&i) {
                    connections_to_remove.push(i);
                }
                is_valid = false;
            }
        }

        // Remove invalid connections (in reverse order to preserve indices)
        for i in connections_to_remove.into_iter().rev() {
            fixes_applied.push(format!(
                "Removed invalid connection from {} to {}",
                fixed_connections[i].from_node, fixed_connections[i].to_node
            ));
            fixed_connections.remove(i);
        }

        // Check for duplicate connections
        let mut seen_connections = HashSet::new();
        let mut duplicates = Vec::new();
        for (i, conn) in fixed_connections.iter().enumerate() {
            let key = (conn.from_node, conn.to_node, &conn.from_port, &conn.to_port);
            if seen_connections.contains(&key) {
                duplicates.push(i);
            } else {
                seen_connections.insert(key);
            }
        }
        for i in duplicates.into_iter().rev() {
            fixes_applied.push("Removed duplicate connection".to_string());
            fixed_connections.remove(i);
        }

        // Check for cycles (DAG validation)
        if has_cycle(&fixed_nodes, &fixed_connections) {
            errors.push("Workflow contains cycles - Gaea2 requires a DAG".to_string());
            is_valid = false;
        }

        // Strict mode: additional checks
        if strict_mode {
            // Check all nodes are connected
            let connected_nodes = get_connected_nodes(&fixed_connections);
            for node in &fixed_nodes {
                if !connected_nodes.contains(&node.id) && fixed_nodes.len() > 1 {
                    errors.push(format!("Node {} is not connected to the workflow", node.id));
                }
            }

            // Check for output nodes
            let has_output = fixed_nodes
                .iter()
                .any(|n| n.node_type == "Output" || n.node_type == "Export");
            if !has_output {
                errors.push("Workflow has no Output or Export node".to_string());
            }
        }

        ValidationResult {
            valid: is_valid || !fixes_applied.is_empty(),
            fixed: !fixes_applied.is_empty(),
            errors,
            fixes_applied,
            workflow: Workflow {
                nodes: fixed_nodes,
                connections: fixed_connections,
            },
        }
    }
}

/// Find a similar valid node type for suggestions.
fn find_similar_node_type(invalid_type: &str) -> Option<&'static str> {
    let invalid_lower = invalid_type.to_lowercase();

    // Common typos and alternatives
    let mappings = [
        ("erosion", "Erosion2"),
        ("mountain", "Mountain"),
        ("volcano", "Volcano"),
        ("noise", "Perlin"),
        ("blur", "Blur"),
        ("color", "QuickColor"),
        ("export", "Export"),
        ("output", "Output"),
        ("combine", "Combine"),
        ("mix", "Mixer"),
    ];

    for (pattern, suggestion) in mappings {
        if invalid_lower.contains(pattern) {
            return Some(suggestion);
        }
    }

    None
}

/// Check if the workflow has cycles (not a valid DAG).
fn has_cycle(nodes: &[Node], connections: &[Connection]) -> bool {
    // Build adjacency list
    let mut adj: HashMap<i32, Vec<i32>> = HashMap::new();
    for node in nodes {
        adj.insert(node.id, Vec::new());
    }
    for conn in connections {
        if let Some(neighbors) = adj.get_mut(&conn.from_node) {
            neighbors.push(conn.to_node);
        }
    }

    // DFS for cycle detection
    let mut visited = HashSet::new();
    let mut rec_stack = HashSet::new();

    fn dfs(
        node: i32,
        adj: &HashMap<i32, Vec<i32>>,
        visited: &mut HashSet<i32>,
        rec_stack: &mut HashSet<i32>,
    ) -> bool {
        visited.insert(node);
        rec_stack.insert(node);

        if let Some(neighbors) = adj.get(&node) {
            for &neighbor in neighbors {
                if !visited.contains(&neighbor) {
                    if dfs(neighbor, adj, visited, rec_stack) {
                        return true;
                    }
                } else if rec_stack.contains(&neighbor) {
                    return true;
                }
            }
        }

        rec_stack.remove(&node);
        false
    }

    for node in nodes {
        if !visited.contains(&node.id) && dfs(node.id, &adj, &mut visited, &mut rec_stack) {
            return true;
        }
    }

    false
}

/// Get all node IDs that appear in connections.
fn get_connected_nodes(connections: &[Connection]) -> HashSet<i32> {
    let mut connected = HashSet::new();
    for conn in connections {
        connected.insert(conn.from_node);
        connected.insert(conn.to_node);
    }
    connected
}

/// Normalize connections from various input formats.
pub fn normalize_connections(connections: Vec<serde_json::Value>) -> Vec<Connection> {
    let mut normalized = Vec::new();

    for conn in connections {
        let parsed = if conn.is_object() {
            let obj = conn.as_object().unwrap();

            // Handle various key formats
            let from_node = obj
                .get("from_node")
                .or_else(|| obj.get("from"))
                .or_else(|| obj.get("source"))
                .and_then(|v| v.as_i64())
                .unwrap_or(0) as i32;

            let to_node = obj
                .get("to_node")
                .or_else(|| obj.get("to"))
                .or_else(|| obj.get("target"))
                .and_then(|v| v.as_i64())
                .unwrap_or(0) as i32;

            let from_port = obj
                .get("from_port")
                .or_else(|| obj.get("source_port"))
                .and_then(|v| v.as_str())
                .unwrap_or("Out")
                .to_string();

            let to_port = obj
                .get("to_port")
                .or_else(|| obj.get("target_port"))
                .and_then(|v| v.as_str())
                .unwrap_or("In")
                .to_string();

            Connection {
                from_node,
                to_node,
                from_port,
                to_port,
            }
        } else if conn.is_array() {
            // Handle array format [from_id, to_id]
            let arr = conn.as_array().unwrap();
            let from_node = arr.get(0).and_then(|v| v.as_i64()).unwrap_or(0) as i32;
            let to_node = arr.get(1).and_then(|v| v.as_i64()).unwrap_or(0) as i32;

            Connection {
                from_node,
                to_node,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            }
        } else {
            continue;
        };

        if parsed.from_node != 0 && parsed.to_node != 0 {
            normalized.push(parsed);
        }
    }

    normalized
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_validate_empty_workflow() {
        let workflow = Workflow {
            nodes: vec![],
            connections: vec![],
        };

        let result = Validator::validate_and_fix(&workflow, false).await;
        assert!(result.valid);
        assert!(!result.fixed);
    }

    #[tokio::test]
    async fn test_validate_simple_workflow() {
        let workflow = Workflow {
            nodes: vec![
                Node {
                    id: 1,
                    node_type: "Mountain".to_string(),
                    name: "Mountain".to_string(),
                    position: Default::default(),
                    properties: Default::default(),
                    ports: None,
                    modifiers: None,
                    save_definition: None,
                },
                Node {
                    id: 2,
                    node_type: "Output".to_string(),
                    name: "Output".to_string(),
                    position: Default::default(),
                    properties: Default::default(),
                    ports: None,
                    modifiers: None,
                    save_definition: None,
                },
            ],
            connections: vec![Connection {
                from_node: 1,
                to_node: 2,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            }],
        };

        let result = Validator::validate_and_fix(&workflow, false).await;
        assert!(result.valid);
    }

    #[tokio::test]
    async fn test_detect_cycle() {
        let workflow = Workflow {
            nodes: vec![
                Node {
                    id: 1,
                    node_type: "Mountain".to_string(),
                    name: "".to_string(),
                    position: Default::default(),
                    properties: Default::default(),
                    ports: None,
                    modifiers: None,
                    save_definition: None,
                },
                Node {
                    id: 2,
                    node_type: "Blur".to_string(),
                    name: "".to_string(),
                    position: Default::default(),
                    properties: Default::default(),
                    ports: None,
                    modifiers: None,
                    save_definition: None,
                },
            ],
            connections: vec![
                Connection {
                    from_node: 1,
                    to_node: 2,
                    from_port: "Out".to_string(),
                    to_port: "In".to_string(),
                },
                Connection {
                    from_node: 2,
                    to_node: 1,
                    from_port: "Out".to_string(),
                    to_port: "In".to_string(),
                },
            ],
        };

        let result = Validator::validate_and_fix(&workflow, false).await;
        assert!(result.errors.iter().any(|e| e.contains("cycles")));
    }
}
