//! End-to-end tool tests against an in-process mock of the ComfyUI HTTP API.
//!
//! The real ComfyUI runs on a remote GPU host; these tests never touch the
//! network beyond a loopback listener, so they run offline.

use std::sync::{Arc, Mutex};
use std::time::Duration;

use axum::{
    Json, Router,
    body::Bytes,
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode, header},
    response::{IntoResponse, Response},
    routing::{get, post},
};
use mcp_core::prelude::*;
use serde_json::{Value, json};

use crate::config::Config;
use crate::server::ComfyUIServer;

const PNG: &[u8] = b"\x89PNG\r\n\x1a\nfake-png-body";

#[derive(Default)]
struct Mock {
    prompts: Vec<Value>,
    deleted: Vec<Value>,
    interrupted: Vec<Value>,
    uploads: Vec<(String, usize)>,
    /// Number of /history polls answered with "not yet" before completing.
    pending_polls: usize,
}

type Shared = Arc<Mutex<Mock>>;

async fn post_prompt(State(m): State<Shared>, Json(body): Json<Value>) -> Response {
    let workflow = body["prompt"].clone();
    let bad = workflow
        .as_object()
        .is_some_and(|o| o.values().any(|n| n["class_type"] == "BadNode"));
    if bad {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({
                "error": {"type": "invalid_prompt", "message": "Cannot execute because node BadNode does not exist.", "details": ""},
                "node_errors": {}
            })),
        )
            .into_response();
    }
    let slow = workflow
        .as_object()
        .is_some_and(|o| o.values().any(|n| n["class_type"] == "SlowNode"));
    let fails = workflow
        .as_object()
        .is_some_and(|o| o.values().any(|n| n["class_type"] == "ExplodingNode"));
    m.lock().unwrap().prompts.push(body);
    let id = if slow {
        "prun"
    } else if fails {
        "pfail"
    } else {
        "p1"
    };
    Json(json!({"prompt_id": id, "number": 1, "node_errors": {}})).into_response()
}

async fn history(State(m): State<Shared>, Path(id): Path<String>) -> Json<Value> {
    let mut mock = m.lock().unwrap();
    match id.as_str() {
        "p1" if mock.pending_polls > 0 => {
            mock.pending_polls -= 1;
            Json(json!({}))
        },
        "p1" => Json(json!({"p1": {
            "outputs": {"7": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
            "status": {"status_str": "success", "completed": true, "messages": []}
        }})),
        "pfail" => Json(json!({"pfail": {
            "outputs": {},
            "status": {"status_str": "error", "completed": false, "messages": [
                ["execution_error", {"node_id": "4", "node_type": "KSampler",
                 "exception_type": "RuntimeError", "exception_message": "CUDA out of memory"}]
            ]}
        }})),
        _ => Json(json!({})),
    }
}

async fn queue_get() -> Json<Value> {
    Json(json!({
        "queue_running": [[1, "prun", {}, {}, []]],
        "queue_pending": [[3, "pq2", {}, {}, []], [2, "pq", {}, {}, []]]
    }))
}

async fn queue_post(State(m): State<Shared>, Json(body): Json<Value>) -> StatusCode {
    m.lock().unwrap().deleted.push(body);
    StatusCode::OK
}

async fn interrupt(State(m): State<Shared>, Json(body): Json<Value>) -> StatusCode {
    m.lock().unwrap().interrupted.push(body);
    StatusCode::OK
}

async fn object_info_all() -> Json<Value> {
    Json(json!({
        "KSampler": {"category": "sampling"},
        "CheckpointLoaderSimple": {"category": "loaders"}
    }))
}

async fn object_info_one(Path(class): Path<String>) -> Json<Value> {
    match class.as_str() {
        "CheckpointLoaderSimple" => Json(json!({"CheckpointLoaderSimple": {
            "input": {"required": {"ckpt_name": [["flux1-dev-fp8.safetensors", "sdxl.safetensors"], {}]}}
        }})),
        "UpscaleModelLoader" => Json(json!({"UpscaleModelLoader": {
            "input": {"required": {"model_name": ["COMBO", {"options": ["4x-UltraSharp.pth"]}]}}
        }})),
        _ => Json(json!({})),
    }
}

async fn system_stats() -> Json<Value> {
    Json(json!({
        "system": {"python_version": "3.11", "comfyui_version": "0.3.60"},
        "devices": [{"name": "cuda:0 RTX", "type": "cuda", "vram_total": 24, "vram_free": 20}]
    }))
}

async fn view(Query(q): Query<std::collections::HashMap<String, String>>) -> Response {
    if q.get("filename").map(String::as_str) == Some("out.png")
        && q.get("type").map(String::as_str) == Some("output")
    {
        ([(header::CONTENT_TYPE, "image/png")], PNG.to_vec()).into_response()
    } else if q.get("filename").map(String::as_str) == Some("huge.png") {
        ([(header::CONTENT_TYPE, "image/png")], vec![0u8; 4096]).into_response()
    } else {
        StatusCode::NOT_FOUND.into_response()
    }
}

async fn upload(State(m): State<Shared>, headers: HeaderMap, body: Bytes) -> Response {
    let ct = headers
        .get(header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    if !ct.starts_with("multipart/form-data; boundary=") {
        return StatusCode::BAD_REQUEST.into_response();
    }
    let text = String::from_utf8_lossy(&body);
    let name = text
        .split("filename=\"")
        .nth(1)
        .and_then(|rest| rest.split('"').next())
        .unwrap_or("")
        .to_string();
    m.lock().unwrap().uploads.push((name.clone(), body.len()));
    Json(json!({"name": name, "subfolder": "", "type": "input"})).into_response()
}

/// Start the mock and return (server, mock state, lora temp dir).
async fn setup(pending_polls: usize) -> (ComfyUIServer, Shared, tempfile::TempDir) {
    let mock: Shared = Arc::new(Mutex::new(Mock {
        pending_polls,
        ..Default::default()
    }));
    let app = Router::new()
        .route("/prompt", post(post_prompt))
        .route("/history/:id", get(history))
        .route("/queue", get(queue_get).post(queue_post))
        .route("/interrupt", post(interrupt))
        .route("/object_info", get(object_info_all))
        .route("/object_info/:class", get(object_info_one))
        .route("/system_stats", get(system_stats))
        .route("/view", get(view))
        .route("/upload/image", post(upload))
        .with_state(mock.clone());
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    let tmp = tempfile::tempdir().unwrap();
    let config = Config {
        base_url: format!("http://{addr}"),
        comfyui_path: tmp.path().to_path_buf(),
        generation_timeout_secs: 5,
        request_timeout_secs: 5,
        max_image_bytes: 1024,
        max_lora_download_bytes: 1024,
    };
    (
        ComfyUIServer::with_config_and_poll(config, Duration::from_millis(10)),
        mock,
        tmp,
    )
}

async fn call(server: &ComfyUIServer, name: &str, args: Value) -> Result<ToolResult> {
    let tool = server
        .tools()
        .into_iter()
        .find(|t| t.name() == name)
        .unwrap_or_else(|| panic!("no tool {name}"));
    tool.execute(args).await
}

fn body(result: &ToolResult) -> Value {
    match &result.content[0] {
        Content::Text { text } => serde_json::from_str(text).unwrap(),
        other => panic!("expected text, got {other:?}"),
    }
}

fn image_count(result: &ToolResult) -> usize {
    result
        .content
        .iter()
        .filter(|c| matches!(c, Content::Image { .. }))
        .count()
}

#[tokio::test]
async fn generate_image_waits_and_embeds() {
    let (server, mock, _tmp) = setup(3).await;
    let r = call(
        &server,
        "generate_image",
        json!({"prompt": "a fox", "seed": 11, "include_images": true}),
    )
    .await
    .unwrap();
    assert!(!r.is_error, "{:?}", r.content);
    let b = body(&r);
    assert_eq!(b["success"], true);
    assert_eq!(b["status"], "completed");
    assert_eq!(b["job_id"], "p1");
    assert_eq!(b["seed"], 11);
    assert_eq!(b["template"], "flux_default");
    assert_eq!(b["images"][0]["filename"], "out.png");
    assert_eq!(image_count(&r), 1);

    let sent = &mock.lock().unwrap().prompts[0];
    assert_eq!(sent["prompt"]["2"]["inputs"]["text"], "a fox");
    assert_eq!(sent["prompt"]["4"]["inputs"]["seed"], 11);
    assert!(sent["client_id"].is_string());
}

#[tokio::test]
async fn generate_image_reports_execution_failure() {
    let (server, _mock, _tmp) = setup(0).await;
    let wf = json!({
        "1": {"class_type": "ExplodingNode", "inputs": {}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}}
    });
    let r = call(
        &server,
        "generate_image",
        json!({"prompt": "x", "workflow": wf}),
    )
    .await
    .unwrap();
    assert!(r.is_error);
    let b = body(&r);
    assert_eq!(b["status"], "failed");
    assert!(b["error"].as_str().unwrap().contains("CUDA out of memory"));
}

#[tokio::test]
async fn generate_image_timeout_is_reported_with_job_id() {
    let (server, _mock, _tmp) = setup(0).await;
    let wf = json!({"1": {"class_type": "SlowNode", "inputs": {}}});
    let r = call(
        &server,
        "execute_workflow",
        json!({"workflow": wf, "wait": true, "timeout": 1}),
    )
    .await
    .unwrap();
    assert!(r.is_error);
    let b = body(&r);
    assert_eq!(b["status"], "timeout");
    assert_eq!(b["job_id"], "prun");
    assert!(b["error"].as_str().unwrap().contains("get_job_status"));
}

#[tokio::test]
async fn rejected_workflow_surfaces_comfyui_message() {
    let (server, _mock, _tmp) = setup(0).await;
    let r = call(
        &server,
        "execute_workflow",
        json!({"workflow": {"1": {"class_type": "BadNode", "inputs": {}}}}),
    )
    .await
    .unwrap();
    assert!(r.is_error);
    assert!(
        body(&r)["error"]
            .as_str()
            .unwrap()
            .contains("BadNode does not exist")
    );
}

#[tokio::test]
async fn execute_workflow_is_non_blocking_by_default() {
    let (server, _mock, _tmp) = setup(0).await;
    let wf = crate::workflows::sample_workflow("sdxl_default").unwrap();
    let r = call(&server, "execute_workflow", json!({"workflow": wf}))
        .await
        .unwrap();
    assert!(!r.is_error);
    let b = body(&r);
    assert_eq!(b["status"], "queued");
    assert_eq!(b["job_id"], "p1");

    let r = call(&server, "get_job_status", json!({"job_id": "p1"}))
        .await
        .unwrap();
    let b = body(&r);
    assert_eq!(b["status"], "completed");
    assert_eq!(b["submitted"]["tool"], "execute_workflow");
}

#[tokio::test]
async fn job_status_queue_and_cancel() {
    let (server, mock, _tmp) = setup(0).await;
    let b = body(
        &call(&server, "get_job_status", json!({"prompt_id": "pq2"}))
            .await
            .unwrap(),
    );
    assert_eq!(b["status"], "queued");
    assert_eq!(b["queue_position"], 2);

    let r = call(&server, "get_job_status", json!({"job_id": "gone"}))
        .await
        .unwrap();
    assert!(r.is_error);
    assert_eq!(body(&r)["status"], "unknown");

    assert!(
        call(&server, "get_job_status", json!({"job_id": "../x"}))
            .await
            .is_err()
    );

    let q = body(&call(&server, "get_queue", json!({})).await.unwrap());
    assert_eq!(q["running"], json!(["prun"]));
    assert_eq!(q["pending"], json!(["pq", "pq2"]));

    let c = body(
        &call(&server, "cancel_job", json!({"job_id": "pq"}))
            .await
            .unwrap(),
    );
    assert_eq!(c["action"], "removed_from_queue");
    let c = body(
        &call(&server, "cancel_job", json!({"job_id": "prun"}))
            .await
            .unwrap(),
    );
    assert_eq!(c["action"], "interrupted");
    let c = body(
        &call(&server, "cancel_job", json!({"job_id": "p1"}))
            .await
            .unwrap(),
    );
    assert_eq!(c["cancelled"], false);

    let m = mock.lock().unwrap();
    assert_eq!(m.deleted, [json!({"delete": ["pq"]})]);
    assert_eq!(m.interrupted, [json!({"prompt_id": "prun"})]);
}

#[tokio::test]
async fn img2img_with_inline_data_uploads_first() {
    let (server, mock, _tmp) = setup(0).await;
    let data = crate::validate::encode_base64(PNG);
    let r = call(
        &server,
        "generate_image",
        json!({"prompt": "make it snowy", "input_image_data": data, "wait": false}),
    )
    .await
    .unwrap();
    assert!(!r.is_error, "{:?}", r.content);
    let b = body(&r);
    assert_eq!(b["template"], "img2img");
    let reference = b["input_image"].as_str().unwrap().to_string();
    assert!(reference.starts_with("mcp_") && reference.ends_with(".png"));

    let m = mock.lock().unwrap();
    assert_eq!(m.uploads[0].0, reference);
    assert_eq!(m.prompts[0]["prompt"]["8"]["inputs"]["image"], reference);
}

#[tokio::test]
async fn invalid_generation_uploads_nothing() {
    let (server, mock, _tmp) = setup(0).await;
    let data = crate::validate::encode_base64(PNG);
    let err = call(
        &server,
        "generate_image",
        json!({"prompt": "x", "workflow": "controlnet", "input_image_data": data}),
    )
    .await
    .unwrap_err();
    assert!(err.to_string().contains("controlnet_name"));
    assert!(mock.lock().unwrap().uploads.is_empty());
}

#[tokio::test]
async fn upload_and_get_image() {
    let (server, _mock, _tmp) = setup(0).await;
    let data = crate::validate::encode_base64(PNG);
    let b = body(
        &call(
            &server,
            "upload_image",
            json!({"filename": "ref.png", "data": data}),
        )
        .await
        .unwrap(),
    );
    assert_eq!(b["input_image"], "ref.png");

    let bad = call(
        &server,
        "upload_image",
        json!({"filename": "ref.png", "data": crate::validate::encode_base64(b"not an image")}),
    )
    .await
    .unwrap();
    assert!(bad.is_error);

    let r = call(&server, "get_image", json!({"filename": "out.png"}))
        .await
        .unwrap();
    assert!(!r.is_error);
    match &r.content[1] {
        Content::Image { data, mime_type } => {
            assert_eq!(mime_type, "image/png");
            assert_eq!(crate::validate::decode_base64(data).unwrap(), PNG);
        },
        other => panic!("expected image, got {other:?}"),
    }

    let r = call(&server, "get_image", json!({"filename": "missing.png"}))
        .await
        .unwrap();
    assert!(r.is_error);
    let r = call(&server, "get_image", json!({"filename": "huge.png"}))
        .await
        .unwrap();
    assert!(r.is_error);
    assert!(body(&r)["error"].as_str().unwrap().contains("limit"));
    assert!(
        call(
            &server,
            "get_image",
            json!({"filename": "x.png", "subfolder": "../.."})
        )
        .await
        .is_err()
    );
}

#[tokio::test]
async fn models_object_info_and_system() {
    let (server, _mock, _tmp) = setup(0).await;
    let b = body(&call(&server, "list_models", json!({})).await.unwrap());
    assert_eq!(b["count"], 2);
    assert_eq!(b["models"][0], "flux1-dev-fp8.safetensors");

    let b = body(
        &call(
            &server,
            "list_models",
            json!({"model_type": "upscale_model"}),
        )
        .await
        .unwrap(),
    );
    assert_eq!(b["models"], json!(["4x-UltraSharp.pth"]));

    let r = call(&server, "list_models", json!({"type": "vae"}))
        .await
        .unwrap();
    assert!(
        r.is_error,
        "VAELoader missing on mock -> error, not silent empty list"
    );
    assert!(
        call(&server, "list_models", json!({"type": "bogus"}))
            .await
            .is_err()
    );

    let b = body(&call(&server, "get_object_info", json!({})).await.unwrap());
    assert_eq!(b["node_count"], 2);
    let b = body(
        &call(&server, "get_object_info", json!({"full": true}))
            .await
            .unwrap(),
    );
    assert!(b["KSampler"].is_object());
    let b = body(
        &call(
            &server,
            "get_object_info",
            json!({"node_class": "CheckpointLoaderSimple"}),
        )
        .await
        .unwrap(),
    );
    assert!(b["info"]["input"].is_object());

    let b = body(&call(&server, "get_system_info", json!({})).await.unwrap());
    assert_eq!(b["devices"][0]["type"], "cuda");
    assert_eq!(b["system"]["comfyui_version"], "0.3.60");
    assert!(
        b["comfyui_url"]
            .as_str()
            .unwrap()
            .starts_with("http://127.0.0.1:")
    );
}

#[tokio::test]
async fn lora_tools_roundtrip() {
    let (server, _mock, tmp) = setup(0).await;
    let data = crate::validate::encode_base64(b"lora-bytes");
    let b = body(
        &call(
            &server,
            "upload_lora",
            json!({"filename": "style.safetensors", "data": data, "metadata": {"trigger": "zz"}}),
        )
        .await
        .unwrap(),
    );
    assert_eq!(b["size"], 10);
    assert!(tmp.path().join("models/loras/style.safetensors").exists());

    let b = body(&call(&server, "list_loras", json!({})).await.unwrap());
    assert_eq!(b["count"], 1);
    assert_eq!(b["loras"][0]["has_metadata"], true);

    let b = body(
        &call(
            &server,
            "download_lora",
            json!({"filename": "style.safetensors"}),
        )
        .await
        .unwrap(),
    );
    assert_eq!(b["data"], data);

    assert!(
        call(
            &server,
            "upload_lora",
            json!({"filename": "../x.safetensors", "data": data})
        )
        .await
        .is_err()
    );
    assert!(
        call(
            &server,
            "download_lora",
            json!({"filename": "style.safetensors", "encoding": "hex"})
        )
        .await
        .is_err()
    );
    let r = call(
        &server,
        "download_lora",
        json!({"filename": "nope.safetensors"}),
    )
    .await
    .unwrap();
    assert!(r.is_error);
}

#[tokio::test]
async fn workflow_catalog_tools() {
    let (server, _mock, _tmp) = setup(0).await;
    let b = body(&call(&server, "list_workflows", json!({})).await.unwrap());
    assert_eq!(b["workflows"].as_array().unwrap().len(), 6);
    let b = body(
        &call(&server, "get_workflow", json!({"name": "controlnet"}))
            .await
            .unwrap(),
    );
    assert_eq!(b["workflow"]["14"]["class_type"], "ControlNetApplyAdvanced");
    let r = call(&server, "get_workflow", json!({"name": "nope"}))
        .await
        .unwrap();
    assert!(r.is_error);
    assert!(body(&r)["error"].as_str().unwrap().contains("flux_default"));
}

#[tokio::test]
async fn unreachable_comfyui_gives_clear_error() {
    // Bind then drop a listener to get a port nothing listens on.
    let port = {
        let l = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        l.local_addr().unwrap().port()
    };
    let config = Config {
        base_url: format!("http://127.0.0.1:{port}"),
        request_timeout_secs: 2,
        ..Config::default()
    };
    let server = ComfyUIServer::with_config(config);
    let r = call(&server, "get_system_info", json!({})).await.unwrap();
    assert!(r.is_error);
    assert!(
        body(&r)["error"]
            .as_str()
            .unwrap()
            .contains("cannot reach ComfyUI")
    );
}

#[tokio::test]
async fn missing_required_params_are_invalid_parameters() {
    let (server, _mock, _tmp) = setup(0).await;
    for (tool, args) in [
        ("generate_image", json!({})),
        ("generate_image", json!({"prompt": 5})),
        ("execute_workflow", json!({})),
        ("upload_lora", json!({"filename": "a.safetensors"})),
        ("download_lora", json!({})),
        ("get_image", json!({})),
        ("cancel_job", json!({})),
    ] {
        match call(&server, tool, args.clone()).await {
            Err(MCPError::InvalidParameters(_)) => {},
            other => panic!("{tool} {args}: expected InvalidParameters, got {other:?}"),
        }
    }
}
