//! Project generation for Gaea2 terrain files.
//!
//! Generates .terrain files in Gaea2 2.2.6.0 format.

use std::collections::HashMap;
use std::path::Path;

use chrono::Utc;
use serde_json::{json, Value};
use uuid::Uuid;

use crate::schema::{get_default_ports, is_generator_node};
use crate::types::{BuildConfig, Connection, Node, Position, Workflow};

/// Generate a Gaea2 project file from a workflow.
pub async fn generate_project(
    project_name: &str,
    workflow: &Workflow,
    build_config: Option<BuildConfig>,
    output_path: Option<&str>,
) -> Result<Value, String> {
    let project_id = Uuid::new_v4().to_string();
    let terrain_id = Uuid::new_v4().to_string();
    let timestamp = Utc::now().format("%Y-%m-%d %H:%M:%SZ").to_string();

    let build_config = build_config.unwrap_or_default();

    // Create project structure matching Gaea2 2.2.6.0 format
    let mut ref_id_counter = 25;

    // Process nodes
    let mut nodes_dict = serde_json::Map::new();
    nodes_dict.insert("$id".to_string(), json!("6"));

    for node in &workflow.nodes {
        let (node_obj, next_ref) = create_node_object(node, ref_id_counter)?;
        nodes_dict.insert(node.id.to_string(), node_obj);
        ref_id_counter = next_ref;
    }

    // Add connections to nodes
    for conn in &workflow.connections {
        add_connection_to_nodes(&mut nodes_dict, conn, &mut ref_id_counter);
    }

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
                        "Description": "",
                        "Version": "2.2.6.0",
                        "DateCreated": timestamp,
                        "DateLastBuilt": timestamp,
                        "DateLastSaved": timestamp,
                        "ModifiedVersion": "2.2.6.0"
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
                    "BakeResolution": build_config.bake_resolution,
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
                    "BakeResolution": 2048,
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
            "Description": "",
            "Version": "2.2.6.0",
            "Edition": "G2P",
            "Owner": "",
            "DateCreated": timestamp,
            "DateLastBuilt": timestamp,
            "DateLastSaved": timestamp,
            "ModifiedVersion": "2.2.6.0"
        }
    });

    // Write to file if output path provided
    if let Some(path) = output_path {
        let path = Path::new(path);
        if let Some(parent) = path.parent() {
            tokio::fs::create_dir_all(parent)
                .await
                .map_err(|e| format!("Failed to create directory: {}", e))?;
        }
        let content = serde_json::to_string_pretty(&project)
            .map_err(|e| format!("Failed to serialize project: {}", e))?;
        tokio::fs::write(path, content)
            .await
            .map_err(|e| format!("Failed to write file: {}", e))?;
    }

    Ok(project)
}

/// Create a node object in Gaea2 format.
fn create_node_object(node: &Node, mut ref_id_counter: u32) -> Result<(Value, u32), String> {
    let node_id_ref = ref_id_counter.to_string();

    let mut node_obj = serde_json::Map::new();

    // Required identifiers
    node_obj.insert("$id".to_string(), json!(node_id_ref));
    node_obj.insert(
        "$type".to_string(),
        json!(format!(
            "QuadSpinner.Gaea.Nodes.{}, Gaea.Nodes",
            node.node_type
        )),
    );

    // Node-specific properties
    for (key, value) in &node.properties {
        node_obj.insert(key.clone(), value.clone());
    }

    // Root-level X/Y (normalized 0-1)
    node_obj.insert("X".to_string(), json!(0.5));
    node_obj.insert("Y".to_string(), json!(0.5));

    // Seed for generator nodes
    if is_generator_node(&node.node_type) && !node.properties.contains_key("Seed") {
        let seed = rand::random::<u32>() % 90000 + 10000;
        node_obj.insert("Seed".to_string(), json!(seed));
    }

    // Standard properties
    node_obj.insert("Id".to_string(), json!(node.id));
    node_obj.insert("Name".to_string(), json!(node.name));

    ref_id_counter += 1;
    node_obj.insert(
        "Position".to_string(),
        json!({
            "$id": ref_id_counter.to_string(),
            "X": node.position.x,
            "Y": node.position.y
        }),
    );

    ref_id_counter += 1;
    let ports_id = ref_id_counter.to_string();
    ref_id_counter += 1;
    let modifiers_id = ref_id_counter.to_string();
    ref_id_counter += 1;

    // Create ports
    let port_defs = node.ports.as_ref().map(|p| {
        p.iter()
            .map(|pd| (pd.name.as_str(), pd.port_type.as_str()))
            .collect::<Vec<_>>()
    });
    let default_ports = get_default_ports(&node.node_type);
    let ports_to_use = port_defs.as_deref().unwrap_or(&default_ports);

    let mut port_values = Vec::new();
    for (port_name, port_type) in ports_to_use {
        let port = json!({
            "$id": ref_id_counter.to_string(),
            "Name": port_name,
            "Type": port_type,
            "IsExporting": true,
            "Parent": {"$ref": node_id_ref}
        });
        port_values.push(port);
        ref_id_counter += 1;
    }

    node_obj.insert(
        "Ports".to_string(),
        json!({
            "$id": ports_id,
            "$values": port_values
        }),
    );

    // Modifiers (empty by default)
    let modifier_values: Vec<Value> = if let Some(modifiers) = &node.modifiers {
        modifiers
            .iter()
            .map(|m| {
                let mod_obj = json!({
                    "$id": ref_id_counter.to_string(),
                    "$type": format!("QuadSpinner.Gaea.Nodes.Modifiers.{}, Gaea.Nodes", m.modifier_type),
                    "Name": m.modifier_type,
                    "Parent": {"$ref": node_id_ref},
                    "Intrinsic": true
                });
                ref_id_counter += 1;
                mod_obj
            })
            .collect()
    } else {
        vec![]
    };

    node_obj.insert(
        "Modifiers".to_string(),
        json!({
            "$id": modifiers_id,
            "$values": modifier_values
        }),
    );

    Ok((Value::Object(node_obj), ref_id_counter))
}

/// Add a connection to the nodes in the project.
fn add_connection_to_nodes(
    nodes_dict: &mut serde_json::Map<String, Value>,
    conn: &Connection,
    ref_id_counter: &mut u32,
) {
    let to_id = conn.to_node.to_string();

    if let Some(Value::Object(target_node)) = nodes_dict.get_mut(&to_id) {
        if let Some(Value::Object(ports)) = target_node.get_mut("Ports") {
            if let Some(Value::Array(port_values)) = ports.get_mut("$values") {
                for port in port_values.iter_mut() {
                    if let Value::Object(port_obj) = port {
                        if port_obj.get("Name") == Some(&json!(conn.to_port)) {
                            // Update port type to Required if input
                            if let Some(Value::String(port_type)) = port_obj.get("Type") {
                                if port_type.contains("In") && !port_type.contains("Required") {
                                    port_obj.insert(
                                        "Type".to_string(),
                                        json!(format!("{}, Required", port_type)),
                                    );
                                }
                            }

                            // Add connection record
                            port_obj.insert(
                                "Record".to_string(),
                                json!({
                                    "$id": ref_id_counter.to_string(),
                                    "From": conn.from_node,
                                    "To": conn.to_node,
                                    "FromPort": conn.from_port,
                                    "ToPort": conn.to_port,
                                    "IsValid": true
                                }),
                            );
                            *ref_id_counter += 1;
                            break;
                        }
                    }
                }
            }
        }
    }
}

/// Parse nodes from JSON input.
pub fn parse_nodes(nodes_json: &[Value]) -> Result<Vec<Node>, String> {
    let mut nodes = Vec::new();

    for (i, node_val) in nodes_json.iter().enumerate() {
        let obj = node_val
            .as_object()
            .ok_or_else(|| format!("Node {} is not an object", i))?;

        let id = obj
            .get("id")
            .and_then(|v| v.as_i64())
            .unwrap_or((100 + i) as i64) as i32;

        let node_type = obj
            .get("type")
            .and_then(|v| v.as_str())
            .unwrap_or("Mountain")
            .to_string();

        let name = obj
            .get("name")
            .and_then(|v| v.as_str())
            .unwrap_or(&node_type)
            .to_string();

        let position = if let Some(pos) = obj.get("position") {
            Position {
                x: pos
                    .get("x")
                    .or_else(|| pos.get("X"))
                    .and_then(|v| v.as_f64())
                    .unwrap_or(25000.0),
                y: pos
                    .get("y")
                    .or_else(|| pos.get("Y"))
                    .and_then(|v| v.as_f64())
                    .unwrap_or(25000.0),
            }
        } else {
            Position::default()
        };

        let properties = obj
            .get("properties")
            .and_then(|v| v.as_object())
            .map(|m| m.clone().into_iter().collect())
            .unwrap_or_default();

        nodes.push(Node {
            id,
            node_type,
            name,
            position,
            properties,
            ports: None,
            modifiers: None,
            save_definition: None,
        });
    }

    Ok(nodes)
}

/// Parse connections from JSON input.
pub fn parse_connections(connections_json: &[Value]) -> Result<Vec<Connection>, String> {
    let mut connections = Vec::new();

    for conn_val in connections_json {
        if let Some(obj) = conn_val.as_object() {
            let from_node = obj
                .get("from_node")
                .or_else(|| obj.get("from"))
                .or_else(|| obj.get("source"))
                .and_then(|v| v.as_i64())
                .ok_or("Connection missing from_node")? as i32;

            let to_node = obj
                .get("to_node")
                .or_else(|| obj.get("to"))
                .or_else(|| obj.get("target"))
                .and_then(|v| v.as_i64())
                .ok_or("Connection missing to_node")? as i32;

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

            connections.push(Connection {
                from_node,
                to_node,
                from_port,
                to_port,
            });
        } else if let Some(arr) = conn_val.as_array() {
            // Handle [from, to] format
            if arr.len() >= 2 {
                connections.push(Connection {
                    from_node: arr[0].as_i64().unwrap_or(0) as i32,
                    to_node: arr[1].as_i64().unwrap_or(0) as i32,
                    from_port: "Out".to_string(),
                    to_port: "In".to_string(),
                });
            }
        }
    }

    Ok(connections)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_generate_project() {
        let workflow = Workflow {
            nodes: vec![
                Node {
                    id: 100,
                    node_type: "Mountain".to_string(),
                    name: "Mountain".to_string(),
                    position: Position {
                        x: 25000.0,
                        y: 25000.0,
                    },
                    properties: HashMap::new(),
                    ports: None,
                    modifiers: None,
                    save_definition: None,
                },
                Node {
                    id: 101,
                    node_type: "Output".to_string(),
                    name: "Output".to_string(),
                    position: Position {
                        x: 25300.0,
                        y: 25000.0,
                    },
                    properties: HashMap::new(),
                    ports: None,
                    modifiers: None,
                    save_definition: None,
                },
            ],
            connections: vec![Connection {
                from_node: 100,
                to_node: 101,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            }],
        };

        let result = generate_project("test_project", &workflow, None, None).await;
        assert!(result.is_ok());
    }

    #[test]
    fn test_parse_nodes() {
        let nodes_json = vec![
            json!({"id": 1, "type": "Mountain", "name": "Mountain"}),
            json!({"id": 2, "type": "Output", "name": "Output"}),
        ];

        let nodes = parse_nodes(&nodes_json).unwrap();
        assert_eq!(nodes.len(), 2);
        assert_eq!(nodes[0].node_type, "Mountain");
    }

    #[test]
    fn test_parse_connections() {
        let conns_json = vec![json!({"from_node": 1, "to_node": 2}), json!([1, 3])];

        let connections = parse_connections(&conns_json).unwrap();
        assert_eq!(connections.len(), 2);
        assert_eq!(connections[0].from_node, 1);
        assert_eq!(connections[0].to_node, 2);
    }
}
