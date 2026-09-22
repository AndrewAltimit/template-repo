//! Workflow validation and auto-fixing for Gaea2 projects.
//!
//! The validator distinguishes three severities:
//! * **errors** - problems that would produce an invalid or broken `.terrain`
//!   file and that could not be fixed automatically (the workflow is invalid);
//! * **fixes** - problems that were corrected automatically (only when
//!   `auto_fix` is enabled; otherwise they are reported as errors);
//! * **warnings** - suspicious but loadable constructs (unknown properties,
//!   dangling nodes, color data fed into heightfield inputs, ...).

use std::collections::{BTreeMap, HashMap, HashSet, VecDeque};

use serde_json::{Map, Number, Value};

use crate::schema::{
    canonical_property_name, get_default_ports, is_generator_node, is_valid_node_type,
    outputs_color, port_direction, property_spec, property_specs, rejects_color_input,
    suggest_node_type, PortDirection, PropKind, RESERVED_PROPERTY_KEYS,
};
use crate::types::{Connection, Node, ValidationResult, Workflow};

/// Options controlling validation.
#[derive(Debug, Clone, Copy)]
pub struct ValidateOptions {
    /// Escalate completeness checks (unconnected nodes, missing Export,
    /// unconnected primary inputs) from warnings to errors.
    pub strict: bool,
    /// Apply automatic fixes. When false, fixable problems are errors.
    pub auto_fix: bool,
}

impl Default for ValidateOptions {
    fn default() -> Self {
        Self {
            strict: false,
            auto_fix: true,
        }
    }
}

/// Port table for a node: name -> gaea type string.
pub fn node_ports(node: &Node) -> Vec<(String, String)> {
    match &node.ports {
        Some(ports) => ports
            .iter()
            .map(|p| (p.name.clone(), p.port_type.clone()))
            .collect(),
        None => get_default_ports(&node.node_type)
            .into_iter()
            .map(|(n, t)| (n.to_string(), t.to_string()))
            .collect(),
    }
}

/// Find a port by name (exact match first, then case-insensitive) with the
/// given direction. Returns the canonical port name.
fn find_port(ports: &[(String, String)], name: &str, dir: PortDirection) -> Option<String> {
    let matches_dir = |t: &str| port_direction(t) == Some(dir);
    ports
        .iter()
        .find(|(n, t)| n == name && matches_dir(t))
        .or_else(|| {
            ports
                .iter()
                .find(|(n, t)| n.eq_ignore_ascii_case(name) && matches_dir(t))
        })
        .map(|(n, _)| n.clone())
}

fn port_names(ports: &[(String, String)], dir: PortDirection) -> Vec<&str> {
    ports
        .iter()
        .filter(|(_, t)| port_direction(t) == Some(dir))
        .map(|(n, _)| n.as_str())
        .collect()
}

/// Collector that routes fixable problems to `fixes` or `errors`.
struct Report {
    auto_fix: bool,
    errors: Vec<String>,
    warnings: Vec<String>,
    fixes: Vec<String>,
}

impl Report {
    /// Record a fixable problem. Returns true when the caller should apply the fix.
    fn fixable(&mut self, problem: String, fix: String) -> bool {
        if self.auto_fix {
            self.fixes.push(fix);
            true
        } else {
            self.errors.push(problem);
            false
        }
    }
}

/// Validator for Gaea2 workflows.
pub struct Validator;

impl Validator {
    /// Validate a workflow, applying automatic fixes when enabled.
    ///
    /// The returned `workflow` is the fixed workflow; `valid` is true when it
    /// contains no remaining blocking errors.
    pub fn validate_and_fix(workflow: &Workflow, opts: ValidateOptions) -> ValidationResult {
        let mut r = Report {
            auto_fix: opts.auto_fix,
            errors: Vec::new(),
            warnings: Vec::new(),
            fixes: Vec::new(),
        };
        let mut nodes = workflow.nodes.clone();
        let mut connections = workflow.connections.clone();

        if nodes.is_empty() {
            r.warnings.push("Workflow has no nodes".to_string());
        }

        // --- Node IDs -----------------------------------------------------
        let mut seen_ids = HashSet::new();
        for node in &nodes {
            if node.id < 0 {
                r.errors
                    .push(format!("Node id {} must not be negative", node.id));
            }
            if !seen_ids.insert(node.id) {
                r.errors.push(format!(
                    "Duplicate node id {} - every node needs a unique id",
                    node.id
                ));
            }
        }

        // --- Per-node checks ------------------------------------------------
        for node in nodes.iter_mut() {
            validate_node(node, &mut r);
        }

        // --- Connections ------------------------------------------------------
        let by_id: HashMap<i32, &Node> = nodes.iter().map(|n| (n.id, n)).collect();
        let mut kept: Vec<Connection> = Vec::with_capacity(connections.len());
        let mut seen_conns: HashSet<Connection> = HashSet::new();
        let mut input_owner: HashMap<(i32, String), Connection> = HashMap::new();

        for mut conn in connections.drain(..) {
            let desc = format!(
                "{}.{} -> {}.{}",
                conn.from_node, conn.from_port, conn.to_node, conn.to_port
            );
            let (Some(src), Some(dst)) = (by_id.get(&conn.from_node), by_id.get(&conn.to_node))
            else {
                let missing = if !by_id.contains_key(&conn.from_node) {
                    conn.from_node
                } else {
                    conn.to_node
                };
                if r.fixable(
                    format!("Connection {desc} references missing node {missing}"),
                    format!("Removed connection {desc} (node {missing} does not exist)"),
                ) {
                    continue;
                }
                kept.push(conn);
                continue;
            };

            if conn.from_node == conn.to_node {
                if r.fixable(
                    format!("Self-connection {desc}"),
                    format!("Removed self-connection {desc}"),
                ) {
                    continue;
                }
                kept.push(conn);
                continue;
            }

            let src_ports = node_ports(src);
            let dst_ports = node_ports(dst);
            let mut ok = true;

            match find_port(&src_ports, &conn.from_port, PortDirection::Output) {
                Some(p) if p == conn.from_port => {},
                Some(p) => {
                    if r.fixable(
                        format!(
                            "Connection {desc}: output port '{}' should be '{p}'",
                            conn.from_port
                        ),
                        format!(
                            "Connection {desc}: output port '{}' -> '{p}'",
                            conn.from_port
                        ),
                    ) {
                        conn.from_port = p;
                    }
                },
                None => {
                    ok = false;
                    r.errors.push(format!(
                        "Connection {desc}: {} ({}) has no output port '{}'. Available outputs: {:?}",
                        src.id,
                        src.node_type,
                        conn.from_port,
                        port_names(&src_ports, PortDirection::Output)
                    ));
                },
            }
            match find_port(&dst_ports, &conn.to_port, PortDirection::Input) {
                Some(p) if p == conn.to_port => {},
                Some(p) => {
                    if r.fixable(
                        format!(
                            "Connection {desc}: input port '{}' should be '{p}'",
                            conn.to_port
                        ),
                        format!("Connection {desc}: input port '{}' -> '{p}'", conn.to_port),
                    ) {
                        conn.to_port = p;
                    }
                },
                None => {
                    ok = false;
                    let inputs = port_names(&dst_ports, PortDirection::Input);
                    let hint = if inputs.is_empty() {
                        " (generator nodes take no inputs)".to_string()
                    } else {
                        format!(". Available inputs: {inputs:?}")
                    };
                    r.errors.push(format!(
                        "Connection {desc}: {} ({}) has no input port '{}'{hint}. Declare custom ports via the node's 'ports' field if needed",
                        dst.id, dst.node_type, conn.to_port
                    ));
                },
            }

            if seen_conns.contains(&conn)
                && r.fixable(
                    format!("Duplicate connection {desc}"),
                    format!("Removed duplicate connection {desc}"),
                )
            {
                continue;
            }
            seen_conns.insert(conn.clone());

            if ok {
                let key = (conn.to_node, conn.to_port.clone());
                if let Some(existing) = input_owner.get(&key) {
                    r.errors.push(format!(
                        "Input port {}.{} has multiple incoming connections (from {} and {}); a Gaea2 input accepts exactly one - use a Combine node to merge",
                        conn.to_node, conn.to_port, existing.from_node, conn.from_node
                    ));
                } else {
                    input_owner.insert(key, conn.clone());
                }

                if conn.from_port == "Out"
                    && outputs_color(&src.node_type)
                    && rejects_color_input(&dst.node_type)
                {
                    r.warnings.push(format!(
                        "Connection {desc}: {} outputs color data but {} expects a heightfield",
                        src.node_type, dst.node_type
                    ));
                }
            }
            kept.push(conn);
        }
        let connections = kept;

        // --- Cycles -------------------------------------------------------------
        if let Some(cycle_nodes) = find_cycle_nodes(&nodes, &connections) {
            r.errors.push(format!(
                "Workflow contains a cycle involving nodes {cycle_nodes:?} - Gaea2 graphs must be acyclic"
            ));
        }

        // --- Completeness (warnings, errors in strict mode) ----------------------
        let mut completeness = Vec::new();
        if nodes.len() > 1 {
            let connected: HashSet<i32> = connections
                .iter()
                .flat_map(|c| [c.from_node, c.to_node])
                .collect();
            for node in &nodes {
                if !connected.contains(&node.id) && !node.node_type.starts_with("Portal") {
                    completeness.push(format!(
                        "Node {} ({}) is not connected to the workflow",
                        node.id, node.node_type
                    ));
                }
            }
        }
        let connected_inputs: HashSet<(i32, &str)> = connections
            .iter()
            .map(|c| (c.to_node, c.to_port.as_str()))
            .collect();
        for node in &nodes {
            let ports = node_ports(node);
            let has_primary_in = ports.iter().any(|(_, t)| t.starts_with("PrimaryIn"));
            if has_primary_in
                && !is_generator_node(&node.node_type)
                && !connected_inputs.contains(&(node.id, "In"))
            {
                completeness.push(format!(
                    "Node {} ({}) has nothing connected to its primary 'In' port",
                    node.id, node.node_type
                ));
            }
        }
        if !nodes.is_empty()
            && !nodes.iter().any(|n| {
                matches!(
                    n.node_type.as_str(),
                    "Export" | "Output" | "Unity" | "Unreal"
                )
            })
        {
            completeness
                .push("Workflow has no Export node - a build will not write any files".to_string());
        }
        if opts.strict {
            r.errors.extend(completeness);
        } else {
            r.warnings.extend(completeness);
        }

        ValidationResult {
            valid: r.errors.is_empty(),
            fixed: !r.fixes.is_empty(),
            errors: r.errors,
            warnings: r.warnings,
            fixes_applied: r.fixes,
            workflow: Workflow { nodes, connections },
        }
    }
}

/// Validate and (optionally) fix a single node in place.
fn validate_node(node: &mut Node, r: &mut Report) {
    let label = format!("Node {}", node.id);

    // Type
    if !is_valid_node_type(&node.node_type) {
        match suggest_node_type(&node.node_type) {
            Some(suggestion) => {
                if r.fixable(
                    format!(
                        "{label} has invalid type '{}' (did you mean '{suggestion}'?)",
                        node.node_type
                    ),
                    format!("{label} type '{}' -> '{suggestion}'", node.node_type),
                ) {
                    node.node_type = suggestion.to_string();
                }
            },
            None => r.errors.push(format!(
                "{label} has invalid type '{}' - not a Gaea2 node type (see list_gaea2_nodes)",
                node.node_type
            )),
        }
    }

    if node.name.trim().is_empty() {
        node.name = node.node_type.clone();
    }

    // Explicit ports
    if let Some(ports) = &node.ports {
        let mut names = HashSet::new();
        for p in ports {
            if p.name.trim().is_empty() {
                r.errors
                    .push(format!("{label} has a port with an empty name"));
            }
            if port_direction(&p.port_type).is_none() {
                r.errors.push(format!(
                    "{label} port '{}' has invalid type '{}' (expected PrimaryIn, In, PrimaryOut or Out)",
                    p.name, p.port_type
                ));
            }
            if !names.insert(p.name.as_str()) {
                r.errors
                    .push(format!("{label} declares port '{}' twice", p.name));
            }
        }
    }

    // Save definition
    if let Some(sd) = &node.save_definition {
        if sd.format.trim().is_empty() {
            r.errors
                .push(format!("{label} save_definition.format must not be empty"));
        }
        if sd.filename.contains(['/', '\\', ':']) {
            r.errors.push(format!(
                "{label} save_definition.filename '{}' must be a bare file name (no path separators)",
                sd.filename
            ));
        }
    }

    // Properties
    let original = std::mem::take(&mut node.properties);
    let mut props = Map::new();
    for (key, value) in original {
        if RESERVED_PROPERTY_KEYS.contains(&key.as_str()) {
            let _ = r.fixable(
                format!("{label} property '{key}' is reserved and would corrupt the file"),
                format!("{label} removed reserved property '{key}'"),
            );
            if !r.auto_fix {
                props.insert(key, value);
            }
            continue;
        }
        if contains_reference_keys(&value) {
            r.errors.push(format!(
                "{label} property '{key}' contains '$ref'/'$type' keys, which are managed by the generator"
            ));
        }
        let key = match canonical_property_name(&key) {
            Some(canon) if !props.contains_key(&canon) => {
                if r.fixable(
                    format!("{label} property '{key}' should be '{canon}' (Gaea2 uses PascalCase names)"),
                    format!("{label} property '{key}' renamed to '{canon}'"),
                ) {
                    canon
                } else {
                    key
                }
            },
            _ => key,
        };
        let value = check_property(node, &label, &key, value, r);
        props.insert(key, value);
    }

    if let Some(specs) = property_specs(&node.node_type) {
        let unknown: Vec<&String> = props
            .keys()
            .filter(|k| {
                k.as_str() != "Seed"
                    && !specs.iter().any(|s| s.name == k.as_str())
                    && !matches!(k.as_str(), "X" | "Y" | "IsMaskable" | "NodeSize")
            })
            .collect();
        if !unknown.is_empty() {
            r.warnings.push(format!(
                "{label} ({}) has properties not in the known schema: {unknown:?}. Gaea2 ignores unknown properties",
                node.node_type
            ));
        }
    }
    node.properties = props;
}

fn contains_reference_keys(value: &Value) -> bool {
    match value {
        Value::Object(m) => {
            m.contains_key("$ref")
                || m.contains_key("$type")
                || m.values().any(contains_reference_keys)
        },
        Value::Array(a) => a.iter().any(contains_reference_keys),
        _ => false,
    }
}

/// Check (and possibly coerce/clamp) one property value against the schema.
fn check_property(node: &Node, label: &str, key: &str, value: Value, r: &mut Report) -> Value {
    let Some(spec) = property_spec(&node.node_type, key) else {
        return value;
    };
    // Seed only applies to generator nodes, but it is harmless elsewhere.
    let what = format!("{label} property {key}");
    match spec.kind {
        PropKind::Float { min, max } => {
            let Some(v) = as_number(&value) else {
                r.errors
                    .push(format!("{what} must be a number, got {value}"));
                return value;
            };
            let clamped = v.clamp(min, max);
            if clamped != v {
                if r.fixable(
                    format!("{what}={v} is outside [{min}, {max}]"),
                    format!("{what} clamped from {v} to {clamped}"),
                ) {
                    return json_f64(clamped);
                }
                return value;
            }
            if !value.is_number()
                && r.fixable(
                    format!("{what} is a string, expected a number"),
                    format!("{what} converted from string to number"),
                )
            {
                return json_f64(v);
            }
            value
        },
        PropKind::Int { min, max } => {
            let Some(v) = as_number(&value) else {
                r.errors
                    .push(format!("{what} must be an integer, got {value}"));
                return value;
            };
            let rounded = v.round();
            let clamped = rounded.clamp(min as f64, max as f64) as i64;
            let exact_int = value.as_i64().is_some();
            if (!exact_int || clamped as f64 != v)
                && r.fixable(
                    format!("{what}={value} must be an integer in [{min}, {max}]"),
                    format!("{what} changed from {value} to {clamped}"),
                )
            {
                return Value::from(clamped);
            }
            value
        },
        PropKind::Bool => match &value {
            Value::Bool(_) => value,
            Value::String(s)
                if s.eq_ignore_ascii_case("true") || s.eq_ignore_ascii_case("false") =>
            {
                let b = s.eq_ignore_ascii_case("true");
                if r.fixable(
                    format!("{what} is the string \"{s}\", expected a boolean"),
                    format!("{what} converted from string to boolean {b}"),
                ) {
                    return Value::Bool(b);
                }
                value
            },
            Value::Number(n) if n.as_i64() == Some(0) || n.as_i64() == Some(1) => {
                let b = n.as_i64() == Some(1);
                if r.fixable(
                    format!("{what} is a number, expected a boolean"),
                    format!("{what} converted from {n} to boolean {b}"),
                ) {
                    return Value::Bool(b);
                }
                value
            },
            _ => {
                r.errors
                    .push(format!("{what} must be a boolean, got {value}"));
                value
            },
        },
        PropKind::Enum { options } => {
            let Some(sv) = value.as_str() else {
                r.errors
                    .push(format!("{what} must be one of {options:?}, got {value}"));
                return value;
            };
            if options.contains(&sv) {
                return value;
            }
            if let Some(canon) = options.iter().find(|o| o.eq_ignore_ascii_case(sv)) {
                if r.fixable(
                    format!("{what}='{sv}' has the wrong case (expected '{canon}')"),
                    format!("{what} '{sv}' -> '{canon}'"),
                ) {
                    return Value::String(canon.to_string());
                }
                return value;
            }
            r.warnings.push(format!(
                "{what}='{sv}' is not a known option {options:?}; Gaea2 may reject it"
            ));
            value
        },
        PropKind::String => {
            if !value.is_string() {
                r.errors
                    .push(format!("{what} must be a string, got {value}"));
            }
            value
        },
    }
}

fn as_number(value: &Value) -> Option<f64> {
    match value {
        Value::Number(n) => n.as_f64(),
        Value::String(s) => s.trim().parse::<f64>().ok().filter(|f| f.is_finite()),
        _ => None,
    }
}

fn json_f64(v: f64) -> Value {
    Number::from_f64(v)
        .map(Value::Number)
        .unwrap_or(Value::Null)
}

/// Return the nodes that participate in (or are downstream of) a cycle, or
/// `None` if the graph is acyclic. Iterative Kahn's algorithm, so arbitrarily
/// long chains cannot overflow the stack.
pub fn find_cycle_nodes(nodes: &[Node], connections: &[Connection]) -> Option<Vec<i32>> {
    let order = topological_order(nodes, connections);
    if order.len() == nodes.len() {
        return None;
    }
    let done: HashSet<i32> = order.into_iter().collect();
    let mut remaining: Vec<i32> = nodes
        .iter()
        .map(|n| n.id)
        .filter(|id| !done.contains(id))
        .collect();
    remaining.sort_unstable();
    remaining.dedup();
    Some(remaining)
}

/// Kahn topological order over the node ids (nodes in cycles are omitted).
pub fn topological_order(nodes: &[Node], connections: &[Connection]) -> Vec<i32> {
    let mut indegree: BTreeMap<i32, usize> = nodes.iter().map(|n| (n.id, 0)).collect();
    let mut adj: HashMap<i32, Vec<i32>> = HashMap::new();
    for c in connections {
        if indegree.contains_key(&c.from_node) && indegree.contains_key(&c.to_node) {
            adj.entry(c.from_node).or_default().push(c.to_node);
            *indegree.entry(c.to_node).or_default() += 1;
        }
    }
    let mut queue: VecDeque<i32> = indegree
        .iter()
        .filter(|(_, d)| **d == 0)
        .map(|(id, _)| *id)
        .collect();
    let mut order = Vec::with_capacity(nodes.len());
    while let Some(id) = queue.pop_front() {
        order.push(id);
        if let Some(next) = adj.get(&id) {
            for n in next {
                if let Some(d) = indegree.get_mut(n) {
                    *d -= 1;
                    if *d == 0 {
                        queue.push_back(*n);
                    }
                }
            }
        }
    }
    order
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn node(id: i32, t: &str) -> Node {
        Node::new(id, t)
    }

    fn simple() -> Workflow {
        Workflow {
            nodes: vec![node(1, "Mountain"), node(2, "Erosion2"), node(3, "Export")],
            connections: vec![
                Connection::new(1, "Out", 2, "In"),
                Connection::new(2, "Out", 3, "In"),
            ],
        }
    }

    fn validate(w: &Workflow) -> ValidationResult {
        Validator::validate_and_fix(w, ValidateOptions::default())
    }

    #[test]
    fn empty_workflow_is_valid_with_warning() {
        let r = validate(&Workflow::default());
        assert!(r.valid);
        assert!(!r.fixed);
        assert!(!r.warnings.is_empty());
    }

    #[test]
    fn simple_workflow_is_clean() {
        let r = validate(&simple());
        assert!(r.valid, "{:?}", r.errors);
        assert!(!r.fixed, "{:?}", r.fixes_applied);
        assert!(r.warnings.is_empty(), "{:?}", r.warnings);
    }

    #[test]
    fn strict_mode_escalates_completeness() {
        let mut w = simple();
        w.nodes.push(node(4, "Blur"));
        let lax = validate(&w);
        assert!(lax.valid);
        assert!(lax.warnings.iter().any(|w| w.contains("not connected")));
        let strict = Validator::validate_and_fix(
            &w,
            ValidateOptions {
                strict: true,
                auto_fix: true,
            },
        );
        assert!(!strict.valid);
    }

    #[test]
    fn detects_cycle() {
        let w = Workflow {
            nodes: vec![node(1, "Blur"), node(2, "Adjust")],
            connections: vec![
                Connection::new(1, "Out", 2, "In"),
                Connection::new(2, "Out", 1, "In"),
            ],
        };
        let r = validate(&w);
        assert!(!r.valid);
        assert!(r.errors.iter().any(|e| e.contains("cycle")));
    }

    #[test]
    fn long_chain_does_not_overflow() {
        let n = 1000;
        let nodes: Vec<Node> = (0..n).map(|i| node(i, "Blur")).collect();
        let connections: Vec<Connection> = (0..n - 1)
            .map(|i| Connection::new(i, "Out", i + 1, "In"))
            .collect();
        assert!(find_cycle_nodes(&nodes, &connections).is_none());
    }

    #[test]
    fn fixes_type_typos_and_reports_unfixable() {
        let mut w = simple();
        w.nodes[1].node_type = "erosion2".into();
        let r = validate(&w);
        assert!(r.valid);
        assert_eq!(r.workflow.nodes[1].node_type, "Erosion2");

        w.nodes[1].node_type = "TotallyMadeUp".into();
        let r = validate(&w);
        assert!(!r.valid);
    }

    #[test]
    fn no_fix_mode_reports_errors_and_keeps_input() {
        let mut w = simple();
        w.nodes[1].node_type = "erosion2".into();
        let r = Validator::validate_and_fix(
            &w,
            ValidateOptions {
                strict: false,
                auto_fix: false,
            },
        );
        assert!(!r.valid);
        assert!(!r.fixed);
        assert_eq!(r.workflow.nodes[1].node_type, "erosion2");
    }

    #[test]
    fn fixes_do_not_mask_remaining_errors() {
        // One fixable problem (typo) and one unfixable (duplicate id).
        let mut w = simple();
        w.nodes[1].node_type = "erosion2".into();
        w.nodes.push(node(1, "Blur"));
        let r = validate(&w);
        assert!(r.fixed);
        assert!(!r.valid, "a fix must not make an invalid workflow valid");
    }

    #[test]
    fn removes_bad_connections() {
        let mut w = simple();
        w.connections.push(Connection::new(1, "Out", 99, "In"));
        w.connections.push(Connection::new(2, "Out", 2, "In"));
        w.connections.push(Connection::new(1, "Out", 2, "In"));
        let r = validate(&w);
        assert_eq!(r.workflow.connections.len(), 2);
        assert_eq!(r.fixes_applied.len(), 3);
        assert!(r.valid, "{:?}", r.errors);
    }

    #[test]
    fn port_checks() {
        // Unknown input port is an error (previously silently dropped).
        let mut w = simple();
        w.connections[1].to_port = "Bogus".into();
        let r = validate(&w);
        assert!(!r.valid);

        // Case mistakes are fixed.
        let mut w = simple();
        w.connections[0].from_port = "out".into();
        let r = validate(&w);
        assert!(r.valid, "{:?}", r.errors);
        assert_eq!(r.workflow.connections[0].from_port, "Out");

        // Generators take no input.
        let w = Workflow {
            nodes: vec![node(1, "Perlin"), node(2, "Mountain")],
            connections: vec![Connection::new(1, "Out", 2, "In")],
        };
        assert!(!validate(&w).valid);

        // Secondary outputs are valid sources.
        let mut w = simple();
        w.nodes.push(node(4, "Combine"));
        w.connections.push(Connection::new(2, "Flow", 4, "Mask"));
        w.connections.push(Connection::new(1, "Out", 4, "In"));
        let r = validate(&w);
        assert!(r.valid, "{:?}", r.errors);
    }

    #[test]
    fn multiple_inputs_to_one_port_is_error() {
        let mut w = simple();
        w.nodes.push(node(4, "Perlin"));
        w.connections.push(Connection::new(4, "Out", 3, "In"));
        let r = validate(&w);
        assert!(!r.valid);
        assert!(r.errors.iter().any(|e| e.contains("multiple incoming")));
    }

    #[test]
    fn property_checks_and_fixes() {
        let mut w = simple();
        w.nodes[1].properties = json!({
            "Duration": 50.0,
            "erosion scale": "6000",
            "Seed": 12.7,
            "Bogus": 1
        })
        .as_object()
        .unwrap()
        .clone();
        w.nodes[0].properties = json!({"Style": "alpine", "Id": 5, "ReduceDetails": "true"})
            .as_object()
            .unwrap()
            .clone();
        let r = validate(&w);
        assert!(r.valid, "{:?}", r.errors);
        let ero = &r.workflow.nodes[1].properties;
        assert_eq!(ero["Duration"], json!(2.0));
        assert_eq!(ero["ErosionScale"], json!(6000.0));
        assert_eq!(ero["Seed"], json!(13));
        let mtn = &r.workflow.nodes[0].properties;
        assert_eq!(mtn["Style"], json!("Alpine"));
        assert_eq!(mtn["ReduceDetails"], json!(true));
        assert!(!mtn.contains_key("Id"));
        assert!(r.warnings.iter().any(|w| w.contains("Bogus")));
    }

    #[test]
    fn wrong_property_type_is_error() {
        let mut w = simple();
        w.nodes[1].properties = json!({"Duration": "long"}).as_object().unwrap().clone();
        assert!(!validate(&w).valid);
    }

    #[test]
    fn color_into_heightfield_warns() {
        let w = Workflow {
            nodes: vec![node(1, "Mountain"), node(2, "SatMap"), node(3, "Erosion2")],
            connections: vec![
                Connection::new(1, "Out", 2, "In"),
                Connection::new(2, "Out", 3, "In"),
            ],
        };
        let r = validate(&w);
        assert!(r.warnings.iter().any(|w| w.contains("color")));
    }
}
