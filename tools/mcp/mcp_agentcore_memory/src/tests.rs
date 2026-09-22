//! End-to-end tests of the MCP tools over the in-memory store and the hash
//! embedder (fully offline), plus an opt-in live test against a real ChromaDB.

use std::sync::Arc;
use std::time::Duration;

use mcp_core::prelude::*;
use serde_json::{Value, json};

use crate::config::Config;
use crate::embedding::{Embedder, HashEmbedder};
use crate::server::tools;
use crate::service::{MemoryService, fact_id, meta};
use crate::store::VectorStore;
use crate::store::memory::InMemoryStore;

struct Harness {
    store: Arc<InMemoryStore>,
    service: Arc<MemoryService>,
    tools: Vec<BoxedTool>,
}

fn test_config() -> Config {
    Config {
        cache_ttl: Duration::from_secs(60),
        ..Config::default()
    }
}

fn harness_with(embedder: Arc<dyn Embedder>) -> Harness {
    let store = Arc::new(InMemoryStore::default());
    let service = Arc::new(MemoryService::new(&test_config(), store.clone(), embedder));
    Harness {
        tools: tools(service.clone()),
        store,
        service,
    }
}

fn harness() -> Harness {
    harness_with(Arc::new(HashEmbedder::default()))
}

impl Harness {
    async fn call_raw(&self, name: &str, args: Value) -> Result<ToolResult> {
        let tool = self
            .tools
            .iter()
            .find(|t| t.name() == name)
            .unwrap_or_else(|| panic!("no tool {name}"));
        tool.execute(args).await
    }

    /// Call a tool that must succeed and return its JSON body.
    async fn call(&self, name: &str, args: Value) -> Value {
        let r = self.call_raw(name, args).await.expect("tool returned Err");
        assert!(!r.is_error, "tool {name} returned isError: {}", text(&r));
        serde_json::from_str(&text(&r)).expect("tool output is JSON")
    }
}

fn text(r: &ToolResult) -> String {
    match &r.content[0] {
        Content::Text { text } => text.clone(),
        _ => panic!("expected text content"),
    }
}

#[test]
fn registers_all_tools_with_valid_schemas() {
    let h = harness();
    let names: Vec<&str> = h.tools.iter().map(|t| t.name()).collect();
    for expected in [
        "store_event",
        "store_facts",
        "search_memories",
        "list_session_events",
        "list_namespaces",
        "memory_status",
        "list_memories",
        "delete_memories",
        "reindex_namespace",
    ] {
        assert!(names.contains(&expected), "missing tool {expected}");
    }
    for t in &h.tools {
        let s = t.schema();
        assert_eq!(s["type"], "object", "{}", t.name());
        assert!(s["properties"].is_object(), "{}", t.name());
        for req in s["required"].as_array().into_iter().flatten() {
            let key = req.as_str().unwrap();
            assert!(s["properties"].get(key).is_some(), "{}: {key}", t.name());
        }
        assert!(!t.description().is_empty());
    }
}

#[test]
fn original_required_params_unchanged() {
    let h = harness();
    let required = |name: &str| -> Vec<String> {
        let t = h.tools.iter().find(|t| t.name() == name).unwrap();
        let mut v: Vec<String> = t.schema()["required"]
            .as_array()
            .map(|a| a.iter().map(|x| x.as_str().unwrap().to_string()).collect())
            .unwrap_or_default();
        v.sort();
        v
    };
    assert_eq!(
        required("store_event"),
        ["actor_id", "content", "session_id"]
    );
    assert_eq!(required("store_facts"), ["facts", "namespace"]);
    assert_eq!(required("search_memories"), ["namespace", "query"]);
    assert_eq!(required("list_session_events"), ["actor_id", "session_id"]);
    assert!(required("list_namespaces").is_empty());
    assert!(required("memory_status").is_empty());
}

#[tokio::test]
async fn store_and_search_facts() {
    let h = harness();
    let r = h
        .call(
            "store_facts",
            json!({
                "facts": [
                    "All MCP servers use the mcp-core crate for transport",
                    "Bananas are a yellow fruit"
                ],
                "namespace": "codebase/patterns",
                "source": "PR #42"
            }),
        )
        .await;
    assert_eq!(r["success"], true);
    assert_eq!(r["created"], 2);
    assert_eq!(r["duplicates"], 0);
    assert_eq!(r["failed"], 0);
    assert_eq!(r["ids"].as_array().unwrap().len(), 2);

    let s = h
        .call(
            "search_memories",
            json!({"query": "which crate do MCP servers use", "namespace": "codebase/patterns", "top_k": 2}),
        )
        .await;
    assert_eq!(s["cached"], false);
    assert_eq!(s["count"], 2);
    let top = &s["memories"][0];
    assert!(top["content"].as_str().unwrap().contains("mcp-core"));
    assert_eq!(top["source"], "PR #42");
    assert!(top["id"].as_str().unwrap().starts_with("fact-"));
    assert!(top["created_at"].is_string());
    let r0 = top["relevance"].as_f64().unwrap();
    let r1 = s["memories"][1]["relevance"].as_f64().unwrap();
    assert!(r0 > r1, "ranked by relevance: {r0} vs {r1}");

    // Same query again is served from cache.
    let s2 = h
        .call(
            "search_memories",
            json!({"query": "which crate do MCP servers use", "namespace": "codebase/patterns", "top_k": 2}),
        )
        .await;
    assert_eq!(s2["cached"], true);
    assert_eq!(s2["memories"], s["memories"]);

    // min_relevance filters (not cached away).
    let s3 = h
        .call(
            "search_memories",
            json!({"query": "which crate do MCP servers use", "namespace": "codebase/patterns",
                   "top_k": 2, "min_relevance": r1 + 0.0001}),
        )
        .await;
    assert_eq!(s3["count"], 1);
}

#[tokio::test]
async fn store_facts_is_idempotent() {
    let h = harness();
    let args =
        json!({"facts": ["fact one", "fact one", "fact two"], "namespace": "testing/patterns"});
    let r = h.call("store_facts", args.clone()).await;
    assert_eq!(r["created"], 2);
    assert_eq!(r["duplicates"], 1);
    let ids = r["ids"].as_array().unwrap();
    assert_eq!(ids[0], ids[1]);
    assert_eq!(ids[0], fact_id("testing/patterns", "fact one"));

    let r = h.call("store_facts", args).await;
    assert_eq!(r["created"], 0);
    assert_eq!(r["duplicates"], 3);

    let coll = h.service.records_collection("testing/patterns");
    assert_eq!(h.store.count(&coll).await.unwrap(), 2);
}

#[tokio::test]
async fn store_invalidates_search_cache() {
    let h = harness();
    h.call(
        "store_facts",
        json!({"facts": ["alpha beta"], "namespace": "a/b"}),
    )
    .await;
    let args = json!({"query": "alpha", "namespace": "a/b"});
    h.call("search_memories", args.clone()).await;
    assert_eq!(
        h.call("search_memories", args.clone()).await["cached"],
        true
    );
    h.call(
        "store_facts",
        json!({"facts": ["alpha gamma"], "namespace": "a/b"}),
    )
    .await;
    let s = h.call("search_memories", args).await;
    assert_eq!(s["cached"], false);
    assert_eq!(s["count"], 2);
}

#[tokio::test]
async fn top_k_is_part_of_cache_key() {
    let h = harness();
    h.call(
        "store_facts",
        json!({"facts": ["one thing", "two things", "three things"], "namespace": "ns"}),
    )
    .await;
    let s = h
        .call(
            "search_memories",
            json!({"query": "things", "namespace": "ns", "top_k": 1}),
        )
        .await;
    assert_eq!(s["count"], 1);
    let s = h
        .call(
            "search_memories",
            json!({"query": "things", "namespace": "ns", "top_k": 3}),
        )
        .await;
    assert_eq!(s["count"], 3);
    assert_eq!(s["cached"], false);
}

#[tokio::test]
async fn namespaces_are_isolated() {
    let h = harness();
    h.call(
        "store_facts",
        json!({"facts": ["secret sauce recipe"], "namespace": "codebase"}),
    )
    .await;
    let s = h
        .call(
            "search_memories",
            json!({"query": "recipe", "namespace": "codebase/patterns"}),
        )
        .await;
    assert_eq!(s["count"], 0);
}

#[tokio::test]
async fn search_on_unknown_namespace_is_empty_and_creates_nothing() {
    let h = harness();
    let s = h
        .call(
            "search_memories",
            json!({"query": "anything", "namespace": "never/used"}),
        )
        .await;
    assert_eq!(s["count"], 0);
    let ns = h
        .call("list_namespaces", json!({"include_stored": true}))
        .await;
    assert_eq!(ns["stored"], json!([]));
}

#[tokio::test]
async fn secrets_are_redacted_before_storage() {
    let h = harness();
    let r = h
        .call(
            "store_facts",
            json!({"facts": ["deploy uses api_key=abcd1234efgh5678 for auth"], "namespace": "security/patterns"}),
        )
        .await;
    assert_eq!(r["redacted"], 1);
    let l = h
        .call("list_memories", json!({"namespace": "security/patterns"}))
        .await;
    let content = l["memories"][0]["content"].as_str().unwrap();
    assert!(!content.contains("abcd1234efgh5678"), "{content}");
    assert!(content.contains("[REDACTED]"));

    let e = h
        .call(
            "store_event",
            json!({"content": "used token ghp_1234567890abcdefghij1234567890abcdef",
                   "actor_id": "claude", "session_id": "s1",
                   "metadata": {"note": "password: hunter2"}}),
        )
        .await;
    assert_eq!(e["redacted"], true);
    let ev = h
        .call(
            "list_session_events",
            json!({"actor_id": "claude", "session_id": "s1"}),
        )
        .await;
    let dump = ev.to_string();
    assert!(!dump.contains("ghp_1234"), "{dump}");
    assert!(!dump.contains("hunter2"), "{dump}");
}

#[tokio::test]
async fn events_roundtrip_newest_first_with_metadata() {
    let h = harness();
    for i in 0..3 {
        let r = h
            .call(
                "store_event",
                json!({"content": format!("event {i}"), "actor_id": "claude-code", "session_id": "s-1",
                       "metadata": {"step": i, "tags": ["a", "b"], "actor_id": "spoofed", "skip": null}}),
            )
            .await;
        assert_eq!(r["success"], true);
        assert_eq!(r["provider"], "chromadb");
        assert_eq!(r["ignored_metadata_keys"], json!(["actor_id"]));
        tokio::time::sleep(Duration::from_millis(5)).await;
    }
    // Another session must not leak in.
    h.call(
        "store_event",
        json!({"content": "other", "actor_id": "claude-code", "session_id": "s-2"}),
    )
    .await;

    let r = h
        .call(
            "list_session_events",
            json!({"actor_id": "claude-code", "session_id": "s-1", "limit": 2}),
        )
        .await;
    assert_eq!(r["count"], 2);
    assert_eq!(r["total"], 3);
    assert_eq!(r["events"][0]["content"], "event 2");
    assert_eq!(r["events"][1]["content"], "event 1");
    let m = &r["events"][0]["metadata"];
    assert_eq!(m["step"], 2);
    assert_eq!(m["tags"], "[\"a\",\"b\"]");
    assert!(m.get("skip").is_none());
    assert!(
        m.get("actor_id").is_none(),
        "system keys are not echoed as user metadata"
    );
}

#[tokio::test]
async fn list_and_delete_memories() {
    let h = harness();
    let r = h
        .call(
            "store_facts",
            json!({"facts": ["f1", "f2", "f3"], "namespace": "reviews/pr"}),
        )
        .await;
    let ids: Vec<String> = r["ids"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_str().unwrap().to_string())
        .collect();

    let page = h
        .call(
            "list_memories",
            json!({"namespace": "reviews/pr", "limit": 2}),
        )
        .await;
    assert_eq!(page["total"], 3);
    assert_eq!(page["count"], 2);
    let page2 = h
        .call(
            "list_memories",
            json!({"namespace": "reviews/pr", "limit": 2, "offset": 2}),
        )
        .await;
    assert_eq!(page2["count"], 1);

    // Warm the cache, then delete: the cache must be invalidated.
    h.call(
        "search_memories",
        json!({"query": "f1", "namespace": "reviews/pr"}),
    )
    .await;
    assert!(h.service.cache_size() > 0);
    let d = h
        .call(
            "delete_memories",
            json!({"namespace": "reviews/pr", "ids": [ids[0], "missing-id", ids[0]]}),
        )
        .await;
    assert_eq!(d["deleted"], json!([ids[0]]));
    assert_eq!(d["not_found"], json!(["missing-id"]));
    assert_eq!(h.service.cache_size(), 0);

    let page = h
        .call("list_memories", json!({"namespace": "reviews/pr"}))
        .await;
    assert_eq!(page["total"], 2);
}

#[tokio::test]
async fn list_namespaces_backward_compatible_and_stored() {
    let h = harness();
    let r = h.call("list_namespaces", json!({})).await;
    assert_eq!(r["namespaces"]["codebase"]["patterns"], "codebase/patterns");
    assert!(r.get("stored").is_none());
    // Called with no arguments at all (null).
    let r = h.call("list_namespaces", Value::Null).await;
    assert!(r["namespaces"].is_object());

    h.call(
        "store_facts",
        json!({"facts": ["x"], "namespace": "custom/area"}),
    )
    .await;
    h.call(
        "store_facts",
        json!({"facts": ["y", "z"], "namespace": "codebase/patterns"}),
    )
    .await;
    // Legacy collection without namespace metadata: resolved via a record.
    let legacy = h.service.records_collection("legacy/ns");
    h.store.insert_raw(
        &legacy,
        "old-1",
        "old fact",
        meta(&[("namespace", json!("legacy/ns"))]),
        vec![],
    );

    let r = h
        .call("list_namespaces", json!({"include_stored": true}))
        .await;
    let stored = r["stored"].as_array().unwrap();
    let find = |ns: &str| stored.iter().find(|s| s["namespace"] == ns).cloned();
    assert_eq!(find("codebase/patterns").unwrap()["count"], 2);
    assert_eq!(find("codebase/patterns").unwrap()["predefined"], true);
    assert_eq!(find("custom/area").unwrap()["predefined"], false);
    assert_eq!(find("custom/area").unwrap()["embedder"], "hash-v1-256");
    assert_eq!(find("legacy/ns").unwrap()["count"], 1);
}

#[tokio::test]
async fn reindex_makes_legacy_facts_searchable() {
    let h = harness();
    let coll = h.service.records_collection("codebase/architecture");
    // Legacy record: document stored without an embedding.
    h.store.insert_raw(
        &coll,
        "legacy-uuid",
        "The gateway routes requests to MCP servers",
        meta(&[
            ("namespace", json!("codebase/architecture")),
            ("created_at", json!("2025-01-01T00:00:00+00:00")),
            ("source", json!("old")),
        ]),
        vec![],
    );
    let s = h
        .call(
            "search_memories",
            json!({"query": "gateway routes", "namespace": "codebase/architecture"}),
        )
        .await;
    assert_eq!(s["count"], 0, "legacy record has no vector");

    let r = h
        .call(
            "reindex_namespace",
            json!({"namespace": "codebase/architecture"}),
        )
        .await;
    assert_eq!(r["reindexed"], 1);
    assert!(
        h.store
            .embedding_of(&coll, "legacy-uuid")
            .is_some_and(|e| !e.is_empty())
    );

    let s = h
        .call(
            "search_memories",
            json!({"query": "gateway routes", "namespace": "codebase/architecture"}),
        )
        .await;
    assert_eq!(s["count"], 1);
    assert_eq!(s["memories"][0]["source"], "old");
    assert_eq!(s["memories"][0]["created_at"], "2025-01-01T00:00:00+00:00");
}

#[tokio::test]
async fn embedder_mismatch_is_rejected() {
    let store = Arc::new(InMemoryStore::default());
    let a = MemoryService::new(
        &test_config(),
        store.clone(),
        Arc::new(HashEmbedder::new(64)),
    );
    a.store_facts(vec!["hello".into()], "ns", None)
        .await
        .unwrap();

    let b = Arc::new(MemoryService::new(
        &test_config(),
        store.clone(),
        Arc::new(HashEmbedder::new(128)),
    ));
    let tools = tools(b);
    let search = tools
        .iter()
        .find(|t| t.name() == "search_memories")
        .unwrap();
    let r = search
        .execute(json!({"query": "hello", "namespace": "ns"}))
        .await
        .unwrap();
    assert!(r.is_error);
    let body: Value = serde_json::from_str(&text(&r)).unwrap();
    assert_eq!(body["success"], false);
    assert_eq!(body["error_kind"], "incompatible_collection");
    assert!(body["error"].as_str().unwrap().contains("hash-v1-64"));
}

#[tokio::test]
async fn invalid_arguments_are_clean_errors() {
    let h = harness();
    let cases = [
        ("store_event", json!({"content": "x", "actor_id": "a"})),
        (
            "store_event",
            json!({"content": "   ", "actor_id": "a", "session_id": "s"}),
        ),
        (
            "store_event",
            json!({"content": "x", "actor_id": "a\u{0007}", "session_id": "s"}),
        ),
        (
            "store_event",
            json!({"content": "x", "actor_id": "a", "session_id": "s", "metadata": "nope"}),
        ),
        (
            "store_facts",
            json!({"facts": "not-an-array", "namespace": "ns"}),
        ),
        ("store_facts", json!({"facts": [], "namespace": "ns"})),
        (
            "store_facts",
            json!({"facts": ["ok", 5], "namespace": "ns"}),
        ),
        (
            "store_facts",
            json!({"facts": ["ok", ""], "namespace": "ns"}),
        ),
        (
            "store_facts",
            json!({"facts": ["ok"], "namespace": "../etc"}),
        ),
        (
            "store_facts",
            json!({"facts": vec!["x"; 101], "namespace": "ns"}),
        ),
        (
            "search_memories",
            json!({"query": "q", "namespace": "ns", "top_k": 0}),
        ),
        (
            "search_memories",
            json!({"query": "q", "namespace": "ns", "top_k": -3}),
        ),
        (
            "search_memories",
            json!({"query": "q", "namespace": "ns", "top_k": "five"}),
        ),
        (
            "search_memories",
            json!({"query": "q", "namespace": "ns", "min_relevance": 7.0}),
        ),
        ("search_memories", json!({"query": "", "namespace": "ns"})),
        ("search_memories", json!({"namespace": "ns"})),
        (
            "list_session_events",
            json!({"actor_id": "a", "session_id": "s", "limit": 0}),
        ),
        ("list_memories", json!({"namespace": ""})),
        ("delete_memories", json!({"namespace": "ns", "ids": []})),
        ("reindex_namespace", json!({})),
    ];
    for (tool, args) in cases {
        match h.call_raw(tool, args.clone()).await {
            Err(MCPError::InvalidParameters(msg)) => assert!(!msg.is_empty()),
            other => panic!("{tool} {args}: expected InvalidParameters, got {other:?}"),
        }
    }

    let big = "x".repeat(crate::service::MAX_CONTENT_BYTES + 1);
    assert!(matches!(
        h.call_raw(
            "store_event",
            json!({"content": big, "actor_id": "a", "session_id": "s"})
        )
        .await,
        Err(MCPError::InvalidParameters(_))
    ));
}

#[tokio::test]
async fn top_k_above_maximum_is_clamped() {
    let h = harness();
    let facts: Vec<String> = (0..60).map(|i| format!("fact number {i}")).collect();
    h.call("store_facts", json!({"facts": facts, "namespace": "ns"}))
        .await;
    let s = h
        .call(
            "search_memories",
            json!({"query": "fact", "namespace": "ns", "top_k": 1000}),
        )
        .await;
    assert_eq!(s["count"], crate::service::MAX_TOP_K);
}

#[tokio::test]
async fn database_outage_is_reported_not_panicked() {
    let h = harness();
    h.store.set_offline(true);
    let r = h
        .call_raw("store_facts", json!({"facts": ["x"], "namespace": "ns"}))
        .await
        .unwrap();
    assert!(r.is_error);
    let body: Value = serde_json::from_str(&text(&r)).unwrap();
    assert_eq!(body["error_kind"], "store_unavailable");

    let status = h.call("memory_status", json!({})).await;
    assert_eq!(status["status"], "disconnected");
    assert!(status["error"].is_string());

    let ns = h
        .call("list_namespaces", json!({"include_stored": true}))
        .await;
    assert!(ns["namespaces"].is_object(), "predefined still returned");
    assert!(ns["stored_error"].is_string());

    h.store.set_offline(false);
    let status = h.call("memory_status", json!({})).await;
    assert_eq!(status["status"], "connected");
    assert_eq!(status["embedder"]["id"], "hash-v1-256");
    assert_eq!(status["embedder"]["dimension"], 256);
    assert_eq!(status["provider"]["collection_prefix"], "agent_memory");
    assert!(status["cache"]["enabled"].as_bool().unwrap());
}

#[test]
fn collection_names_are_stable() {
    // These names must never change, or existing memories become unreachable.
    let h = harness();
    assert_eq!(h.service.events_collection(), "agent_memory_events");
    let name = h.service.records_collection("codebase/patterns");
    assert!(name.starts_with("agent_memory_rec_"));
    assert_eq!(name.len(), "agent_memory_rec_".len() + 16);
    assert_ne!(name, h.service.records_collection("codebase-patterns"));
    assert_eq!(name, h.service.records_collection("codebase/patterns"));
}

/// Live test against a real ChromaDB. Run with e.g.
/// `CHROMADB_TEST_URL=http://localhost:8000 cargo test -- --ignored live_chromadb`.
#[tokio::test]
#[ignore = "requires a running ChromaDB (set CHROMADB_TEST_URL)"]
async fn live_chromadb_roundtrip() {
    let Ok(url) = std::env::var("CHROMADB_TEST_URL") else {
        eprintln!("CHROMADB_TEST_URL not set; skipping");
        return;
    };
    let config = Config {
        chroma_url: url,
        collection_prefix: format!("acmtest{}", std::process::id()),
        ..test_config()
    };
    let store = Arc::new(crate::store::chroma::ChromaStore::new(&config).unwrap());
    let service = Arc::new(MemoryService::new(
        &config,
        store.clone(),
        Arc::new(HashEmbedder::default()),
    ));
    assert!(store.heartbeat().await.is_ok());

    let r = service
        .store_facts(
            vec![
                "Rust servers use mcp-core".into(),
                "Python is used for ML".into(),
            ],
            "live/test",
            Some("live"),
        )
        .await
        .unwrap();
    assert_eq!(r.created, 2);
    let again = service
        .store_facts(vec!["Rust servers use mcp-core".into()], "live/test", None)
        .await
        .unwrap();
    assert_eq!(again.duplicates, 1);

    let s = service
        .search("which servers use mcp-core", "live/test", 2, None)
        .await
        .unwrap();
    assert_eq!(s["count"], 2, "{s}");
    assert!(
        s["memories"][0]["content"]
            .as_str()
            .unwrap()
            .contains("mcp-core")
    );
    assert!(s["memories"][0]["relevance"].as_f64().unwrap() > 0.0);

    service
        .store_event("live-actor", "live-session", "first", None)
        .await
        .unwrap();
    service
        .store_event("live-actor", "live-session", "second", None)
        .await
        .unwrap();
    let ev = service
        .list_events("live-actor", "live-session", 10)
        .await
        .unwrap();
    assert_eq!(ev["count"], 2);
    assert_eq!(ev["events"][0]["content"], "second");

    let l = service.list_memories("live/test", 10, 0).await.unwrap();
    assert_eq!(l["total"], 2);
    let ns = service.list_namespaces(true).await;
    assert!(
        ns["stored"]
            .as_array()
            .unwrap()
            .iter()
            .any(|s| s["namespace"] == "live/test"),
        "{ns}"
    );
    let d = service
        .delete_memories("live/test", vec![r.ids[0].clone(), "nope".into()])
        .await
        .unwrap();
    assert_eq!(d["deleted"].as_array().unwrap().len(), 1);
    assert_eq!(d["not_found"], json!(["nope"]));
    let re = service.reindex_namespace("live/test").await.unwrap();
    assert_eq!(re["reindexed"], 1);
    let missing = service.search("x", "live/never", 3, None).await.unwrap();
    assert_eq!(missing["count"], 0);
    let status = service.status().await;
    assert_eq!(status["status"], "connected", "{status}");
}
