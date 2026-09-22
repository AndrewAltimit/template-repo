//! In-place analysis and repair of existing `.terrain` files.
//!
//! Repair operates directly on the JSON document so that everything the tool
//! does not understand (groups, notes, automation, build profiles, viewport
//! state) is preserved byte-for-byte in meaning. It fixes:
//!
//! * node dictionary keys that disagree with the node's `Id`
//! * misspelled node types in `$type` when there is an unambiguous match
//! * connection `Record`s pointing at missing nodes, at the node itself, or
//!   with a `To` that does not match the owning node
//! * `Required` flags left on input ports whose record was removed
//! * duplicate `$id` values (renumbers all ids and remaps `$ref`s)
//! * `Parent` references on ports that point at the wrong / missing node
//!
//! Problems that cannot be fixed safely (cycles, unknown node types, missing
//! source ports, dangling non-parent references) are reported, not guessed at.

use std::collections::{HashMap, HashSet};

use serde::Serialize;
use serde_json::{json, Map, Value};

use crate::schema::{is_valid_node_type, suggest_node_type};
use crate::types::{Connection, Node};
use crate::validation::find_cycle_nodes;

const TYPE_PREFIX: &str = "QuadSpinner.Gaea.Nodes.";
const TYPE_SUFFIX: &str = ", Gaea.Nodes";

/// Outcome of analysing/repairing a project document.
#[derive(Debug, Default, Serialize)]
pub struct RepairReport {
    /// Problems found (fixed or not).
    pub issues_found: Vec<String>,
    /// Fixes applied to the document.
    pub repairs_applied: Vec<String>,
    /// Problems that remain and need manual attention.
    pub unresolved: Vec<String>,
    pub node_count: usize,
    pub connection_count: usize,
}

impl RepairReport {
    fn fixed(&mut self, issue: String, fix: String) {
        self.issues_found.push(issue);
        self.repairs_applied.push(fix);
    }
    fn unresolved(&mut self, issue: String) {
        self.issues_found.push(issue.clone());
        self.unresolved.push(issue);
    }
}

/// Extract the node type name from a Json.NET `$type` string.
pub fn node_type_from_dollar_type(t: &str) -> Option<&str> {
    t.strip_prefix(TYPE_PREFIX)?.strip_suffix(TYPE_SUFFIX)
}

fn nodes_mut(project: &mut Value) -> Option<&mut Map<String, Value>> {
    project
        .get_mut("Assets")?
        .get_mut("$values")?
        .get_mut(0)?
        .get_mut("Terrain")?
        .get_mut("Nodes")?
        .as_object_mut()
}

/// Analyse and repair a project document in place.
///
/// Returns `Err` only when the document is not recognisably a Gaea2 project.
pub fn repair_project(project: &mut Value) -> Result<RepairReport, String> {
    let mut report = RepairReport::default();

    if !project.is_object() {
        return Err("not a Gaea2 project: top level must be a JSON object".to_string());
    }
    let nodes = nodes_mut(project).ok_or_else(|| {
        "not a Gaea2 project: missing Assets.$values[0].Terrain.Nodes".to_string()
    })?;

    // --- Pass 1: node keys, ids and types ------------------------------------
    let keys: Vec<String> = nodes.keys().filter(|k| *k != "$id").cloned().collect();
    let mut rekey: Vec<(String, String)> = Vec::new();
    for key in &keys {
        let Some(node) = nodes.get_mut(key).and_then(Value::as_object_mut) else {
            report.unresolved(format!("Nodes['{key}'] is not an object"));
            continue;
        };
        match node.get("Id").and_then(Value::as_i64) {
            Some(id) if id.to_string() == *key => {},
            Some(id) => {
                if nodes_has_other_key(&keys, &id.to_string(), key) {
                    report.unresolved(format!(
                        "Nodes['{key}'] has Id {id}, which is also used by another node"
                    ));
                } else {
                    report.fixed(
                        format!("Nodes['{key}'] is keyed differently from its Id {id}"),
                        format!("Re-keyed node '{key}' as '{id}'"),
                    );
                    rekey.push((key.clone(), id.to_string()));
                }
            },
            None => match key.parse::<i32>() {
                Ok(k) => {
                    node.insert("Id".to_string(), json!(k));
                    report.fixed(
                        format!("Node '{key}' has no numeric Id"),
                        format!("Set Id of node '{key}' to {k}"),
                    );
                },
                Err(_) => report.unresolved(format!(
                    "Node '{key}' has neither a numeric key nor a numeric Id"
                )),
            },
        }

        let type_str = node
            .get("$type")
            .and_then(Value::as_str)
            .map(str::to_string);
        match type_str.as_deref().and_then(node_type_from_dollar_type) {
            Some(t) if is_valid_node_type(t) => {},
            Some(t) => match suggest_node_type(t) {
                Some(s) => {
                    node.insert(
                        "$type".to_string(),
                        json!(format!("{TYPE_PREFIX}{s}{TYPE_SUFFIX}")),
                    );
                    report.fixed(
                        format!("Node '{key}' has unknown type '{t}'"),
                        format!("Changed type of node '{key}' from '{t}' to '{s}'"),
                    );
                },
                None => report.unresolved(format!("Node '{key}' has unknown type '{t}'")),
            },
            None => report.unresolved(format!(
                "Node '{key}' has a missing or malformed $type ({type_str:?})"
            )),
        }
    }
    for (old, new) in rekey {
        if let Some(v) = nodes.shift_remove(&old) {
            nodes.insert(new, v);
        }
    }

    // --- Pass 2: connection records -----------------------------------------
    let node_ids: HashSet<i64> = nodes
        .iter()
        .filter(|(k, _)| *k != "$id")
        .filter_map(|(_, v)| v.get("Id").and_then(Value::as_i64))
        .collect();
    // Output port names per node, for FromPort checks.
    let out_ports: HashMap<i64, HashSet<String>> = nodes
        .iter()
        .filter(|(k, _)| *k != "$id")
        .filter_map(|(_, v)| {
            let id = v.get("Id")?.as_i64()?;
            let names = port_values(v)
                .iter()
                .filter(|p| {
                    p.get("Type")
                        .and_then(Value::as_str)
                        .is_some_and(|t| t.split(',').next().unwrap_or("").trim().ends_with("Out"))
                })
                .filter_map(|p| p.get("Name").and_then(Value::as_str).map(str::to_string))
                .collect();
            Some((id, names))
        })
        .collect();

    let mut graph_nodes = Vec::new();
    let mut graph_conns = Vec::new();
    for (key, node) in nodes.iter_mut() {
        if key == "$id" {
            continue;
        }
        let Some(node_id) = node.get("Id").and_then(Value::as_i64) else {
            continue;
        };
        let node_ref = node.get("$id").cloned();
        graph_nodes.push(Node::new(node_id as i32, "Node"));

        let Some(ports) = node
            .get_mut("Ports")
            .and_then(|p| p.get_mut("$values"))
            .and_then(Value::as_array_mut)
        else {
            continue;
        };
        for port in ports.iter_mut().filter_map(Value::as_object_mut) {
            let port_name = port
                .get("Name")
                .and_then(Value::as_str)
                .unwrap_or("?")
                .to_string();

            // Parent reference must point at the owning node.
            if let (Some(nref), Some(parent)) = (&node_ref, port.get("Parent")) {
                if parent.get("$ref") != Some(nref) {
                    report.fixed(
                        format!("Port {node_id}.{port_name} has a wrong Parent reference"),
                        format!("Pointed Parent of port {node_id}.{port_name} at its node"),
                    );
                    port.insert("Parent".to_string(), json!({"$ref": nref}));
                }
            }

            let Some(record) = port.get_mut("Record").and_then(Value::as_object_mut) else {
                continue;
            };
            let from = record.get("From").and_then(Value::as_i64);
            let desc = format!("{node_id}.{port_name}");
            let remove_reason = match from {
                None => Some("has no numeric From".to_string()),
                Some(f) if f == node_id => Some("connects the node to itself".to_string()),
                Some(f) if !node_ids.contains(&f) => Some(format!("comes from missing node {f}")),
                _ => None,
            };
            if let Some(reason) = remove_reason {
                port.shift_remove("Record");
                if let Some(Value::String(t)) = port.get("Type").cloned() {
                    let stripped = t.replace(", Required", "");
                    port.insert("Type".to_string(), json!(stripped));
                }
                report.fixed(
                    format!("Connection into {desc} {reason}"),
                    format!("Removed invalid connection into {desc}"),
                );
                continue;
            }
            let from = from.unwrap_or_default();
            if record.get("To").and_then(Value::as_i64) != Some(node_id) {
                record.insert("To".to_string(), json!(node_id));
                report.fixed(
                    format!("Connection into {desc} has a mismatched To"),
                    format!("Set To of connection into {desc} to {node_id}"),
                );
            }
            if record.get("ToPort").and_then(Value::as_str) != Some(port_name.as_str()) {
                record.insert("ToPort".to_string(), json!(port_name));
                report.fixed(
                    format!("Connection into {desc} has a mismatched ToPort"),
                    format!("Set ToPort of connection into {desc} to '{port_name}'"),
                );
            }
            let from_port = record
                .get("FromPort")
                .and_then(Value::as_str)
                .unwrap_or("Out")
                .to_string();
            if let Some(outs) = out_ports.get(&from) {
                if !outs.is_empty() && !outs.contains(&from_port) {
                    report.unresolved(format!(
                        "Connection into {desc} uses output port '{from_port}' which node {from} does not have"
                    ));
                }
            }
            graph_conns.push(Connection::new(
                from as i32,
                &from_port,
                node_id as i32,
                &port_name,
            ));
        }
    }
    report.node_count = graph_nodes.len();
    report.connection_count = graph_conns.len();

    if let Some(cycle) = find_cycle_nodes(&graph_nodes, &graph_conns) {
        report.unresolved(format!(
            "Graph contains a cycle involving nodes {cycle:?}; remove one of the connections in Gaea2"
        ));
    }

    // --- Pass 3: $id uniqueness and $ref integrity ---------------------------
    let mut all_ids = Vec::new();
    crate::generation::collect_ref_ids(project, &mut all_ids);
    let unique: HashSet<&String> = all_ids.iter().collect();
    if unique.len() != all_ids.len() {
        let dupes = all_ids.len() - unique.len();
        renumber_ids(project);
        report.fixed(
            format!("{dupes} duplicate $id value(s)"),
            "Renumbered all $id values and remapped $ref references".to_string(),
        );
    }
    let mut ids = Vec::new();
    crate::generation::collect_ref_ids(project, &mut ids);
    let defined: HashSet<String> = ids.into_iter().collect();
    let mut dangling = Vec::new();
    collect_dangling_refs(project, &defined, &mut dangling);
    for r in dangling {
        report.unresolved(format!("Reference to undefined $id '{r}'"));
    }

    Ok(report)
}

fn nodes_has_other_key(keys: &[String], candidate: &str, own: &str) -> bool {
    keys.iter().any(|k| k == candidate && k != own)
}

fn port_values(node: &Value) -> Vec<Value> {
    node.get("Ports")
        .and_then(|p| p.get("$values"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default()
}

/// Renumber `$id`s in document order starting at 1. A `$ref` resolves to the
/// most recent definition of that id seen so far (Json.NET's reading order).
fn renumber_ids(project: &mut Value) {
    fn walk(v: &mut Value, next: &mut u64, map: &mut HashMap<String, String>) {
        match v {
            Value::Object(m) => {
                if let Some(Value::String(old)) = m.get("$id").cloned() {
                    let new = next.to_string();
                    *next += 1;
                    map.insert(old, new.clone());
                    m.insert("$id".to_string(), Value::String(new));
                }
                if let Some(Value::String(r)) = m.get("$ref").cloned() {
                    if let Some(new) = map.get(&r) {
                        m.insert("$ref".to_string(), Value::String(new.clone()));
                    }
                }
                for (k, child) in m.iter_mut() {
                    if k != "$id" && k != "$ref" {
                        walk(child, next, map);
                    }
                }
            },
            Value::Array(a) => a.iter_mut().for_each(|c| walk(c, next, map)),
            _ => {},
        }
    }
    let mut next = 1;
    let mut map = HashMap::new();
    walk(project, &mut next, &mut map);
}

fn collect_dangling_refs(v: &Value, defined: &HashSet<String>, out: &mut Vec<String>) {
    match v {
        Value::Object(m) => {
            if let Some(Value::String(r)) = m.get("$ref") {
                if !defined.contains(r) {
                    out.push(r.clone());
                }
            }
            m.values()
                .for_each(|c| collect_dangling_refs(c, defined, out));
        },
        Value::Array(a) => a
            .iter()
            .for_each(|c| collect_dangling_refs(c, defined, out)),
        _ => {},
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::generation::{build_project, collect_ref_ids, nodes_of, ProjectOptions};
    use crate::types::{BuildConfig, Workflow};

    fn project() -> Value {
        let wf = Workflow {
            nodes: vec![
                Node::new(100, "Mountain"),
                Node::new(101, "Erosion2"),
                Node::new(102, "Export"),
            ],
            connections: vec![
                Connection::new(100, "Out", 101, "In"),
                Connection::new(101, "Out", 102, "In"),
            ],
        };
        build_project(
            "t",
            &wf,
            &BuildConfig::default(),
            &ProjectOptions::default(),
        )
        .unwrap()
    }

    fn port_mut<'a>(p: &'a mut Value, node: &str, port: &str) -> &'a mut Value {
        nodes_mut(p).unwrap()[node]["Ports"]["$values"]
            .as_array_mut()
            .unwrap()
            .iter_mut()
            .find(|x| x["Name"] == port)
            .unwrap()
    }

    #[test]
    fn clean_project_needs_no_repairs() {
        let mut p = project();
        let before = p.clone();
        let r = repair_project(&mut p).unwrap();
        assert!(r.issues_found.is_empty(), "{:?}", r.issues_found);
        assert_eq!(r.node_count, 3);
        assert_eq!(r.connection_count, 2);
        assert_eq!(p, before);
    }

    #[test]
    fn removes_dangling_and_self_connections() {
        let mut p = project();
        port_mut(&mut p, "101", "In")["Record"]["From"] = json!(999);
        port_mut(&mut p, "102", "In")["Record"]["From"] = json!(102);
        let r = repair_project(&mut p).unwrap();
        assert_eq!(r.repairs_applied.len(), 2, "{:?}", r.repairs_applied);
        let port = port_mut(&mut p, "101", "In");
        assert!(port.get("Record").is_none());
        assert_eq!(port["Type"], "PrimaryIn");
        assert!(r.unresolved.is_empty());
    }

    #[test]
    fn fixes_types_keys_and_duplicate_ids() {
        let mut p = project();
        {
            let nodes = nodes_mut(&mut p).unwrap();
            nodes["100"]["$type"] = json!("QuadSpinner.Gaea.Nodes.mountain, Gaea.Nodes");
            let n = nodes.remove("102").unwrap();
            nodes.insert("555".to_string(), n);
            // Duplicate an $id
            nodes["101"]["Position"]["$id"] = json!("25");
        }
        let r = repair_project(&mut p).unwrap();
        assert!(r.unresolved.is_empty(), "{:?}", r.unresolved);
        let nodes = nodes_of(&p).unwrap();
        assert_eq!(
            nodes["100"]["$type"],
            "QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes"
        );
        assert!(nodes.contains_key("102"));
        let mut ids = Vec::new();
        collect_ref_ids(&p, &mut ids);
        let unique: HashSet<_> = ids.iter().collect();
        assert_eq!(unique.len(), ids.len());
        // Every $ref still resolves after renumbering.
        let defined: HashSet<String> = ids.into_iter().collect();
        let mut dangling = Vec::new();
        collect_dangling_refs(&p, &defined, &mut dangling);
        assert!(dangling.is_empty());
    }

    #[test]
    fn reports_cycles_and_unknown_types() {
        let mut p = project();
        // 102 -> 100 is impossible (Mountain has no In), so add one on Erosion2.
        {
            let port = port_mut(&mut p, "101", "Flow");
            port["Record"] = json!({"$id": "9000", "From": 102, "To": 101, "FromPort": "Out", "ToPort": "Flow", "IsValid": true});
            port["Type"] = json!("In");
        }
        {
            let port = port_mut(&mut p, "102", "In");
            port["Record"]["From"] = json!(101);
        }
        nodes_mut(&mut p).unwrap()["100"]["$type"] =
            json!("QuadSpinner.Gaea.Nodes.Qwertyuiop, Gaea.Nodes");
        let r = repair_project(&mut p).unwrap();
        assert!(
            r.unresolved.iter().any(|u| u.contains("cycle")),
            "{:?}",
            r.unresolved
        );
        assert!(r.unresolved.iter().any(|u| u.contains("Qwertyuiop")));
    }

    #[test]
    fn rejects_non_projects() {
        assert!(repair_project(&mut json!([1, 2])).is_err());
        assert!(repair_project(&mut json!({"a": 1})).is_err());
    }
}
