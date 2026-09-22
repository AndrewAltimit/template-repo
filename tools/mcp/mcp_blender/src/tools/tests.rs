//! Tool-level tests through the real `Tool::execute` boundary.
//!
//! The registry/validation tests need no Blender at all (they fail before a
//! process would be spawned). On Unix, an end-to-end suite drives the tools
//! against a fake `blender` shell script that speaks the same protocol as the
//! real scripts, exercising spawning, result parsing, timeouts, progress
//! polling and job cancellation without a Blender install.

use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};
use tempfile::TempDir;

use crate::config::Config;
use crate::server::BlenderServer;

fn server_with(base: &TempDir, extra: &[(&str, String)]) -> BlenderServer {
    let mut vars: HashMap<String, String> = HashMap::new();
    vars.insert(
        "MCP_BLENDER_BASE_DIR".into(),
        base.path().to_string_lossy().to_string(),
    );
    vars.insert(
        "BLENDER_PATH".into(),
        base.path().join("no-blender").to_string_lossy().to_string(),
    );
    for (k, v) in extra {
        vars.insert((*k).to_string(), v.clone());
    }
    BlenderServer::new(Config::from_vars(|k| vars.get(k).cloned(), false))
}

fn find(server: &BlenderServer, name: &str) -> BoxedTool {
    server
        .tools()
        .into_iter()
        .find(|t| t.name() == name)
        .unwrap_or_else(|| panic!("tool {name} missing"))
}

async fn call(server: &BlenderServer, name: &str, args: Value) -> Result<ToolResult> {
    find(server, name).execute(args).await
}

fn body(result: &ToolResult) -> Value {
    match &result.content[0] {
        Content::Text { text } => serde_json::from_str(text).expect("tool output is JSON"),
        other => panic!("unexpected content {other:?}"),
    }
}

fn invalid_message(result: Result<ToolResult>) -> String {
    match result {
        Err(MCPError::InvalidParameters(msg)) => msg,
        other => panic!("expected InvalidParameters, got {other:?}"),
    }
}

/// Tool names and required parameters of the previous release; these are
/// public API and must never change incompatibly.
const LEGACY_REQUIRED: &[(&str, &[&str])] = &[
    ("create_blender_project", &["name"]),
    ("list_projects", &[]),
    ("add_primitive_objects", &["project", "objects"]),
    ("setup_lighting", &["project", "type"]),
    ("apply_material", &["project", "object_name"]),
    ("render_image", &["project"]),
    ("render_animation", &["project"]),
    ("setup_physics", &["project", "object_name", "physics_type"]),
    ("bake_simulation", &["project"]),
    ("create_animation", &["project", "object_name", "keyframes"]),
    (
        "create_geometry_nodes",
        &["project", "object_name", "node_setup"],
    ),
    ("get_job_status", &["job_id"]),
    ("get_job_result", &["job_id"]),
    ("cancel_job", &["job_id"]),
    ("import_model", &["project", "model_path"]),
    ("export_scene", &["project", "format"]),
    ("setup_camera", &["project"]),
    ("add_camera_track", &["project", "target"]),
    ("add_modifier", &["project", "object_name", "modifier_type"]),
    ("add_particle_system", &["project", "object_name"]),
    ("add_smoke_simulation", &["project", "object_name"]),
    ("add_texture", &["project", "object_name", "texture_type"]),
    ("add_uv_map", &["project", "object_name"]),
    ("setup_compositor", &["project", "setup"]),
    ("batch_render", &["project"]),
    ("delete_objects", &["project"]),
    ("analyze_scene", &["project"]),
    ("optimize_scene", &["project", "optimization_type"]),
    ("create_curve", &["project", "name", "points"]),
    ("setup_world_environment", &["project", "environment_type"]),
    ("blender_status", &[]),
    ("quick_smoke", &["project", "object_names"]),
    ("quick_liquid", &["project", "object_names"]),
    ("quick_explode", &["project", "object_names"]),
    ("quick_fur", &["project", "object_names"]),
    (
        "add_constraint",
        &["project", "object_name", "constraint_type"],
    ),
    ("create_armature", &["project", "bones"]),
    ("create_text_object", &["project", "text"]),
    ("add_advanced_primitives", &["project", "objects"]),
    ("parent_objects", &["project", "parent_name", "children"]),
    ("join_objects", &["project", "object_names", "target_name"]),
];

#[test]
fn registry_is_backward_compatible() {
    let tmp = TempDir::new().unwrap();
    let server = server_with(&tmp, &[]);
    let tools = server.tools();
    let by_name: HashMap<&str, &BoxedTool> = tools.iter().map(|t| (t.name(), t)).collect();
    assert_eq!(by_name.len(), tools.len(), "duplicate tool names");
    assert_eq!(
        tools.len(),
        LEGACY_REQUIRED.len() + 1,
        "41 legacy tools + list_jobs"
    );
    assert!(by_name.contains_key("list_jobs"));

    for (name, required) in LEGACY_REQUIRED {
        let tool = by_name
            .get(name)
            .unwrap_or_else(|| panic!("legacy tool {name} missing"));
        let schema = tool.schema();
        let actual: HashSet<&str> = schema["required"]
            .as_array()
            .map(|a| a.iter().filter_map(Value::as_str).collect())
            .unwrap_or_default();
        let expected: HashSet<&str> = required.iter().copied().collect();
        assert_eq!(actual, expected, "required params of {name} changed");
    }
}

#[test]
fn schemas_are_well_formed() {
    let tmp = TempDir::new().unwrap();
    let server = server_with(&tmp, &[]);
    for tool in server.tools() {
        let schema = tool.schema();
        assert_eq!(schema["type"], "object", "{}", tool.name());
        let props = schema["properties"]
            .as_object()
            .unwrap_or_else(|| panic!("{} has no properties", tool.name()));
        if let Some(required) = schema["required"].as_array() {
            for field in required {
                let field = field.as_str().unwrap();
                assert!(
                    props.contains_key(field),
                    "{}: required '{field}' not in properties",
                    tool.name()
                );
            }
        }
        assert!(
            tool.description().len() >= 20,
            "{} description too short",
            tool.name()
        );
        assert!(
            tool.description().is_ascii(),
            "{} description must be ASCII",
            tool.name()
        );
    }
}

#[tokio::test]
async fn missing_and_mistyped_arguments_are_invalid_parameters() {
    let tmp = TempDir::new().unwrap();
    let server = server_with(&tmp, &[]);
    let msg = invalid_message(call(&server, "render_image", json!({})).await);
    assert!(msg.contains("project"), "{msg}");
    let msg = invalid_message(
        call(
            &server,
            "add_modifier",
            json!({"project": "p", "object_name": "o", "modifier_type": "EXPLODE"}),
        )
        .await,
    );
    assert!(msg.contains("SUBSURF"), "allowed values listed: {msg}");
    let msg = invalid_message(
        call(
            &server,
            "setup_camera",
            json!({"project": "p", "location": [1, 2]}),
        )
        .await,
    );
    assert!(msg.contains("length"), "{msg}");
    // Null arguments behave like an empty object.
    assert!(call(&server, "list_projects", Value::Null).await.is_ok());
}

#[tokio::test]
async fn project_references_are_confined() {
    let tmp = TempDir::new().unwrap();
    let server = server_with(&tmp, &[]);
    for bad in ["../escape", "/etc/passwd", ".hidden", "a/../../b"] {
        let msg = invalid_message(call(&server, "analyze_scene", json!({"project": bad})).await);
        assert!(!msg.is_empty());
    }
    let msg = invalid_message(call(&server, "analyze_scene", json!({"project": "missing"})).await);
    assert!(msg.contains("not found"), "{msg}");
}

#[tokio::test]
async fn project_names_are_validated_before_blender_runs() {
    let tmp = TempDir::new().unwrap();
    let server = server_with(&tmp, &[]);
    for bad in ["../x", "a/b", ".hidden", "semi;colon", ""] {
        let result = call(&server, "create_blender_project", json!({"name": bad})).await;
        assert!(
            matches!(result, Err(MCPError::InvalidParameters(_))),
            "{bad:?}"
        );
    }
    let msg = invalid_message(
        call(
            &server,
            "create_blender_project",
            json!({"name": "ok", "settings": {"resolution": [0, 10]}}),
        )
        .await,
    );
    assert!(msg.contains("resolution"), "{msg}");
}

fn make_project(tmp: &TempDir, name: &str) {
    let dir = tmp.path().join("projects");
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join(name), b"BLENDER-fake").unwrap();
}

#[tokio::test]
async fn existing_project_is_not_overwritten_without_flag() {
    let tmp = TempDir::new().unwrap();
    let server = server_with(&tmp, &[]);
    make_project(&tmp, "scene.blend");
    let msg =
        invalid_message(call(&server, "create_blender_project", json!({"name": "scene"})).await);
    assert!(msg.contains("overwrite"), "{msg}");
}

#[tokio::test]
async fn semantic_validation_happens_before_blender() {
    let tmp = TempDir::new().unwrap();
    let server = server_with(&tmp, &[]);
    make_project(&tmp, "p.blend");
    let cases = [
        (
            "render_animation",
            json!({"project": "p", "start_frame": 10, "end_frame": 5}),
            "end_frame",
        ),
        (
            "render_image",
            json!({"project": "p", "settings": {"samples": 0}}),
            "samples",
        ),
        (
            "setup_lighting",
            json!({"project": "p", "type": "hdri"}),
            "hdri_path",
        ),
        (
            "setup_lighting",
            json!({"project": "p", "type": "hdri", "settings": {"hdri_path": "../x.hdr"}}),
            "hdri_path",
        ),
        (
            "setup_world_environment",
            json!({"project": "p", "environment_type": "HDRI", "settings": {"hdri_path": "nope.hdr"}}),
            "not found",
        ),
        (
            "add_texture",
            json!({"project": "p", "object_name": "Cube", "texture_type": "IMAGE"}),
            "image_path",
        ),
        (
            "import_model",
            json!({"project": "p", "model_path": "missing.fbx"}),
            "not found",
        ),
        (
            "create_animation",
            json!({"project": "p", "object_name": "Cube", "keyframes": [{"frame": 1}]}),
            "location",
        ),
        (
            "create_curve",
            json!({"project": "p", "name": "c", "points": [[0, 0, 0]]}),
            "points",
        ),
        (
            "delete_objects",
            json!({"project": "p"}),
            "Nothing to delete",
        ),
        (
            "quick_fur",
            json!({"project": "p", "object_names": []}),
            "at least one",
        ),
        (
            "apply_material",
            json!({"project": "p", "object_name": "x".repeat(80)}),
            "63",
        ),
        (
            "apply_material",
            json!({"project": "p", "object_name": "Cube", "material": {"base_color": [1, 0]}}),
            "base_color",
        ),
        (
            "parent_objects",
            json!({"project": "p", "parent_name": "A", "children": ["B"], "parent_type": "BONE"}),
            "bone_name",
        ),
        (
            "add_constraint",
            json!({"project": "p", "object_name": "A", "constraint_type": "TRACK_TO"}),
            "target_object",
        ),
        (
            "batch_render",
            json!({"project": "p", "frames": []}),
            "frames",
        ),
        (
            "export_scene",
            json!({"project": "p", "format": "FBX", "filename": "../x"}),
            "invalid name",
        ),
        (
            "get_job_status",
            json!({"job_id": "not-a-uuid"}),
            "Invalid job_id",
        ),
        (
            "cancel_job",
            json!({"job_id": "00000000-0000-0000-0000-000000000000"}),
            "not found",
        ),
    ];
    for (tool, args, needle) in cases {
        let msg = invalid_message(call(&server, tool, args.clone()).await);
        assert!(
            msg.contains(needle),
            "{tool} {args}: '{msg}' should mention '{needle}'"
        );
    }
}

#[tokio::test]
async fn missing_blender_is_a_tool_error_not_a_crash() {
    let tmp = TempDir::new().unwrap();
    let server = server_with(&tmp, &[]);
    make_project(&tmp, "p.blend");
    let result = call(&server, "analyze_scene", json!({"project": "p"}))
        .await
        .unwrap();
    assert!(result.is_error);
    let body = body(&result);
    assert_eq!(body["success"], false);
    assert!(body["error"].as_str().unwrap().contains("BLENDER_PATH"));

    let status = body_of(call(&server, "blender_status", json!({})).await);
    assert_eq!(status["blender_available"], false);
    assert!(
        status["blender_error"]
            .as_str()
            .unwrap()
            .contains("BLENDER_PATH")
    );
}

fn body_of(result: Result<ToolResult>) -> Value {
    let result = result.expect("tool call succeeded");
    assert!(
        !result.is_error,
        "unexpected tool error: {:?}",
        result.content
    );
    body(&result)
}

#[tokio::test]
async fn list_projects_and_jobs_work_without_blender() {
    let tmp = TempDir::new().unwrap();
    let server = server_with(&tmp, &[]);
    make_project(&tmp, "b.blend");
    make_project(&tmp, "a.blend");
    let out = body_of(call(&server, "list_projects", json!({})).await);
    assert_eq!(out["projects"], json!(["a.blend", "b.blend"]));
    assert_eq!(out["count"], 2);
    let jobs = body_of(call(&server, "list_jobs", json!({"status": "running"})).await);
    assert_eq!(jobs["count"], 0);
}

#[tokio::test]
async fn failed_job_is_reported_by_status_and_result() {
    let tmp = TempDir::new().unwrap();
    let server = server_with(&tmp, &[]);
    make_project(&tmp, "p.blend");
    // No Blender: the job is accepted, then fails in the background.
    let started = body_of(call(&server, "render_image", json!({"project": "p"})).await);
    let job_id = started["job_id"].as_str().unwrap().to_string();
    assert!(
        started["output_path"]
            .as_str()
            .unwrap()
            .ends_with(&format!("{job_id}.png"))
    );
    let status = body_of(
        call(
            &server,
            "get_job_status",
            json!({"job_id": job_id, "wait_seconds": 10}),
        )
        .await,
    );
    assert_eq!(status["status"], "FAILED");
    assert!(status["error"].as_str().unwrap().contains("BLENDER_PATH"));
    let result = call(&server, "get_job_result", json!({"job_id": job_id}))
        .await
        .unwrap();
    assert!(result.is_error);
    let cancel = call(&server, "cancel_job", json!({"job_id": job_id}))
        .await
        .unwrap();
    assert!(cancel.is_error, "finished jobs cannot be cancelled");
}

#[cfg(unix)]
mod fake_blender {
    //! End-to-end tests against a fake `blender` executable.

    use super::*;
    use std::os::unix::fs::PermissionsExt;
    use std::time::Duration;

    const FAKE: &str = r#"#!/bin/sh
if [ "$1" = "--version" ]; then echo "Blender 4.5.1 (fake)"; exit 0; fi
while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do shift; done
shift
ARGS="$1"; ID="$2"
field() { sed -n "s/.*\"$1\":\"\([^\"]*\)\".*/\1/p" "$ARGS"; }
OP=$(field operation)
echo "Blender 4.5.1 (fake) running $OP"
if grep -q SLEEPME "$ARGS"; then exec sleep 30; fi
if grep -q FAILME "$ARGS"; then echo "Error: boom"; echo 'MCP_RESULT:{"success": false, "error": "Object FAILME not found"}'; exit 1; fi
if grep -q CRASHME "$ARGS"; then echo "Segmentation fault" >&2; exit 139; fi
case "$OP" in
  create_project)
    P=$(field project_path); echo fake > "$P"
    echo 'MCP_RESULT:{"success": true, "template": "basic_scene", "objects": ["Camera"]}'; exit 0;;
  render_image)
    OUT=$(field output_path)
    if grep -q '"frame":99' "$ARGS"; then
      echo $$ > "$BLENDER_MCP_JOBS_DIR/$ID.pid"
      printf '{"status":"RUNNING","progress":42,"message":"half way"}' > "$BLENDER_MCP_JOBS_DIR/$ID.status"
      exec sleep 30
    fi
    mkdir -p "$(dirname "$OUT")"; echo png > "$OUT"
    echo "MCP_RESULT:{\"success\": true, \"output_path\": \"$OUT\"}"; exit 0;;
esac
echo "MCP_RESULT:{\"success\": true, \"operation\": \"$OP\", \"id\": \"$ID\"}"
"#;

    fn fake_server(tmp: &TempDir, extra: &[(&str, String)]) -> BlenderServer {
        let exe = tmp.path().join("fake-blender");
        std::fs::write(&exe, FAKE).unwrap();
        std::fs::set_permissions(&exe, std::fs::Permissions::from_mode(0o755)).unwrap();
        let mut vars: Vec<(&str, String)> =
            vec![("BLENDER_PATH", exe.to_string_lossy().to_string())];
        vars.extend(extra.iter().cloned());
        server_with(tmp, &vars)
    }

    #[tokio::test]
    async fn create_edit_and_status_round_trip() {
        let tmp = TempDir::new().unwrap();
        let server = fake_server(&tmp, &[]);
        let created = body_of(
            call(
                &server,
                "create_blender_project",
                json!({"name": "demo", "template": "BASIC_SCENE"}),
            )
            .await,
        );
        assert_eq!(created["project_path"], "demo.blend");
        assert!(tmp.path().join("projects/demo.blend").is_file());

        let added = body_of(
            call(
                &server,
                "add_primitive_objects",
                json!({"project": "demo.blend", "objects": [{"type": "Cube", "name": "Box"}]}),
            )
            .await,
        );
        assert_eq!(added["objects_added"], 1);

        // Absolute path echoed back from create_blender_project is accepted too.
        let full = created["full_path"].as_str().unwrap();
        body_of(call(&server, "analyze_scene", json!({"project": full})).await);

        let status = body_of(call(&server, "blender_status", json!({})).await);
        assert_eq!(status["blender_available"], true);
        assert!(status["blender_version"].as_str().unwrap().contains("fake"));

        // Temp args files are cleaned up.
        let leftovers: Vec<_> = std::fs::read_dir(tmp.path().join("temp"))
            .unwrap()
            .collect();
        assert!(leftovers.is_empty(), "temp dir not cleaned: {leftovers:?}");
    }

    #[tokio::test]
    async fn script_failures_and_crashes_become_tool_errors() {
        let tmp = TempDir::new().unwrap();
        let server = fake_server(&tmp, &[]);
        make_project(&tmp, "p.blend");
        let failed = call(
            &server,
            "add_uv_map",
            json!({"project": "p", "object_name": "FAILME"}),
        )
        .await
        .unwrap();
        assert!(failed.is_error);
        let b = body(&failed);
        assert_eq!(b["error"], "Object FAILME not found");
        assert!(
            b["blender_log"]
                .as_array()
                .unwrap()
                .iter()
                .any(|l| l == "Error: boom")
        );

        let crashed = call(
            &server,
            "add_uv_map",
            json!({"project": "p", "object_name": "CRASHME"}),
        )
        .await
        .unwrap();
        assert!(crashed.is_error);
        let msg = body(&crashed)["error"].as_str().unwrap().to_string();
        assert!(msg.contains("139") && msg.contains("crash"), "{msg}");
    }

    #[tokio::test]
    async fn operations_time_out_and_kill_blender() {
        let tmp = TempDir::new().unwrap();
        let server = fake_server(&tmp, &[("BLENDER_JOB_TIMEOUT_SECS", "1".to_string())]);
        make_project(&tmp, "p.blend");
        let started = std::time::Instant::now();
        let result = call(
            &server,
            "add_uv_map",
            json!({"project": "p", "object_name": "SLEEPME"}),
        )
        .await
        .unwrap();
        assert!(result.is_error);
        assert!(
            body(&result)["error"]
                .as_str()
                .unwrap()
                .contains("did not finish within 1s")
        );
        assert!(started.elapsed() < Duration::from_secs(15));
    }

    #[tokio::test]
    async fn render_job_completes_with_output_path() {
        let tmp = TempDir::new().unwrap();
        let server = fake_server(&tmp, &[]);
        make_project(&tmp, "p.blend");
        let started = body_of(
            call(
                &server,
                "render_image",
                json!({"project": "p", "settings": {"format": "jpeg"}}),
            )
            .await,
        );
        let job_id = started["job_id"].as_str().unwrap().to_string();
        let expected = started["output_path"].as_str().unwrap().to_string();
        assert!(expected.ends_with(".jpg"));

        let status = body_of(
            call(
                &server,
                "get_job_status",
                json!({"job_id": job_id, "wait_seconds": 20}),
            )
            .await,
        );
        assert_eq!(status["status"], "COMPLETED", "{status}");
        let result = body_of(call(&server, "get_job_result", json!({"job_id": job_id})).await);
        assert_eq!(result["output_path"], expected);
        assert!(std::path::Path::new(&expected).is_file());
        let listed = body_of(call(&server, "list_jobs", json!({"status": "COMPLETED"})).await);
        assert_eq!(listed["count"], 1);
    }

    #[tokio::test]
    async fn running_job_reports_progress_and_cancel_kills_blender() {
        let tmp = TempDir::new().unwrap();
        let server = fake_server(&tmp, &[]);
        make_project(&tmp, "p.blend");
        let started = body_of(
            call(
                &server,
                "render_image",
                json!({"project": "p", "frame": 99}),
            )
            .await,
        );
        let job_id = started["job_id"].as_str().unwrap().to_string();

        // Wait for the status file to be picked up.
        let mut progressed = false;
        for _ in 0..40 {
            let status = body_of(call(&server, "get_job_status", json!({"job_id": job_id})).await);
            if status["status"] == "RUNNING" && status["progress"] == 42 {
                assert_eq!(status["message"], "half way");
                progressed = true;
                break;
            }
            tokio::time::sleep(Duration::from_millis(250)).await;
        }
        assert!(
            progressed,
            "progress from the status file was never reported"
        );

        let pid_file = tmp
            .path()
            .join("outputs/jobs")
            .join(format!("{job_id}.pid"));
        let pid = std::fs::read_to_string(&pid_file)
            .unwrap()
            .trim()
            .to_string();

        let cancelled = body_of(call(&server, "cancel_job", json!({"job_id": job_id})).await);
        assert_eq!(cancelled["status"], "CANCELLED");

        let mut dead = false;
        for _ in 0..40 {
            let alive = std::process::Command::new("kill")
                .args(["-0", &pid])
                .status()
                .map(|s| s.success())
                .unwrap_or(false);
            if !alive {
                dead = true;
                break;
            }
            tokio::time::sleep(Duration::from_millis(250)).await;
        }
        assert!(dead, "Blender process {pid} survived cancellation");
        let status = body_of(call(&server, "get_job_status", json!({"job_id": job_id})).await);
        assert_eq!(
            status["status"], "CANCELLED",
            "a killed job must stay cancelled"
        );
    }

    #[tokio::test]
    async fn queued_jobs_wait_for_a_slot_and_can_be_cancelled_while_queued() {
        let tmp = TempDir::new().unwrap();
        let server = fake_server(&tmp, &[("MAX_CONCURRENT_JOBS", "1".to_string())]);
        make_project(&tmp, "p.blend");
        let first = body_of(
            call(
                &server,
                "render_image",
                json!({"project": "p", "frame": 99}),
            )
            .await,
        );
        let second = body_of(call(&server, "render_image", json!({"project": "p"})).await);
        let second_id = second["job_id"].as_str().unwrap().to_string();
        tokio::time::sleep(Duration::from_millis(500)).await;
        let status = body_of(call(&server, "get_job_status", json!({"job_id": second_id})).await);
        assert_eq!(status["status"], "QUEUED");
        body_of(call(&server, "cancel_job", json!({"job_id": second_id})).await);
        body_of(call(&server, "cancel_job", json!({"job_id": first["job_id"]})).await);
        let status = body_of(call(&server, "get_job_status", json!({"job_id": second_id})).await);
        assert_eq!(status["status"], "CANCELLED");
    }
}
