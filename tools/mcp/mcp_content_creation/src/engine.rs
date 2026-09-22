//! Content creation engine: orchestrates LaTeX, poppler, pdf2svg, and Manim
//! subprocesses and turns their results into tool responses.
//!
//! Security model for LaTeX (untrusted input is expected):
//! - compilation runs in a fresh temporary directory;
//! - `-no-shell-escape` plus `shell_escape=f` disable `\write18`;
//! - `openin_any=p` / `openout_any=p` (kpathsea "paranoid" mode) forbid
//!   reading or writing absolute paths, parent directories, and dotfiles, so
//!   `\input{/etc/passwd}` or `\openout` to arbitrary locations fail;
//! - `dvips -R2` disables backtick commands in `\special`;
//! - every subprocess has a deadline and is killed when it expires.
//!
//! Manim scripts are arbitrary Python and are executed as-is; the only
//! protections are the timeout, the temporary working directory, and the
//! container the server runs in.

use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{Duration, Instant};

use serde::Serialize;
use tokio::process::Command;
use tokio::sync::Semaphore;
use tracing::{debug, info, warn};

use crate::latex;
use crate::manim;
use crate::paths::{PathPolicy, sanitize_stem, unique_stem};
use crate::process::{self, CmdError, truncate_chars};
use crate::types::{
    CompileLatexArgs, CompileResult, LatexFormat, LatexTemplate, ManimArgs, ManimFormat,
    ManimQuality, ManimResult, PreviewPdfArgs, PreviewResult, RenderTikzArgs, ResponseMode,
    TikzFormat, non_empty, round2,
};

/// Default DPI for page previews.
pub const PREVIEW_DPI_STANDARD: u32 = 150;
/// Default DPI for `render_tikz` PNG output.
pub const PREVIEW_DPI_HIGH: u32 = 300;
/// Accepted DPI range; values outside are clamped (with a warning).
pub const DPI_RANGE: (u32, u32) = (36, 600);
/// Maximum number of pages rendered by a single preview request.
pub const MAX_PREVIEW_PAGES: usize = 50;
/// Maximum size of inline LaTeX / TikZ content.
pub const MAX_LATEX_BYTES: usize = 2 * 1024 * 1024;
/// Maximum size of a Manim script.
pub const MAX_SCRIPT_BYTES: usize = 1024 * 1024;
/// Maximum number of LaTeX runs for one document.
const MAX_LATEX_PASSES: u32 = 4;
/// Deadline for quick helper tools (pdfinfo, `--version` probes).
const QUICK_TIMEOUT: Duration = Duration::from_secs(30);
/// Job name used for the main `.tex` file inside the temp directory.
const JOB_NAME: &str = "document";

/// Names (or paths) of the external executables the engine invokes.
#[derive(Debug, Clone)]
pub struct Binaries {
    pub pdflatex: String,
    pub latex: String,
    pub dvips: String,
    pub bibtex: String,
    pub pdfinfo: String,
    pub pdftoppm: String,
    pub pdf2svg: String,
    pub manim: String,
}

impl Default for Binaries {
    fn default() -> Self {
        Self {
            pdflatex: "pdflatex".into(),
            latex: "latex".into(),
            dvips: "dvips".into(),
            bibtex: "bibtex".into(),
            pdfinfo: "pdfinfo".into(),
            pdftoppm: "pdftoppm".into(),
            pdf2svg: "pdf2svg".into(),
            manim: "manim".into(),
        }
    }
}

/// Engine configuration (populated from CLI flags / environment in `main`).
#[derive(Debug, Clone)]
pub struct EngineConfig {
    pub output_dir: PathBuf,
    pub project_root: PathBuf,
    pub host_project_root: Option<PathBuf>,
    pub host_output_dir: String,
    pub latex_timeout: Duration,
    pub manim_timeout: Duration,
    pub max_concurrent_jobs: usize,
    pub binaries: Binaries,
}

impl EngineConfig {
    /// Configuration with default timeouts and binaries.
    pub fn new(output_dir: PathBuf, project_root: PathBuf) -> Self {
        Self {
            output_dir,
            project_root,
            host_project_root: None,
            host_output_dir: "outputs/mcp-content".into(),
            latex_timeout: Duration::from_secs(120),
            manim_timeout: Duration::from_secs(600),
            max_concurrent_jobs: 2,
            binaries: Binaries::default(),
        }
    }
}

/// Availability of one external tool, as reported by `content_creation_status`.
#[derive(Debug, Clone, Serialize)]
pub struct DependencyStatus {
    pub name: &'static str,
    pub command: String,
    pub available: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hint: Option<&'static str>,
}

/// Successful LaTeX job output.
struct LatexOutput {
    /// Final file in the latex output directory.
    path: PathBuf,
    passes: u32,
    warnings: Vec<String>,
}

/// The content creation engine. Cheap to share behind an `Arc`.
pub struct ContentEngine {
    cfg: EngineConfig,
    paths: PathPolicy,
    manim_output_dir: PathBuf,
    latex_output_dir: PathBuf,
    preview_output_dir: PathBuf,
    jobs: Arc<Semaphore>,
}

impl ContentEngine {
    /// Create the engine and its output directories.
    pub fn new(cfg: EngineConfig) -> Self {
        let manim_output_dir = cfg.output_dir.join("manim");
        let latex_output_dir = cfg.output_dir.join("latex");
        let preview_output_dir = cfg.output_dir.join("previews");

        for dir in [&manim_output_dir, &latex_output_dir, &preview_output_dir] {
            if let Err(e) = std::fs::create_dir_all(dir) {
                warn!("Failed to create directory {}: {}", dir.display(), e);
            }
        }

        let paths = PathPolicy::new(
            cfg.project_root.clone(),
            cfg.output_dir.clone(),
            cfg.host_project_root.clone(),
            cfg.host_output_dir.clone(),
        );

        info!(
            "Content engine ready (output_dir: {}, project_root: {})",
            cfg.output_dir.display(),
            cfg.project_root.display()
        );

        Self {
            jobs: Arc::new(Semaphore::new(cfg.max_concurrent_jobs.max(1))),
            cfg,
            paths,
            manim_output_dir,
            latex_output_dir,
            preview_output_dir,
        }
    }

    /// Engine configuration.
    pub fn config(&self) -> &EngineConfig {
        &self.cfg
    }

    // ------------------------------------------------------------------
    // compile_latex
    // ------------------------------------------------------------------

    /// Compile a LaTeX document from inline content or a project file.
    pub async fn compile_latex(&self, args: CompileLatexArgs) -> CompileResult {
        let start = Instant::now();
        let format = args.output_format.unwrap_or(LatexFormat::Pdf);
        let template = args.template.unwrap_or(LatexTemplate::Custom);
        let mode = args.response_mode.unwrap_or(ResponseMode::Standard);
        let mut warnings = Vec::new();

        let (raw, source_dir, stem_prefix) = match (&args.content, &args.input_path) {
            (None, None) => {
                return CompileResult::failure("Must provide either 'content' or 'input_path'");
            },
            (Some(_), Some(_)) => {
                return CompileResult::failure(
                    "Provide only one of 'content' or 'input_path', not both",
                );
            },
            (Some(content), None) => (content.clone(), None, "document".to_string()),
            (None, Some(path)) => {
                let resolved = match self.paths.resolve_input_file(path) {
                    Ok(p) => p,
                    Err(e) => return CompileResult::failure(e),
                };
                match tokio::fs::read(&resolved).await {
                    Ok(bytes) if bytes.len() > MAX_LATEX_BYTES => {
                        return CompileResult::failure(format!(
                            "input file is larger than {} bytes",
                            MAX_LATEX_BYTES
                        ));
                    },
                    Ok(bytes) => {
                        let stem = resolved
                            .file_stem()
                            .map(|s| s.to_string_lossy().into_owned())
                            .unwrap_or_else(|| "document".into());
                        (
                            String::from_utf8_lossy(&bytes).into_owned(),
                            resolved.parent().map(Path::to_path_buf),
                            sanitize_stem(&stem),
                        )
                    },
                    Err(e) => {
                        return CompileResult::failure(format!("Failed to read input file: {}", e));
                    },
                }
            },
        };

        if raw.len() > MAX_LATEX_BYTES {
            return CompileResult::failure(format!(
                "content is larger than {} bytes",
                MAX_LATEX_BYTES
            ));
        }
        if raw.trim().is_empty() {
            return CompileResult::failure("LaTeX content is empty");
        }
        if template != LatexTemplate::Custom && latex::has_documentclass(&raw) {
            warnings.push(format!(
                "template '{}' ignored because the content already has \\documentclass",
                template.as_str()
            ));
        }
        let document = latex::wrap_with_template(&raw, template);

        let preview_spec = match (&args.preview_pages, args.visual_feedback) {
            (Some(spec), _) => spec.clone(),
            (None, Some(true)) => "1".to_string(),
            _ => "none".to_string(),
        };
        if format != LatexFormat::Pdf && !is_none_spec(&preview_spec) {
            warnings.push("previews are only generated for PDF output".to_string());
        }
        let dpi = clamp_dpi(
            args.preview_dpi.unwrap_or(PREVIEW_DPI_STANDARD),
            &mut warnings,
        );

        let _permit = self.acquire().await;

        let output = match self
            .run_latex_job(&document, source_dir.as_deref(), format, &stem_prefix)
            .await
        {
            Ok(o) => o,
            Err(e) => return CompileResult::failure(e),
        };
        warnings.extend(output.warnings);

        let page_count = if format == LatexFormat::Pdf {
            match self.pdf_page_count(&output.path).await {
                Ok(n) => Some(n),
                Err(e) => {
                    warnings.push(format!("could not determine page count: {}", e));
                    None
                },
            }
        } else {
            None
        };

        let mut preview_paths = None;
        if format == LatexFormat::Pdf && !is_none_spec(&preview_spec) {
            match page_count {
                Some(total) => match latex::parse_page_spec(&preview_spec, total) {
                    Ok(pages) if pages.is_empty() => warnings.push(format!(
                        "preview_pages '{}' selects no pages (document has {})",
                        preview_spec, total
                    )),
                    Ok(pages) => {
                        let pages = cap_pages(pages, &mut warnings);
                        let base = file_stem(&output.path);
                        let (paths, errs) =
                            self.export_pages(&output.path, &base, &pages, dpi).await;
                        warnings.extend(errs);
                        preview_paths =
                            Some(paths.iter().map(|p| self.paths.to_host_path(p)).collect());
                    },
                    Err(e) => warnings.push(e),
                },
                None => warnings.push("previews skipped: page count unavailable".to_string()),
            }
        }

        let mut result = CompileResult {
            success: true,
            output_path: Some(self.paths.to_host_path(&output.path)),
            container_path: Some(output.path.to_string_lossy().into_owned()),
            page_count,
            file_size_kb: Some(file_size_kb(&output.path).await),
            warnings: non_empty(warnings),
            ..Default::default()
        };
        if mode == ResponseMode::Standard {
            result.format = Some(format.as_str().to_string());
            result.compile_time_seconds = Some(round2(start.elapsed().as_secs_f64()));
            result.latex_passes = Some(output.passes);
            result.preview_paths = preview_paths;
        }
        result
    }

    // ------------------------------------------------------------------
    // render_tikz
    // ------------------------------------------------------------------

    /// Render a TikZ snippet as a standalone PDF, PNG, or SVG.
    pub async fn render_tikz(&self, args: RenderTikzArgs) -> CompileResult {
        let format = args.output_format.unwrap_or(TikzFormat::Pdf);
        let mode = args.response_mode.unwrap_or(ResponseMode::Standard);
        let mut warnings = Vec::new();

        if args.tikz_code.len() > MAX_LATEX_BYTES {
            return CompileResult::failure(format!(
                "tikz_code is larger than {} bytes",
                MAX_LATEX_BYTES
            ));
        }
        let document = match latex::build_tikz_document(
            &args.tikz_code,
            args.tikz_libraries.as_deref().unwrap_or(&[]),
            args.packages.as_deref().unwrap_or(&[]),
        ) {
            Ok(d) => d,
            Err(e) => return CompileResult::failure(e),
        };
        let dpi = clamp_dpi(args.dpi.unwrap_or(PREVIEW_DPI_HIGH), &mut warnings);
        if format != TikzFormat::Png && args.dpi.is_some() {
            warnings.push("dpi only applies to PNG output".to_string());
        }

        let _permit = self.acquire().await;

        let output = match self
            .run_latex_job(&document, None, LatexFormat::Pdf, "tikz")
            .await
        {
            Ok(o) => o,
            Err(e) => return CompileResult::failure(e),
        };
        warnings.extend(output.warnings);

        let final_path = match format {
            TikzFormat::Pdf => output.path.clone(),
            TikzFormat::Png | TikzFormat::Svg => {
                match self.convert_pdf(&output.path, format, dpi).await {
                    Ok(p) => p,
                    Err(e) => {
                        return CompileResult::failure(format!("Format conversion error: {}", e));
                    },
                }
            },
        };

        let mut result = CompileResult {
            success: true,
            output_path: Some(self.paths.to_host_path(&final_path)),
            container_path: Some(final_path.to_string_lossy().into_owned()),
            file_size_kb: Some(file_size_kb(&final_path).await),
            warnings: non_empty(warnings),
            ..Default::default()
        };
        if format == TikzFormat::Pdf {
            result.page_count = Some(1);
        }
        if mode == ResponseMode::Standard {
            result.format = Some(format.as_str().to_string());
            result.latex_passes = Some(output.passes);
            if format != TikzFormat::Pdf {
                result.pdf_path = Some(self.paths.to_host_path(&output.path));
            }
        }
        result
    }

    // ------------------------------------------------------------------
    // preview_pdf
    // ------------------------------------------------------------------

    /// Render selected pages of an existing PDF to PNG.
    pub async fn preview_pdf(&self, args: PreviewPdfArgs) -> PreviewResult {
        let mode = args.response_mode.unwrap_or(ResponseMode::Standard);
        let spec = args.pages.as_deref().unwrap_or("1");
        let mut warnings = Vec::new();
        let dpi = clamp_dpi(args.dpi.unwrap_or(PREVIEW_DPI_STANDARD), &mut warnings);

        let resolved = match self.paths.resolve_input_file(&args.pdf_path) {
            Ok(p) => p,
            Err(e) => return PreviewResult::failure(e),
        };

        let _permit = self.acquire().await;

        let page_count = match self.pdf_page_count(&resolved).await {
            Ok(n) if n > 0 => n,
            Ok(_) => return PreviewResult::failure("PDF reports zero pages"),
            Err(e) => return PreviewResult::failure(e),
        };

        let pages = match latex::parse_page_spec(spec, page_count) {
            Ok(p) if p.is_empty() => {
                return PreviewResult::failure(format!(
                    "No valid pages in specification '{}' (PDF has {} pages)",
                    spec, page_count
                ));
            },
            Ok(p) => cap_pages(p, &mut warnings),
            Err(e) => return PreviewResult::failure(e),
        };

        let base = unique_stem(&file_stem(&resolved));
        let (paths, errs) = self.export_pages(&resolved, &base, &pages, dpi).await;
        if paths.is_empty() {
            let detail = errs.first().cloned().unwrap_or_default();
            return PreviewResult::failure(format!("Failed to generate previews: {}", detail));
        }
        warnings.extend(errs);

        let mut result = PreviewResult {
            success: true,
            preview_paths: Some(paths.iter().map(|p| self.paths.to_host_path(p)).collect()),
            warnings: non_empty(warnings),
            ..Default::default()
        };
        if mode == ResponseMode::Standard {
            result.pdf_path = Some(self.paths.to_host_path(&resolved));
            result.page_count = Some(page_count);
            result.pages_exported = Some(pages);
        }
        result
    }

    // ------------------------------------------------------------------
    // create_manim_animation
    // ------------------------------------------------------------------

    /// Render a Manim scene.
    pub async fn create_manim_animation(&self, args: ManimArgs) -> ManimResult {
        let start = Instant::now();
        let format = if args.preview == Some(true) {
            ManimFormat::Png
        } else {
            args.output_format.unwrap_or(ManimFormat::Mp4)
        };
        let quality = args.quality.unwrap_or(ManimQuality::Low);

        if args.script.len() > MAX_SCRIPT_BYTES {
            return ManimResult::failure(format!(
                "script is larger than {} bytes",
                MAX_SCRIPT_BYTES
            ));
        }
        let (scene, mut warnings) =
            match manim::select_scene(&args.script, args.scene_name.as_deref()) {
                Ok(s) => s,
                Err(e) => return ManimResult::failure(e),
            };
        if args.preview == Some(true) && args.output_format.is_some_and(|f| f != ManimFormat::Png) {
            warnings
                .push("preview=true renders the last frame as PNG; output_format ignored".into());
        }

        let work = match tempfile::Builder::new().prefix("mcp-manim-").tempdir() {
            Ok(d) => d,
            Err(e) => {
                return ManimResult::failure(format!("Failed to create temp directory: {}", e));
            },
        };
        let script_path = work.path().join("animation.py");
        if let Err(e) = tokio::fs::write(&script_path, &args.script).await {
            return ManimResult::failure(format!("Failed to write script: {}", e));
        }
        let media_dir = work.path().join("media");

        let _permit = self.acquire().await;

        let mut cmd = Command::new(&self.cfg.binaries.manim);
        cmd.args(manim::build_args(
            &script_path,
            &scene,
            format,
            quality,
            &media_dir,
        ))
        .current_dir(work.path())
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .env("PYTHONUNBUFFERED", "1");

        let out = match process::run(cmd, &self.cfg.binaries.manim, self.cfg.manim_timeout).await {
            Ok(o) => o,
            Err(e) => return ManimResult::failure(e.to_string()),
        };
        if !out.status.success() {
            return ManimResult::failure(format!(
                "Manim failed ({}):\n{}",
                out.status,
                truncate_chars(&out.diagnostic_tail(40), 6000)
            ));
        }

        let ext = format.as_str();
        let media = media_dir.clone();
        let scene_for_search = scene.clone();
        let found =
            tokio::task::spawn_blocking(move || manim::find_output(&media, &scene_for_search, ext))
                .await
                .ok()
                .flatten();
        let Some(rendered) = found else {
            return ManimResult::failure(format!(
                "Manim exited successfully but produced no .{} file for scene '{}'. Output:\n{}",
                ext,
                scene,
                truncate_chars(&out.diagnostic_tail(20), 3000)
            ));
        };

        let final_path = self
            .manim_output_dir
            .join(format!("{}.{}", unique_stem(&scene), ext));
        if let Err(e) = tokio::fs::copy(&rendered, &final_path).await {
            return ManimResult::failure(format!("Failed to copy output: {}", e));
        }

        ManimResult {
            success: true,
            error: None,
            output_path: Some(self.paths.to_host_path(&final_path)),
            container_path: Some(final_path.to_string_lossy().into_owned()),
            format: Some(ext.to_string()),
            scene_name: Some(scene),
            quality: Some(quality.as_str().to_string()),
            file_size_kb: Some(file_size_kb(&final_path).await),
            render_time_seconds: Some(round2(start.elapsed().as_secs_f64())),
            warnings: non_empty(warnings),
        }
    }

    // ------------------------------------------------------------------
    // Status
    // ------------------------------------------------------------------

    /// Probe each external tool for availability and version.
    pub async fn dependency_status(&self) -> Vec<DependencyStatus> {
        let b = &self.cfg.binaries;
        let probes: Vec<(&'static str, String, Vec<&'static str>)> = vec![
            ("pdflatex", b.pdflatex.clone(), vec!["--version"]),
            ("latex", b.latex.clone(), vec!["--version"]),
            ("bibtex", b.bibtex.clone(), vec!["--version"]),
            ("dvips", b.dvips.clone(), vec!["--version"]),
            ("pdfinfo", b.pdfinfo.clone(), vec!["-v"]),
            ("pdftoppm", b.pdftoppm.clone(), vec!["-v"]),
            // pdf2svg has no version flag; running it bare prints usage.
            ("pdf2svg", b.pdf2svg.clone(), vec![]),
            ("manim", b.manim.clone(), vec!["--version"]),
        ];

        let mut set = tokio::task::JoinSet::new();
        for (idx, (name, command, args)) in probes.into_iter().enumerate() {
            set.spawn(async move {
                let mut cmd = Command::new(&command);
                cmd.args(&args);
                let status = match process::run(cmd, &command, QUICK_TIMEOUT).await {
                    Ok(out) => DependencyStatus {
                        name,
                        available: true,
                        version: first_nonempty_line(&out.stdout)
                            .or_else(|| first_nonempty_line(&out.stderr)),
                        hint: None,
                        command,
                    },
                    Err(e) => DependencyStatus {
                        name,
                        available: false,
                        version: None,
                        hint: Some(process::install_hint(&command)),
                        command: if matches!(e, CmdError::NotFound { .. }) {
                            command
                        } else {
                            format!("{} ({})", command, e)
                        },
                    },
                };
                (idx, status)
            });
        }
        let mut results: Vec<(usize, DependencyStatus)> = set.join_all().await;
        results.sort_by_key(|(i, _)| *i);
        results.into_iter().map(|(_, s)| s).collect()
    }

    // ------------------------------------------------------------------
    // Internals
    // ------------------------------------------------------------------

    async fn acquire(&self) -> Option<tokio::sync::OwnedSemaphorePermit> {
        // The semaphore is never closed, so this only fails if that changes.
        self.jobs.clone().acquire_owned().await.ok()
    }

    /// Compile `document` in a sandboxed temp dir and copy the result to the
    /// latex output directory.
    async fn run_latex_job(
        &self,
        document: &str,
        source_dir: Option<&Path>,
        format: LatexFormat,
        stem_prefix: &str,
    ) -> Result<LatexOutput, String> {
        let work = tempfile::Builder::new()
            .prefix("mcp-latex-")
            .tempdir()
            .map_err(|e| format!("Failed to create temp directory: {}", e))?;
        let dir = work.path();
        let tex_file = dir.join(format!("{}.tex", JOB_NAME));
        tokio::fs::write(&tex_file, document)
            .await
            .map_err(|e| format!("Failed to write tex file: {}", e))?;
        if let Some(src) = source_dir {
            // `\include{chapters/intro}` writes chapters/intro.aux relative to
            // the working directory, so recreate the (empty) directory layout.
            let (src, dst) = (src.to_path_buf(), dir.to_path_buf());
            let _ = tokio::task::spawn_blocking(move || mirror_subdirs(&src, &dst)).await;
        }

        let compiler = match format {
            LatexFormat::Pdf => &self.cfg.binaries.pdflatex,
            LatexFormat::Dvi | LatexFormat::Ps => &self.cfg.binaries.latex,
        };
        let tex_output = dir.join(format!(
            "{}.{}",
            JOB_NAME,
            if format == LatexFormat::Pdf {
                "pdf"
            } else {
                "dvi"
            }
        ));

        let mut warnings = Vec::new();
        let mut passes = 0;
        let mut bibtex_done = false;
        let summary = loop {
            passes += 1;
            let mut cmd = Command::new(compiler);
            cmd.args(["-interaction=nonstopmode", "-no-shell-escape"])
                .arg(format!("{}.tex", JOB_NAME))
                .current_dir(dir);
            apply_tex_env(&mut cmd, source_dir);
            let out = process::run(cmd, compiler, self.cfg.latex_timeout)
                .await
                .map_err(|e| e.to_string())?;
            debug!("{} pass {} exited with {}", compiler, passes, out.status);

            let log = read_lossy(&dir.join(format!("{}.log", JOB_NAME))).await;
            let summary = latex::parse_log(&log);

            if !tex_output.exists() {
                return Err(describe_failure(
                    &summary,
                    document,
                    &out.diagnostic_tail(15),
                ));
            }
            if passes >= MAX_LATEX_PASSES {
                break summary;
            }

            let mut rerun = summary.needs_rerun;
            if passes == 1 {
                rerun |= latex::needs_toc_pass(document);
                if !bibtex_done {
                    let aux = read_lossy(&dir.join(format!("{}.aux", JOB_NAME))).await;
                    if latex::aux_needs_bibtex(&aux) {
                        bibtex_done = true;
                        rerun = true;
                        if let Some(w) = self.run_bibtex(dir, source_dir).await {
                            warnings.push(w);
                        }
                    }
                }
            }
            if !rerun {
                break summary;
            }
        };

        if summary.wants_biber {
            warnings.push(
                "document uses biblatex with biber, which this server does not run; use backend=bibtex"
                    .to_string(),
            );
        }
        if !summary.errors.is_empty() {
            warnings.push(format!(
                "LaTeX reported errors; output may be incomplete: {}",
                summary.errors.join(" | ")
            ));
        }
        warnings.extend(summary.warnings);

        let produced = if format == LatexFormat::Ps {
            self.run_dvips(dir, &tex_output).await?
        } else {
            tex_output
        };

        let final_path = self.latex_output_dir.join(format!(
            "{}.{}",
            unique_stem(stem_prefix),
            format.extension()
        ));
        tokio::fs::copy(&produced, &final_path)
            .await
            .map_err(|e| format!("Failed to copy output: {}", e))?;

        Ok(LatexOutput {
            path: final_path,
            passes,
            warnings,
        })
    }

    /// Run BibTeX; returns a warning message if it failed.
    async fn run_bibtex(&self, dir: &Path, source_dir: Option<&Path>) -> Option<String> {
        let bibtex = &self.cfg.binaries.bibtex;
        let mut cmd = Command::new(bibtex);
        cmd.arg(JOB_NAME).current_dir(dir);
        apply_tex_env(&mut cmd, source_dir);
        match process::run(cmd, bibtex, self.cfg.latex_timeout).await {
            Ok(out) if out.status.success() => None,
            Ok(out) => Some(format!(
                "bibtex reported problems: {}",
                truncate_chars(&out.diagnostic_tail(5), 800)
            )),
            Err(e) => Some(format!("bibtex could not run: {}", e)),
        }
    }

    /// Convert DVI to PostScript with shell-outs disabled.
    async fn run_dvips(&self, dir: &Path, dvi: &Path) -> Result<PathBuf, String> {
        let dvips = &self.cfg.binaries.dvips;
        let ps = dvi.with_extension("ps");
        let mut cmd = Command::new(dvips);
        cmd.arg("-R2")
            .arg("-q")
            .arg("-o")
            .arg(&ps)
            .arg(dvi)
            .current_dir(dir);
        apply_tex_env(&mut cmd, None);
        let out = process::run(cmd, dvips, self.cfg.latex_timeout)
            .await
            .map_err(|e| e.to_string())?;
        if !out.status.success() || !ps.exists() {
            return Err(format!(
                "dvips failed ({}): {}",
                out.status,
                truncate_chars(&out.diagnostic_tail(10), 2000)
            ));
        }
        Ok(ps)
    }

    /// Page count via `pdfinfo`.
    async fn pdf_page_count(&self, pdf: &Path) -> Result<u32, String> {
        let pdfinfo = &self.cfg.binaries.pdfinfo;
        let mut cmd = Command::new(pdfinfo);
        cmd.arg(pdf);
        let out = process::run(cmd, pdfinfo, QUICK_TIMEOUT)
            .await
            .map_err(|e| e.to_string())?;
        if !out.status.success() {
            return Err(format!(
                "pdfinfo could not read the file (is it a valid PDF?): {}",
                truncate_chars(&out.diagnostic_tail(3), 500)
            ));
        }
        latex::parse_pdfinfo_pages(&out.stdout)
            .ok_or_else(|| "pdfinfo output did not include a page count".to_string())
    }

    /// Export pages to `{preview_dir}/{base}_page{n}.png`. Returns the files
    /// produced and a message for every page that failed.
    async fn export_pages(
        &self,
        pdf: &Path,
        base: &str,
        pages: &[u32],
        dpi: u32,
    ) -> (Vec<PathBuf>, Vec<String>) {
        let pdftoppm = &self.cfg.binaries.pdftoppm;
        let mut produced = Vec::new();
        let mut errors = Vec::new();
        for page in pages {
            let out_base = self
                .preview_output_dir
                .join(format!("{}_page{}", base, page));
            let page_s = page.to_string();
            let mut cmd = Command::new(pdftoppm);
            cmd.args(["-png", "-singlefile", "-f", &page_s, "-l", &page_s, "-r"])
                .arg(dpi.to_string())
                .arg(pdf)
                .arg(&out_base);
            match process::run(cmd, pdftoppm, self.cfg.latex_timeout).await {
                Ok(out) => {
                    let png = out_base.with_extension("png");
                    if out.status.success() && png.exists() {
                        produced.push(png);
                    } else {
                        errors.push(format!(
                            "page {}: pdftoppm failed: {}",
                            page,
                            truncate_chars(&out.diagnostic_tail(3), 300)
                        ));
                    }
                },
                Err(e) => {
                    errors.push(format!("page {}: {}", page, e));
                    if matches!(e, CmdError::NotFound { .. }) {
                        break;
                    }
                },
            }
        }
        (produced, errors)
    }

    /// Convert a single-page PDF to PNG or SVG next to it.
    async fn convert_pdf(
        &self,
        pdf: &Path,
        format: TikzFormat,
        dpi: u32,
    ) -> Result<PathBuf, String> {
        let target = pdf.with_extension(format.as_str());
        let (program, cmd) = match format {
            TikzFormat::Png => {
                let p = &self.cfg.binaries.pdftoppm;
                let mut cmd = Command::new(p);
                cmd.args(["-png", "-singlefile", "-r"])
                    .arg(dpi.to_string())
                    .arg(pdf)
                    .arg(pdf.with_extension(""));
                (p, cmd)
            },
            TikzFormat::Svg => {
                let p = &self.cfg.binaries.pdf2svg;
                let mut cmd = Command::new(p);
                cmd.arg(pdf).arg(&target);
                (p, cmd)
            },
            TikzFormat::Pdf => return Ok(pdf.to_path_buf()),
        };
        let out = process::run(cmd, program, self.cfg.latex_timeout)
            .await
            .map_err(|e| e.to_string())?;
        if !out.status.success() {
            return Err(format!(
                "{} failed: {}",
                program,
                truncate_chars(&out.diagnostic_tail(5), 800)
            ));
        }
        if target.exists() {
            Ok(target)
        } else {
            Err(format!("{} produced no output", program))
        }
    }
}

/// Environment for every TeX-family subprocess (see the module docs).
fn apply_tex_env(cmd: &mut Command, source_dir: Option<&Path>) {
    cmd.env("openin_any", "p")
        .env("openout_any", "p")
        .env("shell_escape", "f")
        // Avoid hard-wrapped log lines so errors/warnings parse cleanly.
        .env("max_print_line", "10000")
        // Paranoid mode would allow writes anywhere under TEXMFOUTPUT.
        .env_remove("TEXMFOUTPUT");
    if let Some(src) = source_dir {
        // Let \input, \includegraphics and \bibliography find files next to the
        // source document. The trailing separator keeps the default search path.
        let sep = if cfg!(windows) { ";" } else { ":" };
        let mut value = OsString::from(src.as_os_str());
        value.push(sep);
        cmd.env("TEXINPUTS", &value).env("BIBINPUTS", &value);
    }
}

/// Build a helpful error message for a LaTeX run that produced no output.
fn describe_failure(summary: &latex::LogSummary, document: &str, tail: &str) -> String {
    let mut msg = if summary.errors.is_empty() {
        let tail = tail.trim();
        if tail.is_empty() {
            "LaTeX compilation failed (no log produced)".to_string()
        } else {
            format!("LaTeX compilation failed:\n{}", truncate_chars(tail, 2000))
        }
    } else {
        format!("LaTeX compilation failed:\n{}", summary.errors.join("\n"))
    };
    if !latex::has_documentclass(document) {
        msg.push_str(
            "\nHint: the content has no \\documentclass; pass template='article' (or report/book/beamer) to wrap a fragment.",
        );
    }
    msg
}

/// Maximum depth of source subdirectories mirrored into the build directory.
const MIRROR_MAX_DEPTH: usize = 3;
/// Maximum number of directories mirrored into the build directory.
const MIRROR_MAX_DIRS: usize = 256;

/// Recreate the directory structure (no files) of `src` under `dst`, skipping
/// hidden and bulky build directories. Returns the number of dirs created.
fn mirror_subdirs(src: &Path, dst: &Path) -> usize {
    let mut created = 0;
    let mut queue = vec![(src.to_path_buf(), dst.to_path_buf(), 0usize)];
    while let Some((from, to, depth)) = queue.pop() {
        if depth >= MIRROR_MAX_DEPTH {
            continue;
        }
        let Ok(entries) = std::fs::read_dir(&from) else {
            continue;
        };
        for entry in entries.flatten() {
            if created >= MIRROR_MAX_DIRS {
                return created;
            }
            let name = entry.file_name();
            let name_s = name.to_string_lossy();
            if name_s.starts_with('.') || matches!(name_s.as_ref(), "node_modules" | "target") {
                continue;
            }
            if entry.file_type().is_ok_and(|t| t.is_dir()) {
                let target = to.join(&name);
                if std::fs::create_dir(&target).is_ok() {
                    created += 1;
                    queue.push((entry.path(), target, depth + 1));
                }
            }
        }
    }
    created
}

fn is_none_spec(spec: &str) -> bool {
    let s = spec.trim();
    s.is_empty() || s.eq_ignore_ascii_case("none")
}

fn clamp_dpi(dpi: u32, warnings: &mut Vec<String>) -> u32 {
    let (lo, hi) = DPI_RANGE;
    let clamped = dpi.clamp(lo, hi);
    if clamped != dpi {
        warnings.push(format!(
            "dpi {} clamped to {} (allowed {}-{})",
            dpi, clamped, lo, hi
        ));
    }
    clamped
}

fn cap_pages(mut pages: Vec<u32>, warnings: &mut Vec<String>) -> Vec<u32> {
    if pages.len() > MAX_PREVIEW_PAGES {
        warnings.push(format!(
            "only the first {} of {} requested pages were rendered",
            MAX_PREVIEW_PAGES,
            pages.len()
        ));
        pages.truncate(MAX_PREVIEW_PAGES);
    }
    pages
}

fn file_stem(path: &Path) -> String {
    sanitize_stem(
        &path
            .file_stem()
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or_default(),
    )
}

async fn file_size_kb(path: &Path) -> f64 {
    tokio::fs::metadata(path)
        .await
        .map(|m| round2(m.len() as f64 / 1024.0))
        .unwrap_or(0.0)
}

async fn read_lossy(path: &Path) -> String {
    tokio::fs::read(path)
        .await
        .map(|b| String::from_utf8_lossy(&b).into_owned())
        .unwrap_or_default()
}

fn first_nonempty_line(s: &str) -> Option<String> {
    s.lines()
        .map(str::trim)
        .find(|l| !l.is_empty())
        .map(|l| truncate_chars(l, 120))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Engine whose external binaries do not exist, so tests are hermetic
    /// regardless of what is installed on the machine.
    fn offline_engine() -> (ContentEngine, tempfile::TempDir, tempfile::TempDir) {
        let project = tempfile::tempdir().unwrap();
        let output = tempfile::tempdir().unwrap();
        let mut cfg = EngineConfig::new(output.path().to_path_buf(), project.path().to_path_buf());
        let missing = |name: &str| format!("/nonexistent-mcp-test-dir/{}", name);
        cfg.binaries = Binaries {
            pdflatex: missing("pdflatex"),
            latex: missing("latex"),
            dvips: missing("dvips"),
            bibtex: missing("bibtex"),
            pdfinfo: missing("pdfinfo"),
            pdftoppm: missing("pdftoppm"),
            pdf2svg: missing("pdf2svg"),
            manim: missing("manim"),
        };
        (ContentEngine::new(cfg), project, output)
    }

    #[test]
    fn creates_output_subdirectories() {
        let (_engine, _p, output) = offline_engine();
        for sub in ["latex", "manim", "previews"] {
            assert!(output.path().join(sub).is_dir(), "{sub} missing");
        }
    }

    #[tokio::test]
    async fn compile_requires_exactly_one_source() {
        let (engine, _p, _o) = offline_engine();
        let r = engine.compile_latex(CompileLatexArgs::default()).await;
        assert!(!r.success);
        assert!(r.error.unwrap().contains("either"));

        let r = engine
            .compile_latex(CompileLatexArgs {
                content: Some("x".into()),
                input_path: Some("a.tex".into()),
                ..Default::default()
            })
            .await;
        assert!(r.error.unwrap().contains("not both"));
    }

    #[tokio::test]
    async fn compile_rejects_paths_outside_project() {
        let (engine, _p, _o) = offline_engine();
        let r = engine
            .compile_latex(CompileLatexArgs {
                input_path: Some("../../../etc/passwd".into()),
                ..Default::default()
            })
            .await;
        assert!(!r.success);
        let err = r.error.unwrap();
        assert!(
            err.contains("not found") || err.contains("access denied"),
            "{err}"
        );
    }

    #[tokio::test]
    async fn compile_rejects_empty_and_oversized_content() {
        let (engine, _p, _o) = offline_engine();
        let r = engine
            .compile_latex(CompileLatexArgs {
                content: Some("   ".into()),
                ..Default::default()
            })
            .await;
        assert!(r.error.unwrap().contains("empty"));

        let r = engine
            .compile_latex(CompileLatexArgs {
                content: Some("x".repeat(MAX_LATEX_BYTES + 1)),
                ..Default::default()
            })
            .await;
        assert!(r.error.unwrap().contains("larger"));
    }

    #[tokio::test]
    async fn compile_reports_missing_latex_clearly() {
        let (engine, _p, _o) = offline_engine();
        let r = engine
            .compile_latex(CompileLatexArgs {
                content: Some("\\documentclass{article}\\begin{document}x\\end{document}".into()),
                ..Default::default()
            })
            .await;
        assert!(!r.success);
        let err = r.error.unwrap();
        assert!(err.contains("not found on PATH"), "{err}");
    }

    #[tokio::test]
    async fn compile_from_file_reaches_compiler() {
        let (engine, project, _o) = offline_engine();
        std::fs::write(project.path().join("paper.tex"), "\\documentclass{article}").unwrap();
        let r = engine
            .compile_latex(CompileLatexArgs {
                input_path: Some("paper.tex".into()),
                ..Default::default()
            })
            .await;
        // The file resolved; failure comes from the (missing) compiler.
        assert!(r.error.unwrap().contains("not found on PATH"));
    }

    #[tokio::test]
    async fn tikz_rejects_bad_library_names_before_compiling() {
        let (engine, _p, _o) = offline_engine();
        let r = engine
            .render_tikz(RenderTikzArgs {
                tikz_code: "\\draw (0,0) -- (1,1);".into(),
                tikz_libraries: Some(vec!["calc}\\input{/etc/passwd".into()]),
                ..Default::default()
            })
            .await;
        assert!(r.error.unwrap().contains("invalid package/library name"));
    }

    #[tokio::test]
    async fn preview_rejects_missing_file() {
        let (engine, _p, _o) = offline_engine();
        let r = engine
            .preview_pdf(PreviewPdfArgs {
                pdf_path: "missing.pdf".into(),
                ..Default::default()
            })
            .await;
        assert!(r.error.unwrap().contains("not found"));
    }

    #[tokio::test]
    async fn preview_reports_missing_pdfinfo() {
        let (engine, project, _o) = offline_engine();
        std::fs::write(project.path().join("doc.pdf"), "%PDF-1.4").unwrap();
        let r = engine
            .preview_pdf(PreviewPdfArgs {
                pdf_path: "doc.pdf".into(),
                ..Default::default()
            })
            .await;
        let err = r.error.unwrap();
        assert!(err.contains("poppler-utils"), "{err}");
    }

    #[tokio::test]
    async fn manim_validates_script_before_running() {
        let (engine, _p, _o) = offline_engine();
        let r = engine
            .create_manim_animation(ManimArgs {
                script: "print('no scene here')".into(),
                ..Default::default()
            })
            .await;
        assert!(r.error.unwrap().contains("no Scene subclass"));
    }

    #[tokio::test]
    async fn manim_reports_missing_binary() {
        let (engine, _p, _o) = offline_engine();
        let r = engine
            .create_manim_animation(ManimArgs {
                script: "from manim import *\nclass A(Scene):\n    pass\n".into(),
                ..Default::default()
            })
            .await;
        assert!(r.error.unwrap().contains("pip install manim"));
    }

    #[tokio::test]
    async fn dependency_status_lists_all_tools() {
        let (engine, _p, _o) = offline_engine();
        let deps = engine.dependency_status().await;
        assert_eq!(deps.len(), 8);
        assert_eq!(deps[0].name, "pdflatex");
        assert!(deps.iter().all(|d| !d.available && d.hint.is_some()));
    }

    #[test]
    fn dpi_is_clamped_with_warning() {
        let mut w = Vec::new();
        assert_eq!(clamp_dpi(150, &mut w), 150);
        assert!(w.is_empty());
        assert_eq!(clamp_dpi(5000, &mut w), 600);
        assert_eq!(clamp_dpi(1, &mut w), 36);
        assert_eq!(w.len(), 2);
    }

    #[test]
    fn mirror_subdirs_copies_layout_only() {
        let src = tempfile::tempdir().unwrap();
        let dst = tempfile::tempdir().unwrap();
        std::fs::create_dir_all(src.path().join("chapters/part1/deep/deeper")).unwrap();
        std::fs::create_dir_all(src.path().join(".git/objects")).unwrap();
        std::fs::create_dir_all(src.path().join("node_modules/x")).unwrap();
        std::fs::write(src.path().join("chapters/intro.tex"), "x").unwrap();

        let created = mirror_subdirs(src.path(), dst.path());
        assert_eq!(created, 3);
        assert!(dst.path().join("chapters/part1/deep").is_dir());
        assert!(!dst.path().join("chapters/part1/deep/deeper").exists());
        assert!(!dst.path().join("chapters/intro.tex").exists());
        assert!(!dst.path().join(".git").exists());
        assert!(!dst.path().join("node_modules").exists());
    }

    #[test]
    fn pages_are_capped() {
        let mut w = Vec::new();
        let pages = cap_pages((1..=80).collect(), &mut w);
        assert_eq!(pages.len(), MAX_PREVIEW_PAGES);
        assert_eq!(w.len(), 1);
    }

    #[test]
    fn failure_message_hints_at_templates() {
        let s = latex::LogSummary {
            errors: vec!["Missing \\begin{document}.".into()],
            ..Default::default()
        };
        let msg = describe_failure(&s, "Hello", "");
        assert!(msg.contains("Missing \\begin{document}"));
        assert!(msg.contains("template='article'"));
        let msg = describe_failure(&s, "\\documentclass{article}", "");
        assert!(!msg.contains("Hint"));
    }
}
