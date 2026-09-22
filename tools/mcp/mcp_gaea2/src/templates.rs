//! Pre-built workflow templates for Gaea2 terrain generation.
//!
//! Templates live in `templates.json` (embedded at compile time) in exactly the
//! node/connection format that `create_gaea2_project` accepts, so they double
//! as worked examples. They are parsed once through the same input parser as
//! user workflows; the unit tests guarantee every template parses and passes
//! validation.

use std::sync::LazyLock;

use serde::Deserialize;
use serde_json::{Map, Value};

use crate::input::{parse_connections, parse_nodes};
use crate::types::Template;

const TEMPLATES_JSON: &str = include_str!("templates.json");

#[derive(Deserialize)]
struct RawTemplate {
    name: String,
    description: String,
    nodes: Vec<Value>,
    connections: Vec<Value>,
}

static TEMPLATES: LazyLock<Vec<Template>> = LazyLock::new(|| match load_templates() {
    Ok(t) => t,
    Err(e) => {
        tracing::error!("Embedded templates are invalid: {e}");
        Vec::new()
    },
});

fn load_templates() -> Result<Vec<Template>, String> {
    let raw: Vec<RawTemplate> =
        serde_json::from_str(TEMPLATES_JSON).map_err(|e| format!("templates.json: {e}"))?;
    raw.into_iter()
        .map(|t| {
            Ok(Template {
                nodes: parse_nodes(&t.nodes).map_err(|e| format!("{}: {e}", t.name))?,
                connections: parse_connections(&t.connections)
                    .map_err(|e| format!("{}: {e}", t.name))?,
                name: t.name,
                description: t.description,
            })
        })
        .collect()
}

/// Get a template by name.
pub fn get_template(name: &str) -> Option<Template> {
    TEMPLATES.iter().find(|t| t.name == name).cloned()
}

/// All templates.
pub fn all_templates() -> &'static [Template] {
    &TEMPLATES
}

/// Names of all templates.
pub fn template_names() -> Vec<&'static str> {
    TEMPLATES.iter().map(|t| t.name.as_str()).collect()
}

/// Apply property overrides to a template.
///
/// `modifications` maps a node *name* or *id* (as a string) to an object of
/// properties that are merged into that node's properties. A `null` value
/// removes the property. Returns the list of applied changes.
pub fn apply_modifications(
    template: &mut Template,
    modifications: &Map<String, Value>,
) -> Result<Vec<String>, String> {
    let mut applied = Vec::new();
    let available: Vec<String> = template
        .nodes
        .iter()
        .map(|n| format!("{} ({})", n.name, n.id))
        .collect();
    let template_name = template.name.clone();
    for (key, props) in modifications {
        let node = template
            .nodes
            .iter_mut()
            .find(|n| n.name == *key || n.id.to_string() == *key)
            .ok_or_else(|| {
                format!(
                    "modifications: no node named or with id '{key}' in template '{template_name}'. Nodes: {}",
                    available.join(", ")
                )
            })?;
        let props = props.as_object().ok_or_else(|| {
            format!("modifications['{key}'] must be an object of property overrides")
        })?;
        for (prop, value) in props {
            if value.is_null() {
                node.properties.shift_remove(prop);
                applied.push(format!("{}: removed {prop}", node.name));
            } else {
                node.properties.insert(prop.clone(), value.clone());
                applied.push(format!("{}: {prop} = {value}", node.name));
            }
        }
    }
    Ok(applied)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::generation::{build_project, ProjectOptions};
    use crate::types::{BuildConfig, Workflow};
    use crate::validation::{ValidateOptions, Validator};
    use serde_json::json;

    #[test]
    fn embedded_templates_parse() {
        let t = load_templates().expect("templates.json must parse");
        assert_eq!(t.len(), 11);
        assert_eq!(template_names().len(), 11);
    }

    #[test]
    fn test_get_template() {
        assert!(get_template("basic_terrain").is_some());
        assert!(get_template("volcanic_terrain").is_some());
        assert!(get_template("nonexistent").is_none());
    }

    #[test]
    fn every_template_validates_cleanly_and_generates() {
        for t in all_templates() {
            let wf = Workflow {
                nodes: t.nodes.clone(),
                connections: t.connections.clone(),
            };
            let r = Validator::validate_and_fix(
                &wf,
                ValidateOptions {
                    strict: false,
                    auto_fix: false,
                },
            );
            assert!(r.valid, "template {} invalid: {:?}", t.name, r.errors);
            assert!(!r.fixed);
            assert!(
                t.nodes
                    .iter()
                    .any(|n| n.node_type == "Export" && n.save_definition.is_some()),
                "template {} has no Export with a save definition",
                t.name
            );
            build_project(
                &t.name,
                &wf,
                &BuildConfig::default(),
                &ProjectOptions::default(),
            )
            .unwrap_or_else(|e| panic!("template {} failed to generate: {e}", t.name));
        }
    }

    #[test]
    fn modifications_apply_by_name_and_id() {
        let mut t = get_template("basic_terrain").unwrap();
        let mods = json!({
            "BaseTerrain": {"Height": 0.9, "Style": null},
            "101": {"Duration": 0.3}
        });
        let applied = apply_modifications(&mut t, mods.as_object().unwrap()).unwrap();
        assert_eq!(applied.len(), 3);
        assert_eq!(t.nodes[0].properties["Height"], json!(0.9));
        assert!(!t.nodes[0].properties.contains_key("Style"));
        assert_eq!(t.nodes[1].properties["Duration"], json!(0.3));

        let bad = json!({"Nope": {"A": 1}});
        assert!(apply_modifications(&mut t, bad.as_object().unwrap()).is_err());
        let bad = json!({"BaseTerrain": 5});
        assert!(apply_modifications(&mut t, bad.as_object().unwrap()).is_err());
    }
}
