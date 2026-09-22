//! HTTP checker behavior against a mock server.

mod common;

use std::time::Duration;

use markdown_link_checker::discover::DiscoverOptions;
use markdown_link_checker::filters::IgnoreRules;
use markdown_link_checker::http::{HttpChecker, HttpOptions};
use markdown_link_checker::{CheckOptions, check_paths};
use wiremock::matchers::{method, path};
use wiremock::{Mock, MockServer, ResponseTemplate};

fn fast_options() -> HttpOptions {
    HttpOptions {
        timeout: Duration::from_secs(5),
        retry_base: Duration::from_millis(10),
        max_retry_wait: Duration::from_millis(50),
        ..HttpOptions::default()
    }
}

#[tokio::test]
async fn head_rejected_falls_back_to_get() {
    let server = MockServer::start().await;
    Mock::given(method("HEAD"))
        .and(path("/page"))
        .respond_with(ResponseTemplate::new(405))
        .expect(1)
        .mount(&server)
        .await;
    Mock::given(method("GET"))
        .and(path("/page"))
        .respond_with(ResponseTemplate::new(200))
        .expect(1)
        .mount(&server)
        .await;

    let checker = HttpChecker::new(fast_options()).unwrap();
    assert_eq!(
        checker.check(&format!("{}/page", server.uri())).await,
        Ok(())
    );
}

#[tokio::test]
async fn not_found_is_broken_without_retry() {
    let server = MockServer::start().await;
    Mock::given(path("/missing"))
        .respond_with(ResponseTemplate::new(404))
        .expect(2) // one HEAD + one GET, no retries
        .mount(&server)
        .await;

    let checker = HttpChecker::new(fast_options()).unwrap();
    let err = checker
        .check(&format!("{}/missing", server.uri()))
        .await
        .unwrap_err();
    assert_eq!(err, "HTTP 404 Not Found");
}

#[tokio::test]
async fn rate_limited_then_ok() {
    let server = MockServer::start().await;
    Mock::given(method("HEAD"))
        .and(path("/busy"))
        .respond_with(ResponseTemplate::new(429).insert_header("Retry-After", "0"))
        .up_to_n_times(1)
        .with_priority(1)
        .expect(1)
        .mount(&server)
        .await;
    Mock::given(method("HEAD"))
        .and(path("/busy"))
        .respond_with(ResponseTemplate::new(200))
        .with_priority(2)
        .expect(1)
        .mount(&server)
        .await;

    let checker = HttpChecker::new(fast_options()).unwrap();
    assert_eq!(
        checker.check(&format!("{}/busy", server.uri())).await,
        Ok(())
    );
}

#[tokio::test]
async fn persistent_server_error_exhausts_retries() {
    let server = MockServer::start().await;
    Mock::given(method("HEAD"))
        .and(path("/down"))
        .respond_with(ResponseTemplate::new(503))
        .expect(3)
        .mount(&server)
        .await;
    Mock::given(method("GET"))
        .and(path("/down"))
        .respond_with(ResponseTemplate::new(503))
        .expect(3)
        .mount(&server)
        .await;

    let checker = HttpChecker::new(fast_options()).unwrap();
    let err = checker
        .check(&format!("{}/down", server.uri()))
        .await
        .unwrap_err();
    assert_eq!(err, "HTTP 503 Service Unavailable (after 2 retries)");
}

#[tokio::test]
async fn accepted_status_codes() {
    let server = MockServer::start().await;
    Mock::given(path("/forbidden"))
        .respond_with(ResponseTemplate::new(403))
        .mount(&server)
        .await;

    let url = format!("{}/forbidden", server.uri());
    let strict = HttpChecker::new(fast_options()).unwrap();
    assert!(strict.check(&url).await.is_err());

    let lenient = HttpChecker::new(HttpOptions {
        accept: vec![403],
        ..fast_options()
    })
    .unwrap();
    assert_eq!(lenient.check(&url).await, Ok(()));
}

#[tokio::test]
async fn timeouts_are_reported() {
    let server = MockServer::start().await;
    Mock::given(path("/slow"))
        .respond_with(ResponseTemplate::new(200).set_delay(Duration::from_secs(3)))
        .mount(&server)
        .await;

    let checker = HttpChecker::new(HttpOptions {
        timeout: Duration::from_millis(200),
        max_retries: 0,
        ..fast_options()
    })
    .unwrap();
    let err = checker
        .check(&format!("{}/slow", server.uri()))
        .await
        .unwrap_err();
    assert_eq!(err, "Request timed out");
}

#[tokio::test]
async fn invalid_url_is_reported() {
    let checker = HttpChecker::new(fast_options()).unwrap();
    let err = checker.check("https://exa mple.com/").await.unwrap_err();
    assert!(err.starts_with("Invalid URL"), "{err}");
}

#[tokio::test]
async fn identical_urls_across_files_are_requested_once() {
    let server = MockServer::start().await;
    Mock::given(method("HEAD"))
        .and(path("/shared"))
        .respond_with(ResponseTemplate::new(200))
        .expect(1)
        .mount(&server)
        .await;

    let url = format!("{}/shared", server.uri());
    let a = format!("[one]({url})\n");
    let b = format!("[two]({url}#section)\n");
    let c = format!("<a href=\"{url}\">three</a>\n");
    let dir = common::write_tree(&[("a.md", &a), ("b.md", &b), ("c/d.md", &c)]);

    let options = CheckOptions {
        check_external: true,
        validate_anchors: true,
        check_undefined_refs: true,
        root: dir.path().to_path_buf(),
        ignore: IgnoreRules::new::<&str>(&[], false).unwrap(),
        http: fast_options(),
        discover: DiscoverOptions::default(),
    };
    let results = check_paths(&[dir.path().to_path_buf()], &options)
        .await
        .unwrap();
    assert_eq!(results.files_checked, 3);
    assert_eq!(results.total_links, 3);
    assert!(results.all_valid);
}
