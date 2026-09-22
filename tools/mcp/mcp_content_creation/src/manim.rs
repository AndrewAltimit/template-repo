//! Manim helpers: scene detection, CLI argument construction, and locating
//! the rendered file. Nothing in here spawns processes.

use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::sync::LazyLock;
use std::time::SystemTime;

use regex::Regex;

use crate::types::{ManimFormat, ManimQuality};

/// Top-level `class Name(Bases):` definitions.
static CLASS_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?m)^class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*:")
        .expect("static regex is valid")
});

/// A class defined at the top level of a Manim script.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClassDef {
    pub name: String,
    /// Whether any base class name ends with `Scene` (Scene, ThreeDScene,
    /// MovingCameraScene, ...).
    pub is_scene: bool,
}

/// Find top-level class definitions in a script.
pub fn find_classes(script: &str) -> Vec<ClassDef> {
    CLASS_RE
        .captures_iter(script)
        .map(|c| {
            let bases = c.get(2).map(|m| m.as_str()).unwrap_or("");
            let is_scene = bases
                .split(',')
                .map(|b| b.trim().rsplit('.').next().unwrap_or("").trim())
                .any(|b| b.ends_with("Scene"));
            ClassDef {
                name: c[1].to_string(),
                is_scene,
            }
        })
        .collect()
}

/// Is `name` a valid Python identifier (ASCII subset)?
pub fn is_identifier(name: &str) -> bool {
    let mut chars = name.chars();
    matches!(chars.next(), Some(c) if c.is_ascii_alphabetic() || c == '_')
        && chars.all(|c| c.is_ascii_alphanumeric() || c == '_')
        && name.len() <= 128
}

/// Pick the scene to render.
///
/// Returns the scene name plus any warnings. An explicitly requested scene
/// must be defined in the script. Otherwise the first `*Scene` subclass is
/// used (manim would otherwise prompt on stdin when several scenes exist).
pub fn select_scene(
    script: &str,
    requested: Option<&str>,
) -> Result<(String, Vec<String>), String> {
    let classes = find_classes(script);
    let scenes: Vec<&str> = classes
        .iter()
        .filter(|c| c.is_scene)
        .map(|c| c.name.as_str())
        .collect();

    if let Some(name) = requested.map(str::trim).filter(|s| !s.is_empty()) {
        if !is_identifier(name) {
            return Err(format!(
                "scene_name '{}' is not a valid Python identifier",
                name
            ));
        }
        if classes.iter().any(|c| c.name == name) {
            return Ok((name.to_string(), Vec::new()));
        }
        return Err(format!(
            "scene_name '{}' is not defined in the script (found scenes: {})",
            name,
            if scenes.is_empty() {
                "none".to_string()
            } else {
                scenes.join(", ")
            }
        ));
    }

    match scenes.as_slice() {
        [] => Err(
            "no Scene subclass found in the script; define e.g. `class MyScene(Scene):` at top level"
                .to_string(),
        ),
        [only] => Ok((only.to_string(), Vec::new())),
        [first, rest @ ..] => Ok((
            first.to_string(),
            vec![format!(
                "script defines several scenes; rendered '{}' (pass scene_name to choose one of: {})",
                first,
                rest.join(", ")
            )],
        )),
    }
}

/// Build the argument list for `manim`.
///
/// PNG output uses `-s` (save last frame); video formats use `--format`.
/// Preview windows (`-p`) are never requested: the server is headless.
pub fn build_args(
    script_path: &Path,
    scene: &str,
    format: ManimFormat,
    quality: ManimQuality,
    media_dir: &Path,
) -> Vec<OsString> {
    let mut args: Vec<OsString> = vec![
        "render".into(),
        "-q".into(),
        quality.flag().into(),
        "--media_dir".into(),
        media_dir.as_os_str().to_owned(),
        "--disable_caching".into(),
        "--progress_bar".into(),
        "none".into(),
        "-v".into(),
        "WARNING".into(),
    ];
    match format {
        ManimFormat::Png => args.push("-s".into()),
        other => {
            args.push("--format".into());
            args.push(other.as_str().into());
        },
    }
    args.push(script_path.as_os_str().to_owned());
    args.push(scene.into());
    args
}

/// Locate the rendered output for `scene` inside `media_dir`.
///
/// Manim writes videos to `videos/<module>/<quality>/<Scene>.<ext>` (with
/// intermediate chunks under `partial_movie_files/`, which are skipped) and
/// last-frame images to `images/<module>/<Scene>[_ManimCE_vX].png`. The most
/// recently modified match wins.
pub fn find_output(media_dir: &Path, scene: &str, ext: &str) -> Option<PathBuf> {
    let mut best: Option<(SystemTime, PathBuf)> = None;
    let mut stack = vec![media_dir.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let Ok(entries) = std::fs::read_dir(&dir) else {
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            let Ok(ft) = entry.file_type() else { continue };
            if ft.is_dir() {
                if entry.file_name() != "partial_movie_files" {
                    stack.push(path);
                }
                continue;
            }
            if !ft.is_file() {
                continue;
            }
            let matches_ext = path
                .extension()
                .and_then(|e| e.to_str())
                .is_some_and(|e| e.eq_ignore_ascii_case(ext));
            let stem = path.file_stem().and_then(|s| s.to_str()).unwrap_or("");
            let matches_scene = stem == scene || stem.starts_with(&format!("{}_", scene));
            if matches_ext && matches_scene {
                let mtime = entry
                    .metadata()
                    .and_then(|m| m.modified())
                    .unwrap_or(SystemTime::UNIX_EPOCH);
                if best.as_ref().is_none_or(|(t, _)| mtime >= *t) {
                    best = Some((mtime, path));
                }
            }
        }
    }
    best.map(|(_, p)| p)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    const SCRIPT: &str = "\
from manim import *

class Helper(object):
    pass

class Intro(Scene):
    def construct(self):
        class Inner(Scene):
            pass
        self.play(Write(Text('hi')))

class Orbit(mn.ThreeDScene):
    pass
";

    #[test]
    fn finds_top_level_classes_only() {
        let classes = find_classes(SCRIPT);
        let names: Vec<&str> = classes.iter().map(|c| c.name.as_str()).collect();
        assert_eq!(names, vec!["Helper", "Intro", "Orbit"]);
        assert!(!classes[0].is_scene);
        assert!(classes[1].is_scene);
        assert!(classes[2].is_scene);
    }

    #[test]
    fn selects_first_scene_with_warning_when_ambiguous() {
        let (scene, warnings) = select_scene(SCRIPT, None).unwrap();
        assert_eq!(scene, "Intro");
        assert_eq!(warnings.len(), 1);
        assert!(warnings[0].contains("Orbit"));
    }

    #[test]
    fn respects_requested_scene() {
        let (scene, warnings) = select_scene(SCRIPT, Some("Orbit")).unwrap();
        assert_eq!(scene, "Orbit");
        assert!(warnings.is_empty());
        assert!(select_scene(SCRIPT, Some("Missing")).is_err());
        assert!(select_scene(SCRIPT, Some("bad name; rm")).is_err());
    }

    #[test]
    fn errors_without_scene() {
        assert!(select_scene("print('hi')", None).is_err());
        assert!(select_scene("class A(object):\n    pass\n", None).is_err());
    }

    #[test]
    fn identifier_check() {
        assert!(is_identifier("MyScene_2"));
        assert!(is_identifier("_x"));
        assert!(!is_identifier("2x"));
        assert!(!is_identifier(""));
        assert!(!is_identifier("a-b"));
    }

    #[test]
    fn args_use_format_or_last_frame() {
        let args = build_args(
            Path::new("s.py"),
            "Intro",
            ManimFormat::Gif,
            ManimQuality::High,
            Path::new("media"),
        );
        let args: Vec<String> = args.iter().map(|a| a.to_string_lossy().into()).collect();
        assert!(args.windows(2).any(|w| w == ["--format", "gif"]));
        assert!(args.windows(2).any(|w| w == ["-q", "h"]));
        assert!(!args.iter().any(|a| a.starts_with("-p")));
        assert_eq!(args.last().unwrap(), "Intro");

        let png = build_args(
            Path::new("s.py"),
            "Intro",
            ManimFormat::Png,
            ManimQuality::Low,
            Path::new("media"),
        );
        assert!(png.iter().any(|a| a == "-s"));
        assert!(!png.iter().any(|a| a == "--format"));
    }

    #[test]
    fn find_output_skips_partials_and_other_scenes() {
        let media = tempfile::tempdir().unwrap();
        let videos = media.path().join("videos/animation/480p15");
        fs::create_dir_all(videos.join("partial_movie_files/Intro")).unwrap();
        fs::write(videos.join("partial_movie_files/Intro/Intro.mp4"), "p").unwrap();
        fs::write(videos.join("Other.mp4"), "o").unwrap();
        assert!(find_output(media.path(), "Intro", "mp4").is_none());

        fs::write(videos.join("Intro.mp4"), "v").unwrap();
        let found = find_output(media.path(), "Intro", "mp4").unwrap();
        assert_eq!(found, videos.join("Intro.mp4"));

        let images = media.path().join("images/animation");
        fs::create_dir_all(&images).unwrap();
        fs::write(images.join("Intro_ManimCE_v0.19.0.png"), "i").unwrap();
        assert!(find_output(media.path(), "Intro", "png").is_some());
        assert!(find_output(media.path(), "Intr", "png").is_none());
    }
}
