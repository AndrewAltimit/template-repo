//! Pre-built templates for Gaea2 terrain generation.
//!
//! Provides 11 professional-quality templates matching the Python implementation.

use std::collections::HashMap;

use serde_json::json;

use crate::types::{Connection, Node, Position, SaveDefinition, Template};

/// Get a template by name.
pub fn get_template(name: &str) -> Option<Template> {
    match name {
        "basic_terrain" => Some(basic_terrain_template()),
        "detailed_mountain" => Some(detailed_mountain_template()),
        "volcanic_terrain" => Some(volcanic_terrain_template()),
        "desert_canyon" => Some(desert_canyon_template()),
        "mountain_range" => Some(mountain_range_template()),
        "volcanic_island" => Some(volcanic_island_template()),
        "canyon_system" => Some(canyon_system_template()),
        "coastal_cliffs" => Some(coastal_cliffs_template()),
        "river_valley" => Some(river_valley_template()),
        "arctic_terrain" => Some(arctic_terrain_template()),
        "modular_portal_terrain" => Some(modular_portal_terrain_template()),
        _ => None,
    }
}

/// List all available templates with descriptions.
pub fn list_templates() -> Vec<(String, String)> {
    vec![
        (
            "basic_terrain".to_string(),
            "Simple terrain with erosion and basic texturing".to_string(),
        ),
        (
            "detailed_mountain".to_string(),
            "Multi-peak mountain with rivers, snow, and detailed erosion".to_string(),
        ),
        (
            "volcanic_terrain".to_string(),
            "Volcanic island with lava erosion and thermal weathering".to_string(),
        ),
        (
            "desert_canyon".to_string(),
            "Layered canyon with terraces and sand accumulation".to_string(),
        ),
        (
            "mountain_range".to_string(),
            "Extended mountain range with ridge detail and snow".to_string(),
        ),
        (
            "volcanic_island".to_string(),
            "Island with central volcano, lava flows, and beaches".to_string(),
        ),
        (
            "canyon_system".to_string(),
            "Complex canyon system with rock layers and sediments".to_string(),
        ),
        (
            "coastal_cliffs".to_string(),
            "Coastal terrain with sea level, cliffs, and beaches".to_string(),
        ),
        (
            "river_valley".to_string(),
            "River valley with floodplains and sediment deposits".to_string(),
        ),
        (
            "arctic_terrain".to_string(),
            "Arctic terrain with glaciers, snow, and ice formations".to_string(),
        ),
        (
            "modular_portal_terrain".to_string(),
            "Advanced modular workflow using portals for node reuse".to_string(),
        ),
    ]
}

/// Basic terrain template with erosion and texturing.
fn basic_terrain_template() -> Template {
    let mut props1 = HashMap::new();
    props1.insert("Scale".to_string(), json!(1.0));
    props1.insert("Height".to_string(), json!(0.7));
    props1.insert("Style".to_string(), json!("Alpine"));

    let mut props2 = HashMap::new();
    props2.insert("Duration".to_string(), json!(0.15));
    props2.insert("Downcutting".to_string(), json!(0.3));
    props2.insert("ErosionScale".to_string(), json!(5000.0));
    props2.insert("Seed".to_string(), json!(12345));

    let mut props5 = HashMap::new();
    props5.insert("Library".to_string(), json!("Rock"));
    props5.insert("LibraryItem".to_string(), json!(0));

    Template {
        name: "basic_terrain".to_string(),
        description: "Simple terrain with erosion and basic texturing".to_string(),
        nodes: vec![
            Node {
                id: 100,
                node_type: "Mountain".to_string(),
                name: "BaseTerrain".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25000.0,
                },
                properties: props1,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 101,
                node_type: "Erosion2".to_string(),
                name: "NaturalErosion".to_string(),
                position: Position {
                    x: 25300.0,
                    y: 25000.0,
                },
                properties: props2,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 102,
                node_type: "Export".to_string(),
                name: "HeightmapExport".to_string(),
                position: Position {
                    x: 25600.0,
                    y: 25000.0,
                },
                properties: HashMap::new(),
                ports: None,
                modifiers: None,
                save_definition: Some(SaveDefinition {
                    filename: "heightmap".to_string(),
                    format: "PNG16".to_string(),
                    enabled: true,
                    disabled_profiles: vec![],
                }),
            },
            Node {
                id: 103,
                node_type: "TextureBase".to_string(),
                name: "BaseTexture".to_string(),
                position: Position {
                    x: 25300.0,
                    y: 25300.0,
                },
                properties: HashMap::new(),
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 104,
                node_type: "SatMap".to_string(),
                name: "ColorMap".to_string(),
                position: Position {
                    x: 25600.0,
                    y: 25300.0,
                },
                properties: props5,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
        ],
        connections: vec![
            Connection {
                from_node: 100,
                to_node: 101,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 101,
                to_node: 102,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 101,
                to_node: 103,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 103,
                to_node: 104,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
        ],
    }
}

/// Detailed mountain template with rivers and snow.
fn detailed_mountain_template() -> Template {
    let mut props1 = HashMap::new();
    props1.insert("Scale".to_string(), json!(1.5));
    props1.insert("Height".to_string(), json!(0.85));
    props1.insert("Style".to_string(), json!("Alpine"));
    props1.insert("Bulk".to_string(), json!("High"));

    let mut props2 = HashMap::new();
    props2.insert("Scale".to_string(), json!(0.8));
    props2.insert("Height".to_string(), json!(0.6));
    props2.insert("Style".to_string(), json!("Eroded"));

    let mut props3 = HashMap::new();
    props3.insert("Mode".to_string(), json!("Max"));
    props3.insert("Ratio".to_string(), json!(0.7));

    let mut props4 = HashMap::new();
    props4.insert("Duration".to_string(), json!(0.15));
    props4.insert("Downcutting".to_string(), json!(0.35));
    props4.insert("ErosionScale".to_string(), json!(6000.0));
    props4.insert("Seed".to_string(), json!(23456));

    let mut props5 = HashMap::new();
    props5.insert("Water".to_string(), json!(0.3));
    props5.insert("Width".to_string(), json!(0.5));
    props5.insert("Depth".to_string(), json!(0.4));

    let mut props7 = HashMap::new();
    props7.insert("Duration".to_string(), json!(0.6));
    props7.insert("SnowLine".to_string(), json!(0.75));

    let mut props8 = HashMap::new();
    props8.insert("Library".to_string(), json!("Rock"));
    props8.insert("Enhance".to_string(), json!("Autolevel"));

    Template {
        name: "detailed_mountain".to_string(),
        description: "Multi-peak mountain with rivers, snow, and detailed erosion".to_string(),
        nodes: vec![
            Node {
                id: 100,
                node_type: "Mountain".to_string(),
                name: "PrimaryMountain".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25000.0,
                },
                properties: props1,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 101,
                node_type: "Mountain".to_string(),
                name: "SecondaryPeaks".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25300.0,
                },
                properties: props2,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 102,
                node_type: "Combine".to_string(),
                name: "MergePeaks".to_string(),
                position: Position {
                    x: 25300.0,
                    y: 25150.0,
                },
                properties: props3,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 103,
                node_type: "Erosion2".to_string(),
                name: "InitialErosion".to_string(),
                position: Position {
                    x: 25600.0,
                    y: 25150.0,
                },
                properties: props4,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 104,
                node_type: "Rivers".to_string(),
                name: "MountainStreams".to_string(),
                position: Position {
                    x: 25900.0,
                    y: 25150.0,
                },
                properties: props5,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 105,
                node_type: "Export".to_string(),
                name: "MountainHeightmap".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25000.0,
                },
                properties: HashMap::new(),
                ports: None,
                modifiers: None,
                save_definition: Some(SaveDefinition {
                    filename: "mountain_heightmap".to_string(),
                    format: "PNG16".to_string(),
                    enabled: true,
                    disabled_profiles: vec![],
                }),
            },
            Node {
                id: 106,
                node_type: "Snow".to_string(),
                name: "SnowCaps".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25300.0,
                },
                properties: props7,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 107,
                node_type: "SatMap".to_string(),
                name: "RealisticColors".to_string(),
                position: Position {
                    x: 26500.0,
                    y: 25300.0,
                },
                properties: props8,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
        ],
        connections: vec![
            Connection {
                from_node: 100,
                to_node: 102,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 101,
                to_node: 102,
                from_port: "Out".to_string(),
                to_port: "Input2".to_string(),
            },
            Connection {
                from_node: 102,
                to_node: 103,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 103,
                to_node: 104,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 104,
                to_node: 105,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 104,
                to_node: 106,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 106,
                to_node: 107,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
        ],
    }
}

/// Volcanic terrain template.
fn volcanic_terrain_template() -> Template {
    let mut props1 = HashMap::new();
    props1.insert("Scale".to_string(), json!(1.2));
    props1.insert("Height".to_string(), json!(0.8));
    props1.insert("Mouth".to_string(), json!(0.3));

    let mut props2 = HashMap::new();
    props2.insert("Size".to_string(), json!(0.5));
    props2.insert("Chaos".to_string(), json!(0.3));

    let mut props3 = HashMap::new();
    props3.insert("Mode".to_string(), json!("Add"));
    props3.insert("Ratio".to_string(), json!(0.8));

    let mut props4 = HashMap::new();
    props4.insert("Duration".to_string(), json!(0.15));
    props4.insert("Downcutting".to_string(), json!(0.4));
    props4.insert("Seed".to_string(), json!(34567));

    let mut props5 = HashMap::new();
    props5.insert("Strength".to_string(), json!(0.5));
    props5.insert("Angle".to_string(), json!(35.0));

    let mut props7 = HashMap::new();
    props7.insert("Library".to_string(), json!("Rock"));
    props7.insert("LibraryItem".to_string(), json!(1));

    Template {
        name: "volcanic_terrain".to_string(),
        description: "Volcanic island with lava erosion and thermal weathering".to_string(),
        nodes: vec![
            Node {
                id: 100,
                node_type: "Volcano".to_string(),
                name: "MainVolcano".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25000.0,
                },
                properties: props1,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 101,
                node_type: "Island".to_string(),
                name: "VolcanicIsland".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25300.0,
                },
                properties: props2,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 102,
                node_type: "Combine".to_string(),
                name: "MergeVolcano".to_string(),
                position: Position {
                    x: 25300.0,
                    y: 25150.0,
                },
                properties: props3,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 103,
                node_type: "Erosion2".to_string(),
                name: "LavaErosion".to_string(),
                position: Position {
                    x: 25600.0,
                    y: 25150.0,
                },
                properties: props4,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 104,
                node_type: "Thermal".to_string(),
                name: "ThermalWeathering".to_string(),
                position: Position {
                    x: 25900.0,
                    y: 25150.0,
                },
                properties: props5,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 105,
                node_type: "Export".to_string(),
                name: "VolcanoHeightmap".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25000.0,
                },
                properties: HashMap::new(),
                ports: None,
                modifiers: None,
                save_definition: Some(SaveDefinition {
                    filename: "volcano_heightmap".to_string(),
                    format: "PNG16".to_string(),
                    enabled: true,
                    disabled_profiles: vec![],
                }),
            },
            Node {
                id: 106,
                node_type: "SatMap".to_string(),
                name: "VolcanicColors".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25300.0,
                },
                properties: props7,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
        ],
        connections: vec![
            Connection {
                from_node: 100,
                to_node: 102,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 101,
                to_node: 102,
                from_port: "Out".to_string(),
                to_port: "Input2".to_string(),
            },
            Connection {
                from_node: 102,
                to_node: 103,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 103,
                to_node: 104,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 104,
                to_node: 105,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 104,
                to_node: 106,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
        ],
    }
}

/// Desert canyon template.
fn desert_canyon_template() -> Template {
    let mut props1 = HashMap::new();
    props1.insert("Scale".to_string(), json!(1.5));
    props1.insert("Depth".to_string(), json!(0.7));

    let mut props2 = HashMap::new();
    props2.insert("Layers".to_string(), json!(12));
    props2.insert("Strength".to_string(), json!(0.6));

    let mut props3 = HashMap::new();
    props3.insert("Intensity".to_string(), json!(0.5));
    props3.insert("Spacing".to_string(), json!(0.2));
    props3.insert("Seed".to_string(), json!(54321));

    let mut props4 = HashMap::new();
    props4.insert("Duration".to_string(), json!(0.10));
    props4.insert("Downcutting".to_string(), json!(0.2));
    props4.insert("Seed".to_string(), json!(45678));

    let mut props5 = HashMap::new();
    props5.insert("Amount".to_string(), json!(0.4));

    let mut props7 = HashMap::new();
    props7.insert("Library".to_string(), json!("Sand"));

    Template {
        name: "desert_canyon".to_string(),
        description: "Layered canyon with terraces and sand accumulation".to_string(),
        nodes: vec![
            Node {
                id: 100,
                node_type: "Canyon".to_string(),
                name: "MainCanyon".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25000.0,
                },
                properties: props1,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 101,
                node_type: "Stratify".to_string(),
                name: "RockLayers".to_string(),
                position: Position {
                    x: 25300.0,
                    y: 25000.0,
                },
                properties: props2,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 102,
                node_type: "FractalTerraces".to_string(),
                name: "TerraceFormation".to_string(),
                position: Position {
                    x: 25600.0,
                    y: 25000.0,
                },
                properties: props3,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 103,
                node_type: "Erosion2".to_string(),
                name: "WindErosion".to_string(),
                position: Position {
                    x: 25900.0,
                    y: 25000.0,
                },
                properties: props4,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 104,
                node_type: "Sand".to_string(),
                name: "SandAccumulation".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25000.0,
                },
                properties: props5,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 105,
                node_type: "Export".to_string(),
                name: "CanyonHeightmap".to_string(),
                position: Position {
                    x: 26500.0,
                    y: 25000.0,
                },
                properties: HashMap::new(),
                ports: None,
                modifiers: None,
                save_definition: Some(SaveDefinition {
                    filename: "canyon_heightmap".to_string(),
                    format: "PNG16".to_string(),
                    enabled: true,
                    disabled_profiles: vec![],
                }),
            },
            Node {
                id: 106,
                node_type: "SatMap".to_string(),
                name: "DesertColors".to_string(),
                position: Position {
                    x: 26500.0,
                    y: 25300.0,
                },
                properties: props7,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
        ],
        connections: vec![
            Connection {
                from_node: 100,
                to_node: 101,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 101,
                to_node: 102,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 102,
                to_node: 103,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 103,
                to_node: 104,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 104,
                to_node: 105,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 104,
                to_node: 106,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
        ],
    }
}

/// Mountain range template.
fn mountain_range_template() -> Template {
    let mut props1 = HashMap::new();
    props1.insert("Scale".to_string(), json!(2.0));
    props1.insert("Height".to_string(), json!(0.9));
    props1.insert("Style".to_string(), json!("Alpine"));
    props1.insert("Bulk".to_string(), json!("High"));

    let mut props2 = HashMap::new();
    props2.insert("Scale".to_string(), json!(0.5));

    let mut props3 = HashMap::new();
    props3.insert("Mode".to_string(), json!("Add"));
    props3.insert("Ratio".to_string(), json!(0.3));

    let mut props4 = HashMap::new();
    props4.insert("Duration".to_string(), json!(0.15));
    props4.insert("Downcutting".to_string(), json!(0.3));
    props4.insert("Seed".to_string(), json!(54321));

    let mut props6 = HashMap::new();
    props6.insert("Duration".to_string(), json!(0.7));
    props6.insert("SnowLine".to_string(), json!(0.7));

    let mut props7 = HashMap::new();
    props7.insert("Library".to_string(), json!("Rock"));
    props7.insert("Enhance".to_string(), json!("Autolevel"));

    Template {
        name: "mountain_range".to_string(),
        description: "Extended mountain range with ridge detail and snow".to_string(),
        nodes: vec![
            Node {
                id: 100,
                node_type: "Mountain".to_string(),
                name: "MainRange".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25000.0,
                },
                properties: props1,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 101,
                node_type: "Ridge".to_string(),
                name: "RidgeDetail".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25300.0,
                },
                properties: props2,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 102,
                node_type: "Combine".to_string(),
                name: "MergeRidge".to_string(),
                position: Position {
                    x: 25300.0,
                    y: 25150.0,
                },
                properties: props3,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 103,
                node_type: "Erosion2".to_string(),
                name: "AdvancedErosion".to_string(),
                position: Position {
                    x: 25600.0,
                    y: 25150.0,
                },
                properties: props4,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 104,
                node_type: "Export".to_string(),
                name: "RangeHeightmap".to_string(),
                position: Position {
                    x: 25900.0,
                    y: 25000.0,
                },
                properties: HashMap::new(),
                ports: None,
                modifiers: None,
                save_definition: Some(SaveDefinition {
                    filename: "range_heightmap".to_string(),
                    format: "PNG16".to_string(),
                    enabled: true,
                    disabled_profiles: vec![],
                }),
            },
            Node {
                id: 105,
                node_type: "Snow".to_string(),
                name: "SnowLine".to_string(),
                position: Position {
                    x: 25900.0,
                    y: 25300.0,
                },
                properties: props6,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 106,
                node_type: "SatMap".to_string(),
                name: "MountainColors".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25300.0,
                },
                properties: props7,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
        ],
        connections: vec![
            Connection {
                from_node: 100,
                to_node: 102,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 101,
                to_node: 102,
                from_port: "Out".to_string(),
                to_port: "Input2".to_string(),
            },
            Connection {
                from_node: 102,
                to_node: 103,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 103,
                to_node: 104,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 103,
                to_node: 105,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 105,
                to_node: 106,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
        ],
    }
}

/// Volcanic island template.
fn volcanic_island_template() -> Template {
    let mut props1 = HashMap::new();
    props1.insert("Size".to_string(), json!(0.8));
    props1.insert("Height".to_string(), json!(0.5));

    let mut props2 = HashMap::new();
    props2.insert("Scale".to_string(), json!(0.6));
    props2.insert("Height".to_string(), json!(1.0));
    props2.insert("Mouth".to_string(), json!(0.35));

    let mut props3 = HashMap::new();
    props3.insert("Mode".to_string(), json!("Max"));
    props3.insert("Ratio".to_string(), json!(0.9));

    let mut props4 = HashMap::new();
    props4.insert("Intensity".to_string(), json!(0.7));

    let mut props5 = HashMap::new();
    props5.insert("Duration".to_string(), json!(0.12));
    props5.insert("Downcutting".to_string(), json!(0.3));

    let mut props7 = HashMap::new();
    props7.insert("Library".to_string(), json!("Rock"));

    Template {
        name: "volcanic_island".to_string(),
        description: "Island with central volcano".to_string(),
        nodes: vec![
            Node {
                id: 100,
                node_type: "Island".to_string(),
                name: "BaseIsland".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25000.0,
                },
                properties: props1,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 101,
                node_type: "Volcano".to_string(),
                name: "CentralVolcano".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25300.0,
                },
                properties: props2,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 102,
                node_type: "Combine".to_string(),
                name: "MergeVolcano".to_string(),
                position: Position {
                    x: 25300.0,
                    y: 25150.0,
                },
                properties: props3,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 103,
                node_type: "Thermal".to_string(),
                name: "ThermalBreakdown".to_string(),
                position: Position {
                    x: 25600.0,
                    y: 25150.0,
                },
                properties: props4,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 104,
                node_type: "Erosion2".to_string(),
                name: "IslandErosion".to_string(),
                position: Position {
                    x: 25900.0,
                    y: 25150.0,
                },
                properties: props5,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 105,
                node_type: "Export".to_string(),
                name: "IslandHeightmap".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25000.0,
                },
                properties: HashMap::new(),
                ports: None,
                modifiers: None,
                save_definition: Some(SaveDefinition {
                    filename: "island_heightmap".to_string(),
                    format: "PNG16".to_string(),
                    enabled: true,
                    disabled_profiles: vec![],
                }),
            },
            Node {
                id: 106,
                node_type: "SatMap".to_string(),
                name: "VolcanicColors".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25300.0,
                },
                properties: props7,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
        ],
        connections: vec![
            Connection {
                from_node: 100,
                to_node: 102,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 101,
                to_node: 102,
                from_port: "Out".to_string(),
                to_port: "Input2".to_string(),
            },
            Connection {
                from_node: 102,
                to_node: 103,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 103,
                to_node: 104,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 104,
                to_node: 105,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 104,
                to_node: 106,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
        ],
    }
}

/// Canyon system template.
fn canyon_system_template() -> Template {
    let mut props1 = HashMap::new();
    props1.insert("Scale".to_string(), json!(0.8));
    props1.insert("Jitter".to_string(), json!(0.7));

    let mut props2 = HashMap::new();
    props2.insert("Layers".to_string(), json!(12));
    props2.insert("Strength".to_string(), json!(0.5));

    let mut props3 = HashMap::new();
    props3.insert("Duration".to_string(), json!(0.15));
    props3.insert("Downcutting".to_string(), json!(0.5));
    props3.insert("Seed".to_string(), json!(98765));

    let mut props4 = HashMap::new();
    props4.insert("Strength".to_string(), json!(0.3));
    props4.insert("Iterations".to_string(), json!(20));

    let mut props5 = HashMap::new();
    props5.insert("Deposition".to_string(), json!(0.4));

    let mut props7 = HashMap::new();
    props7.insert("Library".to_string(), json!("Sand"));

    Template {
        name: "canyon_system".to_string(),
        description: "Complex canyon system with rock layers".to_string(),
        nodes: vec![
            Node {
                id: 100,
                node_type: "Voronoi".to_string(),
                name: "CanyonPattern".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25000.0,
                },
                properties: props1,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 101,
                node_type: "Stratify".to_string(),
                name: "RockLayers".to_string(),
                position: Position {
                    x: 25300.0,
                    y: 25000.0,
                },
                properties: props2,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 102,
                node_type: "Erosion2".to_string(),
                name: "RiverErosion".to_string(),
                position: Position {
                    x: 25600.0,
                    y: 25000.0,
                },
                properties: props3,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 103,
                node_type: "Thermal".to_string(),
                name: "RockfallErosion".to_string(),
                position: Position {
                    x: 25900.0,
                    y: 25000.0,
                },
                properties: props4,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 104,
                node_type: "Sediment".to_string(),
                name: "ValleyFill".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25000.0,
                },
                properties: props5,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 105,
                node_type: "Export".to_string(),
                name: "CanyonSystemHeightmap".to_string(),
                position: Position {
                    x: 26500.0,
                    y: 25000.0,
                },
                properties: HashMap::new(),
                ports: None,
                modifiers: None,
                save_definition: Some(SaveDefinition {
                    filename: "canyon_system_heightmap".to_string(),
                    format: "PNG16".to_string(),
                    enabled: true,
                    disabled_profiles: vec![],
                }),
            },
            Node {
                id: 106,
                node_type: "SatMap".to_string(),
                name: "CanyonColors".to_string(),
                position: Position {
                    x: 26500.0,
                    y: 25300.0,
                },
                properties: props7,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
        ],
        connections: vec![
            Connection {
                from_node: 100,
                to_node: 101,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 101,
                to_node: 102,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 102,
                to_node: 103,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 103,
                to_node: 104,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 104,
                to_node: 105,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 104,
                to_node: 106,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
        ],
    }
}

/// Coastal cliffs template.
fn coastal_cliffs_template() -> Template {
    let mut props1 = HashMap::new();
    props1.insert("Scale".to_string(), json!(1.0));
    props1.insert("Height".to_string(), json!(0.6));
    props1.insert("Style".to_string(), json!("Eroded"));

    let mut props2 = HashMap::new();
    props2.insert("Erosion".to_string(), json!(0.7));

    let mut props3 = HashMap::new();
    props3.insert("NumTerraces".to_string(), json!(5));
    props3.insert("Steepness".to_string(), json!(0.8));

    let mut props4 = HashMap::new();
    props4.insert("Duration".to_string(), json!(0.12));
    props4.insert("Downcutting".to_string(), json!(0.25));

    let mut props5 = HashMap::new();
    props5.insert("Level".to_string(), json!(0.2));

    let mut props7 = HashMap::new();
    props7.insert("Library".to_string(), json!("Rock"));

    Template {
        name: "coastal_cliffs".to_string(),
        description: "Coastal terrain with sea level and cliffs".to_string(),
        nodes: vec![
            Node {
                id: 100,
                node_type: "Mountain".to_string(),
                name: "CoastalTerrain".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25000.0,
                },
                properties: props1,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 101,
                node_type: "Coast".to_string(),
                name: "Coastline".to_string(),
                position: Position {
                    x: 25300.0,
                    y: 25000.0,
                },
                properties: props2,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 102,
                node_type: "Terraces".to_string(),
                name: "CliffTerraces".to_string(),
                position: Position {
                    x: 25600.0,
                    y: 25000.0,
                },
                properties: props3,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 103,
                node_type: "Erosion2".to_string(),
                name: "CoastalErosion".to_string(),
                position: Position {
                    x: 25900.0,
                    y: 25000.0,
                },
                properties: props4,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 104,
                node_type: "Sea".to_string(),
                name: "OceanLevel".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25000.0,
                },
                properties: props5,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 105,
                node_type: "Export".to_string(),
                name: "CoastalHeightmap".to_string(),
                position: Position {
                    x: 26500.0,
                    y: 25000.0,
                },
                properties: HashMap::new(),
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 106,
                node_type: "SatMap".to_string(),
                name: "CoastalColors".to_string(),
                position: Position {
                    x: 26500.0,
                    y: 25300.0,
                },
                properties: props7,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
        ],
        connections: vec![
            Connection {
                from_node: 100,
                to_node: 101,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 101,
                to_node: 102,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 102,
                to_node: 103,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 103,
                to_node: 104,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 104,
                to_node: 105,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 104,
                to_node: 106,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
        ],
    }
}

/// River valley template.
fn river_valley_template() -> Template {
    let mut props1 = HashMap::new();
    props1.insert("Scale".to_string(), json!(1.2));
    props1.insert("Height".to_string(), json!(0.5));

    let mut props2 = HashMap::new();
    props2.insert("Duration".to_string(), json!(0.12));
    props2.insert("Downcutting".to_string(), json!(0.3));

    let mut props3 = HashMap::new();
    props3.insert("Water".to_string(), json!(0.5));
    props3.insert("Width".to_string(), json!(0.6));
    props3.insert("Depth".to_string(), json!(0.5));

    let mut props4 = HashMap::new();
    props4.insert("Deposition".to_string(), json!(0.5));

    let mut props6 = HashMap::new();
    props6.insert("Library".to_string(), json!("Green"));

    Template {
        name: "river_valley".to_string(),
        description: "River valley with floodplains".to_string(),
        nodes: vec![
            Node {
                id: 100,
                node_type: "Mountain".to_string(),
                name: "ValleyTerrain".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25000.0,
                },
                properties: props1,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 101,
                node_type: "Erosion2".to_string(),
                name: "InitialErosion".to_string(),
                position: Position {
                    x: 25300.0,
                    y: 25000.0,
                },
                properties: props2,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 102,
                node_type: "Rivers".to_string(),
                name: "MainRiver".to_string(),
                position: Position {
                    x: 25600.0,
                    y: 25000.0,
                },
                properties: props3,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 103,
                node_type: "Sediment".to_string(),
                name: "Floodplain".to_string(),
                position: Position {
                    x: 25900.0,
                    y: 25000.0,
                },
                properties: props4,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 104,
                node_type: "Export".to_string(),
                name: "ValleyHeightmap".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25000.0,
                },
                properties: HashMap::new(),
                ports: None,
                modifiers: None,
                save_definition: Some(SaveDefinition {
                    filename: "valley_heightmap".to_string(),
                    format: "PNG16".to_string(),
                    enabled: true,
                    disabled_profiles: vec![],
                }),
            },
            Node {
                id: 105,
                node_type: "SatMap".to_string(),
                name: "ValleyColors".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25300.0,
                },
                properties: props6,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
        ],
        connections: vec![
            Connection {
                from_node: 100,
                to_node: 101,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 101,
                to_node: 102,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 102,
                to_node: 103,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 103,
                to_node: 104,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 103,
                to_node: 105,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
        ],
    }
}

/// Arctic terrain template.
fn arctic_terrain_template() -> Template {
    let mut props1 = HashMap::new();
    props1.insert("Scale".to_string(), json!(1.5));
    props1.insert("Height".to_string(), json!(0.7));
    props1.insert("Style".to_string(), json!("Alpine"));

    let mut props2 = HashMap::new();
    props2.insert("Duration".to_string(), json!(0.1));
    props2.insert("Downcutting".to_string(), json!(0.2));

    let mut props3 = HashMap::new();
    props3.insert("Duration".to_string(), json!(0.8));
    props3.insert("SnowLine".to_string(), json!(0.4));
    props3.insert("Intensity".to_string(), json!(0.9));

    let mut props4 = HashMap::new();
    props4.insert("Intensity".to_string(), json!(0.7));

    let mut props6 = HashMap::new();
    props6.insert("Library".to_string(), json!("Rock"));

    Template {
        name: "arctic_terrain".to_string(),
        description: "Arctic terrain with glaciers and snow".to_string(),
        nodes: vec![
            Node {
                id: 100,
                node_type: "Mountain".to_string(),
                name: "ArcticMountains".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25000.0,
                },
                properties: props1,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 101,
                node_type: "Erosion2".to_string(),
                name: "FrostErosion".to_string(),
                position: Position {
                    x: 25300.0,
                    y: 25000.0,
                },
                properties: props2,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 102,
                node_type: "Snow".to_string(),
                name: "SnowCover".to_string(),
                position: Position {
                    x: 25600.0,
                    y: 25000.0,
                },
                properties: props3,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 103,
                node_type: "Glacier".to_string(),
                name: "GlacierFormation".to_string(),
                position: Position {
                    x: 25900.0,
                    y: 25000.0,
                },
                properties: props4,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 104,
                node_type: "Export".to_string(),
                name: "ArcticHeightmap".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25000.0,
                },
                properties: HashMap::new(),
                ports: None,
                modifiers: None,
                save_definition: Some(SaveDefinition {
                    filename: "arctic_heightmap".to_string(),
                    format: "PNG16".to_string(),
                    enabled: true,
                    disabled_profiles: vec![],
                }),
            },
            Node {
                id: 105,
                node_type: "SatMap".to_string(),
                name: "ArcticColors".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25300.0,
                },
                properties: props6,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
        ],
        connections: vec![
            Connection {
                from_node: 100,
                to_node: 101,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 101,
                to_node: 102,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 102,
                to_node: 103,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 103,
                to_node: 104,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 103,
                to_node: 105,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
        ],
    }
}

/// Modular portal terrain template.
fn modular_portal_terrain_template() -> Template {
    let mut props1 = HashMap::new();
    props1.insert("Scale".to_string(), json!(1.2));
    props1.insert("Height".to_string(), json!(0.8));
    props1.insert("Style".to_string(), json!("Alpine"));

    let mut props2 = HashMap::new();
    props2.insert("PortalName".to_string(), json!("Primary_Shape"));

    let mut props3 = HashMap::new();
    props3.insert("PortalName".to_string(), json!("Primary_Shape"));

    let mut props4 = HashMap::new();
    props4.insert("Duration".to_string(), json!(0.20));
    props4.insert("Downcutting".to_string(), json!(0.4));
    props4.insert("Seed".to_string(), json!(56789));

    let mut props5 = HashMap::new();
    props5.insert("PortalName".to_string(), json!("Eroded_Terrain"));

    let mut props8 = HashMap::new();
    props8.insert("PortalName".to_string(), json!("Eroded_Terrain"));

    let mut props10 = HashMap::new();
    props10.insert("Library".to_string(), json!("Rock"));

    Template {
        name: "modular_portal_terrain".to_string(),
        description: "Advanced modular workflow using portals".to_string(),
        nodes: vec![
            Node {
                id: 100,
                node_type: "Mountain".to_string(),
                name: "PrimaryShape".to_string(),
                position: Position {
                    x: 25000.0,
                    y: 25000.0,
                },
                properties: props1,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 101,
                node_type: "PortalTransmit".to_string(),
                name: "ShapePortal".to_string(),
                position: Position {
                    x: 25300.0,
                    y: 25000.0,
                },
                properties: props2,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 102,
                node_type: "PortalReceive".to_string(),
                name: "ShapeForErosion".to_string(),
                position: Position {
                    x: 25600.0,
                    y: 25000.0,
                },
                properties: props3,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 103,
                node_type: "Erosion2".to_string(),
                name: "DetailedErosion".to_string(),
                position: Position {
                    x: 25900.0,
                    y: 25000.0,
                },
                properties: props4,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 104,
                node_type: "PortalTransmit".to_string(),
                name: "ErodedPortal".to_string(),
                position: Position {
                    x: 26200.0,
                    y: 25000.0,
                },
                properties: props5,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 107,
                node_type: "PortalReceive".to_string(),
                name: "FinalTerrain".to_string(),
                position: Position {
                    x: 26500.0,
                    y: 25000.0,
                },
                properties: props8,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
            Node {
                id: 108,
                node_type: "Export".to_string(),
                name: "PortalTerrainHeightmap".to_string(),
                position: Position {
                    x: 26800.0,
                    y: 25000.0,
                },
                properties: HashMap::new(),
                ports: None,
                modifiers: None,
                save_definition: Some(SaveDefinition {
                    filename: "portal_terrain_heightmap".to_string(),
                    format: "PNG16".to_string(),
                    enabled: true,
                    disabled_profiles: vec![],
                }),
            },
            Node {
                id: 109,
                node_type: "SatMap".to_string(),
                name: "TerrainColors".to_string(),
                position: Position {
                    x: 26800.0,
                    y: 25300.0,
                },
                properties: props10,
                ports: None,
                modifiers: None,
                save_definition: None,
            },
        ],
        connections: vec![
            Connection {
                from_node: 100,
                to_node: 101,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 102,
                to_node: 103,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 103,
                to_node: 104,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 107,
                to_node: 108,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
            Connection {
                from_node: 107,
                to_node: 109,
                from_port: "Out".to_string(),
                to_port: "In".to_string(),
            },
        ],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_template() {
        let template = get_template("basic_terrain").unwrap();
        assert_eq!(template.name, "basic_terrain");
        assert!(!template.nodes.is_empty());
    }

    #[test]
    fn test_list_templates() {
        let templates = list_templates();
        assert_eq!(templates.len(), 11);
    }

    #[test]
    fn test_template_structure() {
        for (name, _) in list_templates() {
            let template = get_template(&name).unwrap();
            assert!(!template.nodes.is_empty());
            assert!(!template.connections.is_empty());

            // Verify all connections reference valid nodes
            let node_ids: Vec<i32> = template.nodes.iter().map(|n| n.id).collect();
            for conn in &template.connections {
                assert!(
                    node_ids.contains(&conn.from_node),
                    "Template {} has invalid from_node {}",
                    name,
                    conn.from_node
                );
                assert!(
                    node_ids.contains(&conn.to_node),
                    "Template {} has invalid to_node {}",
                    name,
                    conn.to_node
                );
            }
        }
    }
}
