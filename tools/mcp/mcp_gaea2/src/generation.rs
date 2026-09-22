//! Project generation for Gaea2 `.terrain` files (Gaea2 2.2.6.0 format).
//!
//! Gaea2 project files are Json.NET documents serialized with
//! `PreserveReferencesHandling`: every object carries a unique `"$id"`, arrays
//! are wrapped as `{"$id": .., "$values": [..]}`, and back-references use
//! `{"$ref": "<id>"}`. Connections are not stored separately - each connected
//! *input* port of the receiving node carries a `Record` describing its source.
//!
//! [`build_project`] is a pure function (apart from random seeds for
//! generator nodes without one) so the produced document can be unit-tested;
//! [`write_project`] persists it atomically.

use std::collections::{HashMap, HashSet};
use std::path::Path;

use chrono::Utc;
use serde_json::{json, Map, Value};
use uuid::Uuid;

use crate::schema::{is_generator_node, port_direction, PortDirection, RESERVED_PROPERTY_KEYS};
use crate::types::{BuildConfig, Connection, Modifier, Node, Position, SaveDefinition, Workflow};
use crate::validation::{node_ports, topological_order};

/// Gaea2 file-format version written into project metadata.
pub const GAEA_VERSION: &str = "2.2.6.0";

/// First `$id` available for nodes; ids 1..=24 are used by the fixed skeleton.
const FIRST_NODE_REF_ID: u32 = 25;

/// Horizontal / vertical spacing used by auto-layout (graph units).
const LAYOUT_DX: f64 = 300.0;
const LAYOUT_DY: f64 = 250.0;
const LAYOUT_ORIGIN: f64 = 25000.0;

/// Optional project-level settings.
#[derive(Debug, Clone, Default)]
pub struct ProjectOptions {
    /// Free-form project description stored in metadata.
    pub description: String,
}

/// Sequential allocator for Json.NET `$id` values.
struct RefIds(u32);

impl RefIds {
    fn next(&mut self) -> String {
        let id = self.0;
        self.0 += 1;
        id.to_string()
    }
}

/// Build a Gaea2 project document from a workflow.
///
/// Performs the structural checks needed to guarantee a well-formed file
/// (unique node ids, existing connection endpoints and ports, one connection
/// per input port, no reserved property keys). Semantic validation lives in
/// [`crate::validation`]; callers should normally validate first.
pub fn build_project(
    project_name: &str,
    workflow: &Workflow,
    build_config: &BuildConfig,
    options: &ProjectOptions,
) -> Result<Value, String> {
    build_config.validate()?;
    check_structure(workflow)?;

    let project_id = Uuid::new_v4().simple().to_string();
    let terrain_id = Uuid::new_v4().to_string();
    let timestamp = Utc::now().format("%Y-%m-%d %H:%M:%SZ").to_string();

    // Incoming connection per (target node, input port).
    let incoming: HashMap<(i32, &str), &Connection> = workflow
        .connections
        .iter()
        .map(|c| ((c.to_node, c.to_port.as_str()), c))
        .collect();

    let positions = layout_positions(workflow);

    let mut ids = RefIds(FIRST_NODE_REF_ID);
    let mut nodes_dict = Map::new();
    nodes_dict.insert("$id".to_string(), json!("6"));
    for node in &workflow.nodes {
        let pos = positions.get(&node.id).copied().unwrap_or_default();
        let node_obj = create_node_object(node, pos, &incoming, &mut ids);
        nodes_dict.insert(node.id.to_string(), node_obj);
    }

    let bake = build_config.bake_resolution();
    let project = json!({
        "$id": "1",
        "Assets": {
            "$id": "2",
            "$values": [{
                "$id": "3",
                "Terrain": {
                    "$id": "4",
                    "Id": terrain_id,
                    "Metadata": {
                        "$id": "5",
                        "Name": project_name,
                        "Description": options.description,
                        "Version": GAEA_VERSION,
                        "DateCreated": timestamp,
                        "DateLastBuilt": timestamp,
                        "DateLastSaved": timestamp,
                        "ModifiedVersion": GAEA_VERSION
                    },
                    "Nodes": Value::Object(nodes_dict),
                    "Groups": {"$id": "7"},
                    "Notes": {"$id": "8"},
                    "GraphTabs": {
                        "$id": "9",
                        "$values": [{
                            "$id": "10",
                            "Name": "Graph 1",
                            "Color": "Brass",
                            "ZoomFactor": 0.6299605249474372,
                            "ViewportLocation": {
                                "$id": "11",
                                "X": 27690.082,
                                "Y": 25804.441
                            }
                        }]
                    },
                    "Width": 5000.0,
                    "Height": 2500.0,
                    "Ratio": 0.5,
                    "Regions": {"$id": "12", "$values": []}
                },
                "Automation": {
                    "$id": "13",
                    "Bindings": {"$id": "14", "$values": []},
                    "Expressions": {"$id": "15"},
                    "Variables": {"$id": "16"}
                },
                "BuildDefinition": {
                    "$id": "17",
                    "Type": build_config.build_type,
                    "Destination": "<Builds>\\[Filename]\\[+++]",
                    "Resolution": build_config.resolution,
                    "BakeResolution": bake,
                    "TileResolution": build_config.tile_resolution,
                    "BucketResolution": build_config.resolution,
                    "NumberOfTiles": build_config.number_of_tiles,
                    "EdgeBlending": build_config.edge_blending,
                    "TileZeroIndex": true,
                    "TilePattern": "_y%Y%_x%X%",
                    "OrganizeFiles": "NodeSubFolder",
                    "ColorSpace": build_config.color_space
                },
                "State": {
                    "$id": "18",
                    "BakeResolution": bake,
                    "PreviewResolution": 1024,
                    "HDResolution": 4096,
                    "SelectedNode": -1,
                    "NodeBookmarks": {"$id": "19", "$values": []},
                    "Viewport": {
                        "$id": "20",
                        "CameraPosition": {"$id": "21", "$values": []},
                        "Camera": {"$id": "22"},
                        "RenderMode": "Realistic",
                        "AmbientOcclusion": true,
                        "Shadows": true
                    }
                },
                "BuildProfiles": {"$id": "23"}
            }]
        },
        "Id": &project_id[..8],
        "Branch": 1,
        "Metadata": {
            "$id": "24",
            "Name": project_name,
            "Description": options.description,
            "Version": GAEA_VERSION,
            "Edition": "G2P",
            "Owner": "",
            "DateCreated": timestamp,
            "DateLastBuilt": timestamp,
            "DateLastSaved": timestamp,
            "ModifiedVersion": GAEA_VERSION
        }
    });

    Ok(project)
}

/// Hard structural requirements; violating any would produce a broken file
/// or silently lose data.
fn check_structure(workflow: &Workflow) -> Result<(), String> {
    let mut problems = Vec::new();
    let mut seen = HashSet::new();
    for node in &workflow.nodes {
        if !seen.insert(node.id) {
            problems.push(format!("duplicate node id {}", node.id));
        }
        for key in node.properties.keys() {
            if RESERVED_PROPERTY_KEYS.contains(&key.as_str()) {
                problems.push(format!(
                    "node {} uses reserved property key '{key}'",
                    node.id
                ));
            }
        }
    }

    let by_id: HashMap<i32, &Node> = workflow.nodes.iter().map(|n| (n.id, n)).collect();
    let mut used_inputs = HashSet::new();
    for c in &workflow.connections {
        let desc = format!(
            "{}.{} -> {}.{}",
            c.from_node, c.from_port, c.to_node, c.to_port
        );
        let (Some(src), Some(dst)) = (by_id.get(&c.from_node), by_id.get(&c.to_node)) else {
            problems.push(format!("connection {desc} references a missing node"));
            continue;
        };
        let has_port = |node: &Node, name: &str, dir: PortDirection| {
            node_ports(node)
                .iter()
                .any(|(n, t)| n == name && port_direction(t) == Some(dir))
        };
        if !has_port(src, &c.from_port, PortDirection::Output) {
            problems.push(format!(
                "connection {desc}: node {} ({}) has no output port '{}'",
                src.id, src.node_type, c.from_port
            ));
        }
        if !has_port(dst, &c.to_port, PortDirection::Input) {
            problems.push(format!(
                "connection {desc}: node {} ({}) has no input port '{}'",
                dst.id, dst.node_type, c.to_port
            ));
        }
        if !used_inputs.insert((c.to_node, c.to_port.as_str())) {
            problems.push(format!(
                "input port {}.{} has more than one incoming connection",
                c.to_node, c.to_port
            ));
        }
    }

    if problems.is_empty() {
        Ok(())
    } else {
        Err(format!("cannot generate project: {}", problems.join("; ")))
    }
}

/// Compute graph positions. Explicit positions are kept; the rest are laid out
/// in columns by their depth in the DAG so the graph is readable in Gaea2.
fn layout_positions(workflow: &Workflow) -> HashMap<i32, Position> {
    let mut depth: HashMap<i32, usize> = HashMap::new();
    let order = topological_order(&workflow.nodes, &workflow.connections);
    for id in &order {
        let d = workflow
            .connections
            .iter()
            .filter(|c| c.to_node == *id)
            .filter_map(|c| depth.get(&c.from_node).map(|d| d + 1))
            .max()
            .unwrap_or(0);
        depth.insert(*id, d);
    }

    let mut rows: HashMap<usize, usize> = HashMap::new();
    let mut out = HashMap::new();
    for node in &workflow.nodes {
        let pos = match node.position {
            Some(p) => p,
            None => {
                let col = depth.get(&node.id).copied().unwrap_or(0);
                let row = rows.entry(col).or_insert(0);
                let p = Position {
                    x: LAYOUT_ORIGIN + col as f64 * LAYOUT_DX,
                    y: LAYOUT_ORIGIN + *row as f64 * LAYOUT_DY,
                };
                *row += 1;
                p
            },
        };
        out.insert(node.id, pos);
    }
    out
}

/// Create a node object in Gaea2 format.
///
/// Key order follows reference files: `$id`, `$type`, node properties, `X`,
/// `Y`, `Seed`, `Id`, `Name`, `Position`, `Ports`, `Modifiers`,
/// `SaveDefinition`, `NodeSize`, `IsMaskable`.
fn create_node_object(
    node: &Node,
    position: Position,
    incoming: &HashMap<(i32, &str), &Connection>,
    ids: &mut RefIds,
) -> Value {
    let node_ref = ids.next();
    let mut obj = Map::new();
    obj.insert("$id".to_string(), json!(node_ref));
    obj.insert(
        "$type".to_string(),
        json!(format!(
            "QuadSpinner.Gaea.Nodes.{}, Gaea.Nodes",
            node.node_type
        )),
    );

    for (key, value) in &node.properties {
        obj.insert(key.clone(), convert_value(value, ids));
    }

    // Root-level X/Y are normalized (0-1) placement; keep user values.
    obj.entry("X").or_insert(json!(0.5));
    obj.entry("Y").or_insert(json!(0.5));

    if is_generator_node(&node.node_type) && !obj.contains_key("Seed") {
        let seed: u32 = rand::random::<u32>() % 90000 + 10000;
        obj.insert("Seed".to_string(), json!(seed));
    }

    obj.insert("Id".to_string(), json!(node.id));
    let name = if node.name.trim().is_empty() {
        node.node_type.as_str()
    } else {
        node.name.as_str()
    };
    obj.insert("Name".to_string(), json!(name));
    obj.insert(
        "Position".to_string(),
        json!({"$id": ids.next(), "X": position.x, "Y": position.y}),
    );

    // Ports, with connection records embedded in connected input ports.
    let ports_id = ids.next();
    let mut port_values = Vec::new();
    for (port_name, port_type) in node_ports(node) {
        let mut port = Map::new();
        port.insert("$id".to_string(), json!(ids.next()));
        port.insert("Name".to_string(), json!(port_name));
        let connection = incoming.get(&(node.id, port_name.as_str()));
        let is_input = port_direction(&port_type) == Some(PortDirection::Input);
        let port_type = if connection.is_some() && is_input && !port_type.contains("Required") {
            format!("{port_type}, Required")
        } else {
            port_type
        };
        port.insert("Type".to_string(), json!(port_type));
        port.insert("IsExporting".to_string(), json!(true));
        port.insert("Parent".to_string(), json!({"$ref": node_ref}));
        if let Some(state) = node
            .ports
            .as_ref()
            .and_then(|ps| ps.iter().find(|p| p.name == port_name))
            .and_then(|p| p.portal_state.clone())
        {
            port.insert("PortalState".to_string(), json!(state));
        }
        if let Some(conn) = connection.filter(|_| is_input) {
            port.insert(
                "Record".to_string(),
                json!({
                    "$id": ids.next(),
                    "From": conn.from_node,
                    "To": conn.to_node,
                    "FromPort": conn.from_port,
                    "ToPort": conn.to_port,
                    "IsValid": true
                }),
            );
        }
        port_values.push(Value::Object(port));
    }
    obj.insert(
        "Ports".to_string(),
        json!({"$id": ports_id, "$values": port_values}),
    );

    let modifiers_id = ids.next();
    let modifier_values: Vec<Value> = node
        .modifiers
        .iter()
        .flatten()
        .map(|m| create_modifier_object(m, &node_ref, ids))
        .collect();
    obj.insert(
        "Modifiers".to_string(),
        json!({"$id": modifiers_id, "$values": modifier_values}),
    );

    if let Some(sd) = &node.save_definition {
        obj.insert(
            "SaveDefinition".to_string(),
            create_save_definition(sd, node.id, name, ids),
        );
    }
    if let Some(size) = &node.node_size {
        obj.insert("NodeSize".to_string(), json!(size));
    }
    obj.entry("IsMaskable")
        .or_insert(json!(node.is_maskable.unwrap_or(true)));

    Value::Object(obj)
}

fn create_modifier_object(m: &Modifier, node_ref: &str, ids: &mut RefIds) -> Value {
    let mut obj = Map::new();
    obj.insert("$id".to_string(), json!(ids.next()));
    obj.insert(
        "$type".to_string(),
        json!(format!(
            "QuadSpinner.Gaea.Nodes.Modifiers.{}, Gaea.Nodes",
            m.modifier_type
        )),
    );
    obj.insert("Name".to_string(), json!(m.modifier_type));
    obj.insert("Parent".to_string(), json!({"$ref": node_ref}));
    obj.insert("Intrinsic".to_string(), json!(true));
    for (key, value) in &m.properties {
        if RESERVED_PROPERTY_KEYS.contains(&key.as_str()) || key == "Parent" {
            continue;
        }
        obj.insert(key.clone(), convert_value(value, ids));
    }
    if m.has_ui {
        obj.insert("HasUI".to_string(), json!(true));
    }
    if let Some(order) = m.order {
        obj.insert("Order".to_string(), json!(order));
    }
    Value::Object(obj)
}

fn create_save_definition(
    sd: &SaveDefinition,
    node_id: i32,
    node_name: &str,
    ids: &mut RefIds,
) -> Value {
    let filename = if sd.filename.trim().is_empty() {
        node_name
    } else {
        sd.filename.as_str()
    };
    json!({
        "$id": ids.next(),
        "Node": node_id,
        "Filename": filename,
        "Format": sd.format,
        "IsEnabled": sd.enabled,
        "DisabledInProfiles": {"$id": ids.next(), "$values": sd.disabled_profiles}
    })
}

/// Convert a user property value into Json.NET reference-preserving form.
///
/// * `{x, y}` / `{X, Y}` pairs become `{"$id", "X", "Y"}` (Gaea2 ranges/points)
/// * other objects get a fresh `$id` (any user `$id` is replaced)
/// * arrays become `{"$id", "$values": [...]}`
/// * scalars pass through unchanged
fn convert_value(value: &Value, ids: &mut RefIds) -> Value {
    match value {
        Value::Object(m) => {
            let get = |k: &str| {
                m.iter()
                    .find(|(key, _)| key.eq_ignore_ascii_case(k))
                    .and_then(|(_, v)| v.as_f64())
            };
            let is_point = m.len() == 2 && get("x").is_some() && get("y").is_some();
            if is_point {
                return json!({
                    "$id": ids.next(),
                    "X": get("x").unwrap_or_default(),
                    "Y": get("y").unwrap_or_default()
                });
            }
            let mut out = Map::new();
            out.insert("$id".to_string(), json!(ids.next()));
            for (k, v) in m {
                if k == "$id" {
                    continue;
                }
                out.insert(k.clone(), convert_value(v, ids));
            }
            Value::Object(out)
        },
        Value::Array(items) => {
            let id = ids.next();
            let values: Vec<Value> = items.iter().map(|v| convert_value(v, ids)).collect();
            json!({"$id": id, "$values": values})
        },
        other => other.clone(),
    }
}

/// Serialize and write a project atomically (temp file + rename).
pub async fn write_project(path: &Path, project: &Value) -> Result<u64, String> {
    if let Some(parent) = path.parent() {
        tokio::fs::create_dir_all(parent)
            .await
            .map_err(|e| format!("Failed to create directory {}: {e}", parent.display()))?;
    }
    let content = serde_json::to_string_pretty(project)
        .map_err(|e| format!("Failed to serialize project: {e}"))?;
    let tmp = path.with_extension(format!("tmp-{}", Uuid::new_v4().simple()));
    tokio::fs::write(&tmp, content.as_bytes())
        .await
        .map_err(|e| format!("Failed to write {}: {e}", tmp.display()))?;
    if let Err(e) = tokio::fs::rename(&tmp, path).await {
        let _ = tokio::fs::remove_file(&tmp).await;
        return Err(format!(
            "Failed to move project into place at {}: {e}",
            path.display()
        ));
    }
    Ok(content.len() as u64)
}

/// Walk a document and collect every `$id` value (used by tests and repair).
pub fn collect_ref_ids(value: &Value, out: &mut Vec<String>) {
    match value {
        Value::Object(m) => {
            if let Some(Value::String(id)) = m.get("$id") {
                out.push(id.clone());
            }
            for v in m.values() {
                collect_ref_ids(v, out);
            }
        },
        Value::Array(a) => a.iter().for_each(|v| collect_ref_ids(v, out)),
        _ => {},
    }
}

/// Locate the `Nodes` dictionary of a Gaea2 project document.
#[cfg(test)]
pub fn nodes_of(project: &Value) -> Option<&Map<String, Value>> {
    project
        .get("Assets")?
        .get("$values")?
        .get(0)?
        .get("Terrain")?
        .get("Nodes")?
        .as_object()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::PortDefinition;

    fn wf() -> Workflow {
        let mut m = Node::new(100, "Mountain");
        m.properties.insert("Scale".into(), json!(1.5));
        m.properties
            .insert("Range".into(), json!({"x": 0.2, "y": 0.8}));
        let e = Node::new(101, "Erosion2");
        let mut x = Node::new(102, "Export");
        x.save_definition = Some(SaveDefinition {
            filename: "height".into(),
            format: "EXR".into(),
            enabled: true,
            disabled_profiles: vec![],
        });
        Workflow {
            nodes: vec![m, e, x],
            connections: vec![
                Connection::new(100, "Out", 101, "In"),
                Connection::new(101, "Out", 102, "In"),
            ],
        }
    }

    fn build(w: &Workflow) -> Result<Value, String> {
        build_project(
            "test",
            w,
            &BuildConfig::default(),
            &ProjectOptions::default(),
        )
    }

    #[test]
    fn ref_ids_are_unique_and_refs_resolve() {
        let p = build(&wf()).unwrap();
        let mut ids = Vec::new();
        collect_ref_ids(&p, &mut ids);
        let unique: HashSet<_> = ids.iter().collect();
        assert_eq!(unique.len(), ids.len(), "duplicate $id in {ids:?}");

        fn refs(v: &Value, out: &mut Vec<String>) {
            match v {
                Value::Object(m) => {
                    if let Some(Value::String(r)) = m.get("$ref") {
                        out.push(r.clone());
                    }
                    m.values().for_each(|v| refs(v, out));
                },
                Value::Array(a) => a.iter().for_each(|v| refs(v, out)),
                _ => {},
            }
        }
        let mut rs = Vec::new();
        refs(&p, &mut rs);
        assert!(!rs.is_empty());
        for r in rs {
            assert!(unique.contains(&r), "dangling $ref {r}");
        }
    }

    #[test]
    fn metadata_keys_come_first() {
        let p = build(&wf()).unwrap();
        let nodes = nodes_of(&p).unwrap();
        let node = nodes["100"].as_object().unwrap();
        let keys: Vec<&String> = node.keys().collect();
        assert_eq!(keys[0], "$id");
        assert_eq!(keys[1], "$type");
        assert_eq!(node["$type"], "QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes");
        assert_eq!(nodes.keys().next().unwrap(), "$id");
    }

    #[test]
    fn connections_become_records_on_input_ports() {
        let p = build(&wf()).unwrap();
        let nodes = nodes_of(&p).unwrap();
        let ports = nodes["101"]["Ports"]["$values"].as_array().unwrap();
        let input = ports.iter().find(|p| p["Name"] == "In").unwrap();
        assert_eq!(input["Type"], "PrimaryIn, Required");
        assert_eq!(input["Record"]["From"], 100);
        assert_eq!(input["Record"]["To"], 101);
        assert_eq!(input["Record"]["FromPort"], "Out");
        // Output ports never carry records.
        let out = ports.iter().find(|p| p["Name"] == "Out").unwrap();
        assert!(out.get("Record").is_none());
    }

    #[test]
    fn save_definition_and_seed_and_ranges() {
        let p = build(&wf()).unwrap();
        let nodes = nodes_of(&p).unwrap();
        let sd = &nodes["102"]["SaveDefinition"];
        assert_eq!(sd["Filename"], "height");
        assert_eq!(sd["Format"], "EXR");
        assert_eq!(sd["Node"], 102);
        assert!(sd["DisabledInProfiles"]["$values"].is_array());

        let seed = nodes["100"]["Seed"].as_u64().unwrap();
        assert!((10000..100000).contains(&seed));
        assert!(nodes["102"].get("Seed").is_none());

        let range = &nodes["100"]["Range"];
        assert_eq!(range["X"], 0.2);
        assert_eq!(range["Y"], 0.8);
        assert!(range["$id"].is_string());
    }

    #[test]
    fn user_xy_and_seed_are_not_clobbered() {
        let mut w = wf();
        w.nodes[0].properties.insert("X".into(), json!(0.25));
        w.nodes[0].properties.insert("Seed".into(), json!(42));
        let p = build(&w).unwrap();
        let n = &nodes_of(&p).unwrap()["100"];
        assert_eq!(n["X"], 0.25);
        assert_eq!(n["Y"], 0.5);
        assert_eq!(n["Seed"], 42);
    }

    #[test]
    fn rejects_structural_problems() {
        let mut w = wf();
        w.nodes.push(Node::new(100, "Blur"));
        assert!(build(&w).unwrap_err().contains("duplicate node id"));

        let mut w = wf();
        w.connections
            .push(Connection::new(100, "Out", 102, "Bogus"));
        assert!(build(&w).unwrap_err().contains("no input port"));

        let mut w = wf();
        w.connections.push(Connection::new(100, "Out", 102, "In"));
        assert!(build(&w).unwrap_err().contains("more than one"));

        let mut w = wf();
        w.nodes[0].properties.insert("$id".into(), json!("1"));
        assert!(build(&w).unwrap_err().contains("reserved"));

        let bad = BuildConfig {
            resolution: 1000,
            ..Default::default()
        };
        assert!(build_project("t", &wf(), &bad, &ProjectOptions::default()).is_err());
    }

    #[test]
    fn custom_ports_are_used() {
        let mut w = wf();
        w.nodes[1].ports = Some(vec![
            PortDefinition {
                name: "In".into(),
                port_type: "PrimaryIn".into(),
                portal_state: None,
            },
            PortDefinition {
                name: "Precipitation".into(),
                port_type: "In".into(),
                portal_state: None,
            },
            PortDefinition {
                name: "Out".into(),
                port_type: "PrimaryOut".into(),
                portal_state: None,
            },
        ]);
        w.nodes.push(Node::new(103, "Perlin"));
        w.connections
            .push(Connection::new(103, "Out", 101, "Precipitation"));
        let p = build(&w).unwrap();
        let ports = nodes_of(&p).unwrap()["101"]["Ports"]["$values"]
            .as_array()
            .unwrap()
            .clone();
        let precip = ports.iter().find(|p| p["Name"] == "Precipitation").unwrap();
        assert_eq!(precip["Record"]["From"], 103);
    }

    #[test]
    fn auto_layout_places_nodes_in_columns() {
        let p = build(&wf()).unwrap();
        let nodes = nodes_of(&p).unwrap();
        let x = |id: &str| nodes[id]["Position"]["X"].as_f64().unwrap();
        assert!(x("100") < x("101") && x("101") < x("102"));
    }

    #[test]
    fn modifiers_are_emitted() {
        let mut w = wf();
        w.nodes[1].modifiers = Some(vec![Modifier {
            modifier_type: "Height".into(),
            properties: json!({"Range": {"x": 0.4, "y": 0.5}, "Falloff": 0.15})
                .as_object()
                .unwrap()
                .clone(),
            order: Some(3),
            has_ui: true,
        }]);
        let p = build(&w).unwrap();
        let m = &nodes_of(&p).unwrap()["101"]["Modifiers"]["$values"][0];
        assert_eq!(
            m["$type"],
            "QuadSpinner.Gaea.Nodes.Modifiers.Height, Gaea.Nodes"
        );
        assert_eq!(m["Falloff"], 0.15);
        assert_eq!(m["Range"]["X"], 0.4);
        assert_eq!(m["Order"], 3);
        assert_eq!(m["HasUI"], true);
    }

    #[tokio::test]
    async fn write_project_is_atomic_and_readable() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("sub").join("a.terrain");
        let p = build(&wf()).unwrap();
        let size = write_project(&path, &p).await.unwrap();
        assert!(size > 0);
        let back: Value = serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(back, p);
        let leftovers: Vec<_> = std::fs::read_dir(path.parent().unwrap())
            .unwrap()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_name().to_string_lossy().contains("tmp-"))
            .collect();
        assert!(leftovers.is_empty());
    }
}
