//! Parsing of user-supplied node and connection JSON.
//!
//! Tool arguments arrive as loosely-typed JSON written by agents, so this
//! module accepts a few common spellings (string IDs, `from`/`source` aliases,
//! `[from, to]` tuples) but never guesses silently: anything it cannot
//! interpret becomes an error naming the offending array index.

use std::collections::HashSet;

use serde_json::{Map, Value};

use crate::types::{Connection, Modifier, Node, PortDefinition, Position, SaveDefinition};

/// Upper bound on nodes in one workflow (guards against runaway inputs).
pub const MAX_NODES: usize = 1000;
/// Upper bound on connections in one workflow.
pub const MAX_CONNECTIONS: usize = 5000;

/// Parse a node ID from an integer, an integral float, or a numeric string.
pub fn parse_id(value: &Value) -> Result<i32, String> {
    let as_i64 = match value {
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Some(i)
            } else {
                n.as_f64()
                    .filter(|f| f.fract() == 0.0 && f.abs() < 1e12)
                    .map(|f| f as i64)
            }
        },
        Value::String(s) => s.trim().parse::<i64>().ok(),
        _ => None,
    };
    let id = as_i64.ok_or_else(|| format!("expected an integer node id, got {value}"))?;
    if !(0..=i64::from(i32::MAX)).contains(&id) {
        return Err(format!(
            "node id {id} is out of range (must be 0..={})",
            i32::MAX
        ));
    }
    Ok(id as i32)
}

/// Parse an array of node definitions.
///
/// Accepted keys per node: `id` (optional, int or numeric string), `type`
/// (required), `name`, `position` (`{x, y}` or `{X, Y}`), `properties`,
/// `ports`, `modifiers`, `save_definition`, `node_size`, `is_maskable`.
/// Nodes without an `id` get fresh IDs that do not collide with explicit ones.
pub fn parse_nodes(nodes_json: &[Value]) -> Result<Vec<Node>, String> {
    if nodes_json.len() > MAX_NODES {
        return Err(format!(
            "too many nodes ({}); the limit is {MAX_NODES}",
            nodes_json.len()
        ));
    }

    let mut nodes = Vec::with_capacity(nodes_json.len());
    let mut missing_id = Vec::new();

    for (i, node_val) in nodes_json.iter().enumerate() {
        let ctx = |msg: String| format!("nodes[{i}]: {msg}");
        let obj = node_val
            .as_object()
            .ok_or_else(|| ctx(format!("expected an object, got {node_val}")))?;

        let node_type = match obj.get("type").or_else(|| obj.get("node_type")) {
            Some(Value::String(s)) if !s.trim().is_empty() => s.trim().to_string(),
            Some(other) => {
                return Err(ctx(format!(
                    "'type' must be a non-empty string, got {other}"
                )))
            },
            None => {
                return Err(ctx(
                    "missing required 'type' (e.g. \"Mountain\")".to_string()
                ))
            },
        };

        let id = match obj.get("id") {
            Some(v) => parse_id(v).map_err(ctx)?,
            None => {
                missing_id.push(i);
                -1
            },
        };

        let name = match obj.get("name") {
            None | Some(Value::Null) => node_type.clone(),
            Some(Value::String(s)) => s.clone(),
            Some(other) => return Err(ctx(format!("'name' must be a string, got {other}"))),
        };

        let position = match obj.get("position") {
            None | Some(Value::Null) => None,
            Some(v @ Value::Object(_)) => Some(
                serde_json::from_value::<Position>(v.clone())
                    .map_err(|e| ctx(format!("invalid 'position': {e}")))?,
            ),
            Some(other) => {
                return Err(ctx(format!(
                    "'position' must be an object like {{\"x\": 25000, \"y\": 25000}}, got {other}"
                )))
            },
        };

        let properties = match obj.get("properties") {
            None | Some(Value::Null) => Map::new(),
            Some(Value::Object(m)) => m.clone(),
            Some(other) => return Err(ctx(format!("'properties' must be an object, got {other}"))),
        };

        let ports = optional_field::<Vec<PortDefinition>>(obj, "ports").map_err(ctx)?;
        let modifiers = optional_field::<Vec<Modifier>>(obj, "modifiers").map_err(ctx)?;
        let save_definition =
            optional_field::<SaveDefinition>(obj, "save_definition").map_err(ctx)?;
        let node_size = optional_field::<String>(obj, "node_size").map_err(ctx)?;
        let is_maskable = optional_field::<bool>(obj, "is_maskable").map_err(ctx)?;

        nodes.push(Node {
            id,
            node_type,
            name,
            position,
            properties,
            ports,
            modifiers,
            save_definition,
            node_size,
            is_maskable,
        });
    }

    // Assign IDs to nodes that did not specify one, avoiding explicit IDs.
    if !missing_id.is_empty() {
        let used: HashSet<i32> = nodes.iter().map(|n| n.id).filter(|id| *id >= 0).collect();
        let mut next = used.iter().copied().max().map_or(100, |m| m.max(99) + 1);
        for i in missing_id {
            while used.contains(&next) {
                next += 1;
            }
            nodes[i].id = next;
            next += 1;
        }
    }

    Ok(nodes)
}

fn optional_field<T: serde::de::DeserializeOwned>(
    obj: &Map<String, Value>,
    key: &str,
) -> Result<Option<T>, String> {
    match obj.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(v) => serde_json::from_value(v.clone())
            .map(Some)
            .map_err(|e| format!("invalid '{key}': {e}")),
    }
}

/// Parse an array of connections.
///
/// Accepted forms:
/// * `{"from_node": 1, "to_node": 2, "from_port": "Out", "to_port": "In"}`
///   (aliases: `from`/`source`, `to`/`target`, `source_port`, `target_port`)
/// * `[from, to]` or `[from, to, from_port, to_port]`
pub fn parse_connections(connections_json: &[Value]) -> Result<Vec<Connection>, String> {
    if connections_json.len() > MAX_CONNECTIONS {
        return Err(format!(
            "too many connections ({}); the limit is {MAX_CONNECTIONS}",
            connections_json.len()
        ));
    }

    let mut connections = Vec::with_capacity(connections_json.len());
    for (i, conn_val) in connections_json.iter().enumerate() {
        let ctx = |msg: String| format!("connections[{i}]: {msg}");
        let conn = match conn_val {
            Value::Object(obj) => {
                let pick = |keys: &[&str]| keys.iter().find_map(|k| obj.get(*k));
                let from_node = pick(&["from_node", "from", "source"])
                    .ok_or_else(|| ctx("missing 'from_node'".to_string()))
                    .and_then(|v| parse_id(v).map_err(ctx))?;
                let to_node = pick(&["to_node", "to", "target"])
                    .ok_or_else(|| ctx("missing 'to_node'".to_string()))
                    .and_then(|v| parse_id(v).map_err(ctx))?;
                let from_port = port_name(pick(&["from_port", "source_port"]), "Out")
                    .map_err(|e| ctx(format!("'from_port' {e}")))?;
                let to_port = port_name(pick(&["to_port", "target_port"]), "In")
                    .map_err(|e| ctx(format!("'to_port' {e}")))?;
                Connection {
                    from_node,
                    to_node,
                    from_port,
                    to_port,
                }
            },
            Value::Array(arr) if (2..=4).contains(&arr.len()) => Connection {
                from_node: parse_id(&arr[0]).map_err(ctx)?,
                to_node: parse_id(&arr[1]).map_err(ctx)?,
                from_port: port_name(arr.get(2), "Out")
                    .map_err(|e| ctx(format!("from port {e}")))?,
                to_port: port_name(arr.get(3), "In").map_err(|e| ctx(format!("to port {e}")))?,
            },
            other => {
                return Err(ctx(format!(
                    "expected an object {{from_node, to_node, from_port?, to_port?}} or an array [from, to], got {other}"
                )))
            },
        };
        connections.push(conn);
    }
    Ok(connections)
}

fn port_name(value: Option<&Value>, default: &str) -> Result<String, String> {
    match value {
        None | Some(Value::Null) => Ok(default.to_string()),
        Some(Value::String(s)) if !s.trim().is_empty() => Ok(s.trim().to_string()),
        Some(other) => Err(format!("must be a non-empty string, got {other}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn parses_basic_nodes() {
        let nodes = parse_nodes(&[
            json!({"id": 1, "type": "Mountain", "name": "Base"}),
            json!({"id": "2", "type": "Erosion2", "position": {"X": 10, "Y": 20}}),
        ])
        .unwrap();
        assert_eq!(nodes.len(), 2);
        assert_eq!(nodes[0].name, "Base");
        assert_eq!(nodes[1].id, 2);
        assert_eq!(nodes[1].name, "Erosion2");
        assert_eq!(nodes[1].position, Some(Position { x: 10.0, y: 20.0 }));
        assert_eq!(nodes[0].position, None);
    }

    #[test]
    fn auto_ids_do_not_collide() {
        let nodes = parse_nodes(&[
            json!({"type": "Mountain"}),
            json!({"id": 100, "type": "Erosion2"}),
            json!({"type": "Export"}),
        ])
        .unwrap();
        let ids: Vec<i32> = nodes.iter().map(|n| n.id).collect();
        assert_eq!(ids, vec![101, 100, 102]);
    }

    #[test]
    fn missing_type_is_an_error_not_a_mountain() {
        let err = parse_nodes(&[json!({"id": 1})]).unwrap_err();
        assert!(err.contains("nodes[0]") && err.contains("type"), "{err}");
    }

    #[test]
    fn rejects_bad_ids_and_shapes() {
        assert!(parse_nodes(&[json!({"id": "abc", "type": "Mountain"})]).is_err());
        assert!(parse_nodes(&[json!({"id": -5, "type": "Mountain"})]).is_err());
        assert!(parse_nodes(&[json!({"id": 1.5, "type": "Mountain"})]).is_err());
        assert!(parse_nodes(&[json!({"id": 99999999999i64, "type": "Mountain"})]).is_err());
        assert!(parse_nodes(&[json!("Mountain")]).is_err());
        assert!(parse_nodes(&[json!({"type": "Mountain", "properties": [1]})]).is_err());
        assert!(parse_nodes(&[json!({"type": "Mountain", "position": 5})]).is_err());
    }

    #[test]
    fn parses_ports_modifiers_and_save_definition() {
        let nodes = parse_nodes(&[json!({
            "id": 5,
            "type": "Export",
            "ports": [{"name": "In", "type": "PrimaryIn"}],
            "modifiers": [{"type": "Invert"}],
            "save_definition": {"filename": "height", "format": "EXR"}
        })])
        .unwrap();
        let n = &nodes[0];
        assert_eq!(n.ports.as_ref().unwrap().len(), 1);
        assert_eq!(n.modifiers.as_ref().unwrap()[0].modifier_type, "Invert");
        let sd = n.save_definition.as_ref().unwrap();
        assert_eq!(sd.format, "EXR");
        assert!(sd.enabled);
    }

    #[test]
    fn parses_connection_forms() {
        let conns = parse_connections(&[
            json!({"from_node": 1, "to_node": 2}),
            json!({"from": "3", "to": 4, "to_port": "Input2"}),
            json!({"source": 5, "target": 6, "source_port": "Flow", "target_port": "Mask"}),
            json!([7, 8]),
            json!([9, 10, "Wear", "Mask"]),
        ])
        .unwrap();
        assert_eq!(conns[0], Connection::new(1, "Out", 2, "In"));
        assert_eq!(conns[1], Connection::new(3, "Out", 4, "Input2"));
        assert_eq!(conns[2], Connection::new(5, "Flow", 6, "Mask"));
        assert_eq!(conns[3], Connection::new(7, "Out", 8, "In"));
        assert_eq!(conns[4], Connection::new(9, "Wear", 10, "Mask"));
    }

    #[test]
    fn rejects_bad_connections() {
        let err = parse_connections(&[json!({"from_node": 1})]).unwrap_err();
        assert!(
            err.contains("connections[0]") && err.contains("to_node"),
            "{err}"
        );
        assert!(parse_connections(&[json!([1])]).is_err());
        assert!(parse_connections(&[json!(["a", 2])]).is_err());
        assert!(parse_connections(&[json!({"from": 1, "to": 2, "to_port": 3})]).is_err());
        assert!(parse_connections(&[json!(42)]).is_err());
    }
}
