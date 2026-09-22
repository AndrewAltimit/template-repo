//! End-to-end tests that drive the real tools against tiny synthetic videos
//! generated with ffmpeg's `lavfi` sources.
//!
//! They need `ffmpeg`/`ffprobe` in PATH and skip themselves (with a note on
//! stderr) when those are missing, so `cargo test` stays green offline and on
//! machines without ffmpeg. Whisper is replaced by a tiny fake script that
//! writes a canned JSON transcript, so captioning and keyword extraction are
//! exercised without any model.

use std::path::{Path, PathBuf};
use std::time::Duration;

use mcp_core::prelude::*;
use serde_json::{Value, json};

use crate::config::ServerConfig;
use crate::ffmpeg::{self, ffmpeg, media_arg};
use crate::process::run_checked;
use crate::server::VideoEditorServer;
use crate::video;

fn have_ffmpeg() -> bool {
    let ok = which::which("ffmpeg").is_ok() && which::which("ffprobe").is_ok();
    if !ok {
        eprintln!("ffmpeg/ffprobe not in PATH; skipping integration test");
    }
    ok
}

/// Generate a test video: moving test pattern plus audio from an `aevalsrc`
/// expression (in seconds `t`).
async fn make_video(path: &Path, seconds: u32, audio_expr: &str) {
    let audio = format!("aevalsrc=exprs='{audio_expr}':s=48000:d={seconds}");
    run_checked(
        ffmpeg()
            .arg("-y")
            .args([
                "-f",
                "lavfi",
                "-i",
                &format!("testsrc2=s=320x240:r=25:d={seconds}"),
            ])
            .args(["-f", "lavfi", "-i", &audio])
            .args([
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
            ])
            .args(["-c:a", "aac", "-shortest"])
            .arg(media_arg(path)),
        "generate test video",
    )
    .await
    .expect("generate test video");
}

/// Two-colour video with a hard scene change at 2s and continuous tone.
async fn make_scene_video(path: &Path) {
    run_checked(
        ffmpeg()
            .arg("-y")
            .args(["-f", "lavfi", "-i", "color=c=red:s=320x240:r=25:d=2"])
            .args(["-f", "lavfi", "-i", "color=c=blue:s=320x240:r=25:d=2"])
            .args([
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:sample_rate=48000:d=4",
            ])
            .args([
                "-filter_complex",
                "[0:v][1:v]concat=n=2:v=1[v]",
                "-map",
                "[v]",
                "-map",
                "2:a",
            ])
            .args([
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
            ])
            .arg(media_arg(path)),
        "generate scene video",
    )
    .await
    .expect("generate scene video");
}

/// A fake `whisper` executable that writes a fixed transcript.
fn fake_whisper(dir: &Path) -> PathBuf {
    let json = r#"{"text":"hello world this is important","language":"en","segments":[{"id":0,"start":0.2,"end":1.8,"text":"hello world this is important"},{"id":1,"start":2.0,"end":3.5,"text":"second caption line here"}]}"#;
    #[cfg(windows)]
    {
        let path = dir.join("fake_whisper.cmd");
        let script = format!(
            "@echo off\r\nset \"STEM=%~n1\"\r\n:loop\r\nif \"%~1\"==\"\" goto done\r\n\
             if \"%~1\"==\"--output_dir\" set \"OUT=%~2\"\r\nshift\r\ngoto loop\r\n:done\r\n\
             > \"%OUT%\\%STEM%.json\" echo {json}\r\n"
        );
        std::fs::write(&path, script).unwrap();
        path
    }
    #[cfg(not(windows))]
    {
        use std::os::unix::fs::PermissionsExt;
        let path = dir.join("fake_whisper.sh");
        let script = format!(
            "#!/bin/sh\naudio=\"$1\"; out=\"\"\nwhile [ $# -gt 0 ]; do\n  \
             if [ \"$1\" = \"--output_dir\" ]; then out=\"$2\"; fi\n  shift\ndone\n\
             stem=$(basename \"$audio\" .wav)\nprintf '%s' '{json}' > \"$out/$stem.json\"\n"
        );
        std::fs::write(&path, script).unwrap();
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o755)).unwrap();
        path
    }
}

fn server_with(cfg: ServerConfig) -> VideoEditorServer {
    VideoEditorServer::new(cfg)
}

async fn call(server: &VideoEditorServer, name: &str, args: Value) -> (bool, Value) {
    let tool = server
        .tools()
        .into_iter()
        .find(|t| t.name() == name)
        .unwrap();
    let result = tool
        .execute(args)
        .await
        .unwrap_or_else(|e| panic!("{name}: {e}"));
    let text = match &result.content[0] {
        Content::Text { text } => text.clone(),
        _ => panic!("non-text result"),
    };
    (
        result.is_error,
        serde_json::from_str(&text).unwrap_or(Value::String(text)),
    )
}

#[tokio::test]
async fn analyze_detects_silence_and_scenes() {
    if !have_ffmpeg() {
        return;
    }
    let tmp = tempfile::tempdir().unwrap();
    let cfg = ServerConfig::for_root(tmp.path());
    let server = server_with(cfg);
    let vid = tmp.path().join("talk.mp4");
    // Tone for 2s, silence 2-5s, tone 5-7s.
    make_video(&vid, 7, "if(lt(t\\,2)+gt(t\\,5)\\,0.5*sin(2*PI*440*t)\\,0)").await;
    let scene = tmp.path().join("scene.mp4");
    make_scene_video(&scene).await;

    let (err, v) = call(
        &server,
        "video_editor/analyze",
        json!({"video_inputs": [vid, scene], "analysis_options": {"transcribe": false, "identify_speakers": false}}),
    )
    .await;
    assert!(!err, "{v}");
    let a = &v["analysis"][vid.to_str().unwrap()];
    assert_eq!(a["video_info"]["width"], 320);
    let silences = a["audio_analysis"]["silence_segments"].as_array().unwrap();
    assert_eq!(silences.len(), 1, "{silences:?}");
    let (s, e) = (
        silences[0][0].as_f64().unwrap(),
        silences[0][1].as_f64().unwrap(),
    );
    assert!((s - 2.0).abs() < 0.2 && (e - 5.0).abs() < 0.2, "{s}-{e}");
    let scenes = v["analysis"][scene.to_str().unwrap()]["scene_changes"]
        .as_array()
        .unwrap()
        .clone();
    assert!(
        scenes
            .iter()
            .any(|t| (t.as_f64().unwrap() - 2.0).abs() < 0.1),
        "{scenes:?}"
    );
    assert!(v["job_id"].is_string());
}

#[tokio::test]
async fn multicam_edit_and_render_with_transitions() {
    if !have_ffmpeg() {
        return;
    }
    let tmp = tempfile::tempdir().unwrap();
    let cfg = ServerConfig::for_root(tmp.path());
    let server = server_with(cfg.clone());
    let a = tmp.path().join("cam a.mp4");
    let b = tmp.path().join("cam_b.mp4");
    // A speaks 0-3s and 6-9s; B speaks 3-6s. Quiet crosstalk on the other mic.
    let a_expr = "(if(lt(t\\,3)+gt(t\\,6)\\,0.5\\,0.01))*sin(2*PI*300*t)";
    let b_expr = "(if(lt(t\\,3)+gt(t\\,6)\\,0.01\\,0.5))*sin(2*PI*500*t)";
    make_video(&a, 9, a_expr).await;
    make_video(&b, 9, b_expr).await;

    let (err, v) = call(
        &server,
        "video_editor/create_edit",
        json!({"video_inputs": [a, b], "editing_rules": {"zoom_on_emphasis": false, "transition_duration": 0.3}}),
    )
    .await;
    assert!(!err, "{v}");
    assert_eq!(v["strategy"], "speaker");
    let edl = v["edit_decision_list"].as_array().unwrap().clone();
    assert_eq!(edl.len(), 3, "{edl:?}");
    assert_eq!(edl[1]["source"], b.to_str().unwrap());
    assert_eq!(edl[1]["transition_type"], "cross_dissolve");
    assert!(Path::new(v["edl_file"].as_str().unwrap()).is_file());

    let (err, r) = call(
        &server,
        "video_editor/render",
        json!({
            "video_inputs": [a, b],
            "edit_decision_list": edl,
            "output_settings": {"resolution": "320x240", "fps": 25, "bitrate": "500k", "output_path": "multi.mp4"},
            "render_options": {"hardware_acceleration": false}
        }),
    )
    .await;
    assert!(!err, "{r}");
    assert_eq!(r["transitions_rendered"], 2);
    let out = PathBuf::from(r["output_path"].as_str().unwrap());
    assert!(out.starts_with(&cfg.output_dir));
    let info = ffmpeg::probe(&out).await.unwrap();
    // 9s minus two 0.3s cross-fades.
    assert!(
        (info.duration - 8.4).abs() < 0.35,
        "duration {}",
        info.duration
    );
    assert!(info.has_audio && info.width == 320);
    // Temp segments are cleaned up.
    let leftovers: Vec<_> = std::fs::read_dir(&cfg.temp_dir)
        .unwrap()
        .flatten()
        .collect();
    assert!(leftovers.is_empty(), "{leftovers:?}");
}

#[tokio::test]
async fn render_effects_pip_and_silent_sources() {
    if !have_ffmpeg() {
        return;
    }
    let tmp = tempfile::tempdir().unwrap();
    let cfg = ServerConfig::for_root(tmp.path());
    let server = server_with(cfg.clone());
    let a = tmp.path().join("a.mp4");
    make_video(&a, 4, "0.3*sin(2*PI*440*t)").await;
    // Video-only source (no audio stream) must still render (silence is added).
    let silent = tmp.path().join("silent.mp4");
    run_checked(
        ffmpeg()
            .arg("-y")
            .args(["-f", "lavfi", "-i", "testsrc=s=640x360:r=25:d=4"])
            .args([
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
            ])
            .arg(media_arg(&silent)),
        "gen",
    )
    .await
    .unwrap();

    let edl = json!([
        {"timestamp": 0, "duration": 1.5, "source": a, "effects": ["zoom_in"]},
        {"timestamp": 1.5, "duration": 1.5, "source": silent, "pip_source": a, "pip_size": 0.3},
        {"timestamp": 3.5, "duration": 5.0, "source": a}
    ]);
    let (err, r) = call(
        &server,
        "video_editor/render",
        json!({
            "video_inputs": [a],
            "edit_decision_list": edl,
            "output_settings": {"resolution": "320x240", "fps": 25, "format": "mkv"},
            "render_options": {"hardware_acceleration": false, "add_speaker_labels": true}
        }),
    )
    .await;
    assert!(!err, "{r}");
    assert_eq!(r["transitions_rendered"], 0);
    let warnings = r["warnings"].to_string();
    assert!(warnings.contains("shortened"), "{warnings}");
    assert!(warnings.contains("add_speaker_labels"), "{warnings}");
    let out = PathBuf::from(r["output_path"].as_str().unwrap());
    assert_eq!(out.extension().unwrap(), "mkv");
    let info = ffmpeg::probe(&out).await.unwrap();
    assert!(
        (info.duration - 3.5).abs() < 0.3,
        "duration {}",
        info.duration
    );
    assert!(info.has_audio);
}

#[tokio::test]
async fn extract_clips_by_time_and_keyword() {
    if !have_ffmpeg() {
        return;
    }
    let tmp = tempfile::tempdir().unwrap();
    let mut cfg = ServerConfig::for_root(tmp.path());
    cfg.whisper_bin = fake_whisper(tmp.path()).to_string_lossy().to_string();
    let server = server_with(cfg.clone());
    let vid = tmp.path().join("v.mp4");
    make_video(&vid, 6, "0.3*sin(2*PI*440*t)").await;

    let (err, v) = call(
        &server,
        "video_editor/extract_clips",
        json!({
            "video_input": vid,
            "extraction_criteria": {"time_ranges": [[1, 2]], "keywords": ["IMPORTANT"], "speakers": ["SPEAKER_00"],
                                    "min_clip_length": 1.0, "padding": 0.0},
            "output_dir": "myclips"
        }),
    )
    .await;
    assert!(!err, "{v}");
    assert_eq!(v["total_clips"], 2, "{v}");
    let clips = v["clips_extracted"].as_array().unwrap();
    assert_eq!(clips[1]["criteria"], "keyword");
    assert_eq!(clips[1]["keyword"], "IMPORTANT");
    for c in clips {
        let p = PathBuf::from(c["output_path"].as_str().unwrap());
        assert!(p.starts_with(cfg.output_dir.join("myclips")));
        let info = ffmpeg::probe(&p).await.unwrap();
        let expected = c["duration"].as_f64().unwrap();
        assert!(
            (info.duration - expected).abs() < 0.2,
            "{} vs {expected}",
            info.duration
        );
    }
    assert!(v["warnings"].to_string().contains("Speaker-based"));

    // Stream copy mode.
    let (err, v) = call(
        &server,
        "video_editor/extract_clips",
        json!({"video_input": vid, "extraction_criteria": {"time_ranges": [[0, 3]]}, "stream_copy": true}),
    )
    .await;
    assert!(!err, "{v}");
    assert_eq!(v["total_clips"], 1);
}

#[tokio::test]
async fn captions_burn_in_and_soft_subs_with_fake_whisper() {
    if !have_ffmpeg() {
        return;
    }
    let tmp = tempfile::tempdir().unwrap();
    let mut cfg = ServerConfig::for_root(tmp.path());
    cfg.whisper_bin = fake_whisper(tmp.path()).to_string_lossy().to_string();
    let server = server_with(cfg.clone());
    let vid = tmp.path().join("v.mp4");
    make_video(&vid, 4, "0.3*sin(2*PI*440*t)").await;

    let (err, v) = call(
        &server,
        "video_editor/add_captions",
        json!({"video_input": vid, "caption_style": {"max_chars_per_line": 12, "background": "none", "position": "top"}}),
    )
    .await;
    assert!(!err, "{v}");
    let res = &v["languages_processed"][0];
    assert!(res["caption_count"].as_u64().unwrap() >= 2);
    let srt = std::fs::read_to_string(res["srt_path"].as_str().unwrap()).unwrap();
    assert!(srt.contains("00:00:00,200 --> "));
    assert!(
        srt.lines()
            .filter(|l| !l.contains("-->"))
            .all(|l| l.chars().count() <= 12),
        "{srt}"
    );
    assert!(
        ffmpeg::probe(Path::new(res["output_path"].as_str().unwrap()))
            .await
            .unwrap()
            .has_video
    );

    let (err, v) = call(
        &server,
        "video_editor/add_captions",
        json!({"video_input": vid, "burn_in": false, "languages": ["en", "de"], "output_path": "soft.mkv"}),
    )
    .await;
    assert!(!err, "{v}");
    let outs = v["languages_processed"].as_array().unwrap();
    assert_eq!(outs.len(), 2);
    assert!(
        outs[1]["output_path"]
            .as_str()
            .unwrap()
            .ends_with("soft_de.mkv")
    );
}

#[tokio::test]
async fn subtitle_filter_escaping_survives_hostile_paths() {
    if !have_ffmpeg() {
        return;
    }
    let tmp = tempfile::tempdir().unwrap();
    let vid = tmp.path().join("v.mp4");
    make_video(&vid, 2, "0.1*sin(2*PI*440*t)").await;
    let nasty = tmp.path().join("we'ird, [dir]; x=y");
    std::fs::create_dir_all(&nasty).unwrap();
    let srt = nasty.join("sub's, file.srt");
    std::fs::write(&srt, "1\n00:00:00,000 --> 00:00:01,500\nHello\n\n").unwrap();
    let out = nasty.join("out'put.mp4");
    let style = crate::captions::force_style(&crate::types::CaptionStyle::default(), 240).unwrap();
    video::burn_subtitles(&vid, &srt, &style, &out)
        .await
        .expect("burn with hostile paths");
    assert!(ffmpeg::probe(&out).await.unwrap().duration > 1.5);
}

#[tokio::test]
async fn background_render_can_be_polled_and_cancelled() {
    if !have_ffmpeg() {
        return;
    }
    let tmp = tempfile::tempdir().unwrap();
    let cfg = ServerConfig::for_root(tmp.path());
    let server = server_with(cfg);
    let vid = tmp.path().join("v.mp4");
    make_video(&vid, 3, "0.3*sin(2*PI*440*t)").await;

    let (err, v) = call(
        &server,
        "video_editor/render",
        json!({"video_inputs": [vid], "background": true,
               "edit_decision_list": [{"timestamp": 0, "duration": 2, "source": vid}],
               "output_settings": {"resolution": "320x240"},
               "render_options": {"hardware_acceleration": false}}),
    )
    .await;
    assert!(!err, "{v}");
    let job_id = v["job_id"].as_str().unwrap().to_string();
    let mut status = Value::Null;
    for _ in 0..600 {
        let (_, s) = call(
            &server,
            "video_editor/get_job_status",
            json!({"job_id": job_id}),
        )
        .await;
        status = s;
        if status["status"] == "completed" || status["status"] == "failed" {
            break;
        }
        tokio::time::sleep(Duration::from_millis(100)).await;
    }
    assert_eq!(status["status"], "completed", "{status}");
    assert!(status["result"]["output_path"].is_string());

    // Cancel a second, long-running job.
    let (_, v) = call(
        &server,
        "video_editor/render",
        json!({"video_inputs": [vid], "background": true,
               "edit_decision_list": [{"timestamp": 0, "duration": 3, "source": vid}]}),
    )
    .await;
    let job_id = v["job_id"].as_str().unwrap().to_string();
    let (err, c) = call(
        &server,
        "video_editor/cancel_job",
        json!({"job_id": job_id}),
    )
    .await;
    assert!(!err);
    assert!(
        c["status"] == "cancelled" || c["status"] == "completed",
        "{c}"
    );
}

#[tokio::test]
async fn render_with_hardware_acceleration_or_fallback() {
    if !have_ffmpeg() {
        return;
    }
    let tmp = tempfile::tempdir().unwrap();
    let mut cfg = ServerConfig::for_root(tmp.path());
    cfg.enable_gpu = true;
    let server = server_with(cfg);
    let vid = tmp.path().join("v.mp4");
    make_video(&vid, 2, "0.3*sin(2*PI*440*t)").await;
    let (err, r) = call(
        &server,
        "video_editor/render",
        json!({"video_inputs": [vid],
               "edit_decision_list": [{"timestamp": 0, "duration": 2, "source": vid}],
               "output_settings": {"resolution": "320x240"}}),
    )
    .await;
    assert!(!err, "{r}");
    let codec = r["codec"].as_str().unwrap();
    assert!(codec == "h264_nvenc" || codec == "libx264", "{codec}");
}
