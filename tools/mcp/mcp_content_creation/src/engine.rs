//! Content creation engine - LaTeX compilation, PDF utilities, Manim animations.

use regex::Regex;
use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::Instant;
use tempfile::TempDir;
use tokio::process::Command;
use tracing::{debug, error, info, warn};

use crate::types::{
    CompileResult, LatexTemplate, ManimFormat, ManimResult, OutputFormat, PreviewResult,
    ResponseMode,
};

/// Preview DPI settings
pub const PREVIEW_DPI_STANDARD: u32 = 150;
pub const PREVIEW_DPI_HIGH: u32 = 300;

/// Container to host path mappings
const CONTAINER_MAPPINGS: &[(&str, &str)] = &[
    ("/app/output", "outputs/mcp-content"),
    ("/output", "outputs/mcp-content"),
    ("/app", "."),
];

/// Content creation engine
pub struct ContentEngine {
    output_dir: PathBuf,
    manim_output_dir: PathBuf,
    latex_output_dir: PathBuf,
    preview_output_dir: PathBuf,
    project_root: PathBuf,
}

impl ContentEngine {
    /// Create a new content engine
    pub fn new(output_dir: PathBuf, project_root: PathBuf) -> Self {
        let manim_output_dir = output_dir.join("manim");
        let latex_output_dir = output_dir.join("latex");
        let preview_output_dir = output_dir.join("previews");

        // Create directories
        for dir in [&manim_output_dir, &latex_output_dir, &preview_output_dir] {
            if let Err(e) = fs::create_dir_all(dir) {
                warn!("Failed to create directory {}: {}", dir.display(), e);
            }
        }

        info!(
            "Content engine initialized with output_dir: {}",
            output_dir.display()
        );

        Self {
            output_dir,
            manim_output_dir,
            latex_output_dir,
            preview_output_dir,
            project_root,
        }
    }

    /// Convert container path to host-relative path
    pub fn container_to_host_path(&self, container_path: &str) -> String {
        for (container_prefix, host_prefix) in CONTAINER_MAPPINGS {
            if container_path.starts_with(container_prefix) {
                let relative = container_path
                    .strip_prefix(container_prefix)
                    .unwrap_or("")
                    .trim_start_matches('/');
                if *host_prefix == "." {
                    return relative.to_string();
                }
                return format!("{}/{}", host_prefix, relative);
            }
        }
        container_path.to_string()
    }

    /// Resolve input path relative to project root with security checks
    pub fn resolve_input_path(&self, input_path: &str) -> Result<PathBuf, String> {
        let path = Path::new(input_path);

        #[allow(clippy::collapsible_if)]
        if path.is_absolute() {
            // Check if this is a host path that should be converted
            if let Ok(host_root) = std::env::var("MCP_HOST_PROJECT_ROOT") {
                if input_path.starts_with(&host_root) {
                    let relative = input_path
                        .strip_prefix(&host_root)
                        .unwrap_or("")
                        .trim_start_matches(std::path::MAIN_SEPARATOR);
                    return Ok(self.project_root.join(relative));
                }
            }
            // For other absolute paths, just normalize
            return Ok(PathBuf::from(input_path));
        }

        // For relative paths, resolve relative to project root
        let resolved = self.project_root.join(input_path);
        let resolved = resolved.canonicalize().unwrap_or(resolved);

        // Security check: ensure path stays within project root
        let project_root_canonical = self
            .project_root
            .canonicalize()
            .unwrap_or_else(|_| self.project_root.clone());

        if !resolved.starts_with(&project_root_canonical) {
            return Err(format!(
                "Path traversal detected: '{}' resolves outside project root",
                input_path
            ));
        }

        Ok(resolved)
    }

    /// Get PDF page count using pdfinfo
    pub async fn get_pdf_page_count(&self, pdf_path: &Path) -> i32 {
        let output = Command::new("pdfinfo")
            .arg(pdf_path)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .await;

        match output {
            Ok(out) if out.status.success() => {
                let stdout = String::from_utf8_lossy(&out.stdout);
                #[allow(clippy::collapsible_if)]
                for line in stdout.lines() {
                    if line.starts_with("Pages:") {
                        if let Some(count) = line.split(':').nth(1) {
                            if let Ok(n) = count.trim().parse() {
                                return n;
                            }
                        }
                    }
                }
                0
            },
            _ => 0,
        }
    }

    /// Get file size in KB
    pub fn get_file_size_kb(&self, path: &Path) -> f64 {
        fs::metadata(path)
            .map(|m| m.len() as f64 / 1024.0)
            .unwrap_or(0.0)
    }

    /// Parse page specification string
    pub fn parse_page_spec(&self, spec: &str, total_pages: i32) -> Vec<i32> {
        if spec.is_empty() || spec.to_lowercase() == "none" {
            return vec![];
        }

        if spec.to_lowercase() == "all" {
            return (1..=total_pages).collect();
        }

        let mut pages: HashSet<i32> = HashSet::new();

        #[allow(clippy::collapsible_if)]
        for part in spec.split(',') {
            let part = part.trim();
            if part.contains('-') {
                // Range: "1-5"
                let parts: Vec<&str> = part.split('-').collect();
                if parts.len() == 2 {
                    if let (Ok(start), Ok(end)) = (
                        parts[0].trim().parse::<i32>(),
                        parts[1].trim().parse::<i32>(),
                    ) {
                        let start = start.max(1);
                        let end = end.min(total_pages);
                        for p in start..=end {
                            pages.insert(p);
                        }
                    }
                }
            } else if let Ok(page) = part.parse::<i32>() {
                if page >= 1 && page <= total_pages {
                    pages.insert(page);
                }
            }
        }

        let mut result: Vec<i32> = pages.into_iter().collect();
        result.sort();
        result
    }

    /// Export PDF pages to PNG files
    pub async fn export_pages_to_png(
        &self,
        pdf_path: &Path,
        pages: &[i32],
        dpi: u32,
    ) -> Vec<PathBuf> {
        let base_name = pdf_path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("document");

        let mut png_paths = Vec::new();

        for page in pages {
            let output_base = self
                .preview_output_dir
                .join(format!("{}_page{}", base_name, page));

            let result = Command::new("pdftoppm")
                .args([
                    "-png",
                    "-f",
                    &page.to_string(),
                    "-l",
                    &page.to_string(),
                    "-r",
                    &dpi.to_string(),
                    "-singlefile",
                ])
                .arg(pdf_path)
                .arg(&output_base)
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .output()
                .await;

            match result {
                Ok(out) if out.status.success() => {
                    let png_path = output_base.with_extension("png");
                    if png_path.exists() {
                        png_paths.push(png_path);
                    }
                },
                Ok(out) => {
                    warn!(
                        "Failed to export page {}: {}",
                        page,
                        String::from_utf8_lossy(&out.stderr)
                    );
                },
                Err(e) => {
                    warn!("Failed to run pdftoppm for page {}: {}", page, e);
                },
            }
        }

        png_paths
    }

    /// Wrap content with LaTeX template if needed
    pub fn wrap_content_with_template(&self, content: &str, template: LatexTemplate) -> String {
        if content.contains("\\documentclass") {
            return content.to_string();
        }
        template.wrap_content(content)
    }

    /// Extract error from LaTeX log file
    pub fn extract_latex_error(&self, log_path: &Path) -> String {
        if !log_path.exists() {
            return "Compilation failed".to_string();
        }

        match fs::read_to_string(log_path) {
            Ok(content) => {
                let errors: Vec<&str> = content
                    .lines()
                    .filter(|line| line.starts_with("!"))
                    .take(5)
                    .collect();
                if errors.is_empty() {
                    "Compilation failed".to_string()
                } else {
                    errors.join("\n")
                }
            },
            Err(_) => "Compilation failed".to_string(),
        }
    }

    /// Run LaTeX compilation
    async fn run_latex_compilation(
        &self,
        compiler: &str,
        tex_file: &Path,
        working_dir: &Path,
        output_format: OutputFormat,
    ) -> Option<PathBuf> {
        let cmd_args = ["-interaction=nonstopmode", "-no-shell-escape"];

        // Run compilation twice for references
        for pass in 0..2 {
            let result = Command::new(compiler)
                .args(cmd_args)
                .arg(tex_file.file_name().unwrap())
                .current_dir(working_dir)
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .output()
                .await;

            match result {
                Ok(out) => {
                    if !out.status.success() && pass == 0 {
                        debug!(
                            "First compilation pass had warnings/errors (often normal): {}",
                            String::from_utf8_lossy(&out.stderr)
                        );
                    }
                },
                Err(e) => {
                    error!("Failed to run {}: {}", compiler, e);
                    return None;
                },
            }
        }

        // Handle PS output (requires dvips)
        if output_format == OutputFormat::Ps {
            let dvi_file = tex_file.with_extension("dvi");
            let ps_file = tex_file.with_extension("ps");

            let _ = Command::new("dvips")
                .arg(&dvi_file)
                .arg("-o")
                .arg(&ps_file)
                .current_dir(working_dir)
                .output()
                .await;
        }

        let output_file = tex_file.with_extension(output_format.as_str());
        if output_file.exists() {
            Some(output_file)
        } else {
            None
        }
    }

    /// Convert PDF to PNG or SVG
    async fn convert_pdf_to_image(
        &self,
        pdf_path: &Path,
        output_format: OutputFormat,
    ) -> Result<PathBuf, String> {
        let base_name = pdf_path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("document");
        let output_path =
            self.latex_output_dir
                .join(format!("{}.{}", base_name, output_format.as_str()));

        match output_format {
            OutputFormat::Png => {
                let output_base = output_path.with_extension("");
                let result = Command::new("pdftoppm")
                    .args(["-png", "-singlefile", "-r", &PREVIEW_DPI_HIGH.to_string()])
                    .arg(pdf_path)
                    .arg(&output_base)
                    .output()
                    .await
                    .map_err(|e| format!("Failed to run pdftoppm: {}", e))?;

                if !result.status.success() {
                    return Err(format!(
                        "pdftoppm failed: {}",
                        String::from_utf8_lossy(&result.stderr)
                    ));
                }
            },
            OutputFormat::Svg => {
                let result = Command::new("pdf2svg")
                    .arg(pdf_path)
                    .arg(&output_path)
                    .output()
                    .await
                    .map_err(|e| format!("Failed to run pdf2svg: {}", e))?;

                if !result.status.success() {
                    return Err(format!(
                        "pdf2svg failed: {}",
                        String::from_utf8_lossy(&result.stderr)
                    ));
                }
            },
            _ => {
                return Err(format!(
                    "Unsupported conversion format: {:?}",
                    output_format
                ));
            },
        }

        if output_path.exists() {
            Ok(output_path)
        } else {
            Err("Conversion produced no output".to_string())
        }
    }

    /// Compile LaTeX document
    #[allow(clippy::too_many_arguments)]
    pub async fn compile_latex(
        &self,
        content: Option<&str>,
        input_path: Option<&str>,
        output_format: OutputFormat,
        template: LatexTemplate,
        response_mode: ResponseMode,
        preview_pages: &str,
        preview_dpi: u32,
    ) -> CompileResult {
        let start_time = Instant::now();

        // Validate inputs
        if content.is_none() && input_path.is_none() {
            return CompileResult {
                success: false,
                error: Some("Must provide either 'content' or 'input_path'".to_string()),
                ..Default::default()
            };
        }

        if content.is_some() && input_path.is_some() {
            return CompileResult {
                success: false,
                error: Some("Provide only one of 'content' or 'input_path', not both".to_string()),
                ..Default::default()
            };
        }

        // Get content from file or parameter
        let (latex_content, source_dir) = if let Some(path) = input_path {
            match self.resolve_input_path(path) {
                Ok(resolved) => {
                    if !resolved.exists() {
                        return CompileResult {
                            success: false,
                            error: Some(format!("Input file not found: {}", path)),
                            ..Default::default()
                        };
                    }
                    match fs::read_to_string(&resolved) {
                        Ok(c) => (c, resolved.parent().map(|p| p.to_path_buf())),
                        Err(e) => {
                            return CompileResult {
                                success: false,
                                error: Some(format!("Failed to read input file: {}", e)),
                                ..Default::default()
                            };
                        },
                    }
                },
                Err(e) => {
                    return CompileResult {
                        success: false,
                        error: Some(e),
                        ..Default::default()
                    };
                },
            }
        } else {
            (content.unwrap().to_string(), None)
        };

        let compiler = if output_format == OutputFormat::Pdf {
            "pdflatex"
        } else {
            "latex"
        };

        // Wrap content with template
        let latex_content = self.wrap_content_with_template(&latex_content, template);

        // Create temp directory for compilation
        let temp_dir = match TempDir::new() {
            Ok(d) => d,
            Err(e) => {
                return CompileResult {
                    success: false,
                    error: Some(format!("Failed to create temp directory: {}", e)),
                    ..Default::default()
                };
            },
        };

        let tex_file = temp_dir.path().join("document.tex");
        let mut symlink_warnings = Vec::new();

        // Symlink source directory contents if compiling from file
        #[allow(clippy::collapsible_if)]
        if let Some(source) = &source_dir {
            if let Ok(entries) = fs::read_dir(source) {
                for entry in entries.flatten() {
                    let src = entry.path();
                    let dst = temp_dir.path().join(entry.file_name());
                    if !dst.exists() {
                        #[cfg(unix)]
                        if let Err(e) = std::os::unix::fs::symlink(&src, &dst) {
                            symlink_warnings.push(format!(
                                "{}: {}",
                                entry.file_name().to_string_lossy(),
                                e
                            ));
                        }
                        #[cfg(windows)]
                        if src.is_dir() {
                            if let Err(e) = std::os::windows::fs::symlink_dir(&src, &dst) {
                                symlink_warnings.push(format!(
                                    "{}: {}",
                                    entry.file_name().to_string_lossy(),
                                    e
                                ));
                            }
                        } else if let Err(e) = std::os::windows::fs::symlink_file(&src, &dst) {
                            symlink_warnings.push(format!(
                                "{}: {}",
                                entry.file_name().to_string_lossy(),
                                e
                            ));
                        }
                    }
                }
            }
        }

        // Write LaTeX content
        if let Err(e) = fs::write(&tex_file, &latex_content) {
            return CompileResult {
                success: false,
                error: Some(format!("Failed to write tex file: {}", e)),
                ..Default::default()
            };
        }

        // Run compilation
        let output_file = self
            .run_latex_compilation(compiler, &tex_file, temp_dir.path(), output_format)
            .await;

        let output_file = match output_file {
            Some(f) => f,
            None => {
                let log_file = tex_file.with_extension("log");
                return CompileResult {
                    success: false,
                    error: Some(self.extract_latex_error(&log_file)),
                    ..Default::default()
                };
            },
        };

        // Copy to output directory
        let timestamp = chrono::Utc::now().timestamp();
        let output_name = format!(
            "document_{}_{}.{}",
            timestamp,
            std::process::id(),
            output_format.as_str()
        );
        let final_output = self.latex_output_dir.join(&output_name);

        if let Err(e) = fs::copy(&output_file, &final_output) {
            return CompileResult {
                success: false,
                error: Some(format!("Failed to copy output: {}", e)),
                ..Default::default()
            };
        }

        // Get metadata
        let page_count = if output_format == OutputFormat::Pdf {
            self.get_pdf_page_count(&final_output).await
        } else {
            0
        };
        let file_size_kb = self.get_file_size_kb(&final_output);
        let compile_time = start_time.elapsed().as_secs_f64();

        // Generate previews if requested
        let preview_paths = if output_format == OutputFormat::Pdf && preview_pages != "none" {
            let pages = self.parse_page_spec(preview_pages, page_count);
            if !pages.is_empty() {
                let paths = self
                    .export_pages_to_png(&final_output, &pages, preview_dpi)
                    .await;
                Some(
                    paths
                        .iter()
                        .map(|p| self.container_to_host_path(&p.to_string_lossy()))
                        .collect(),
                )
            } else {
                None
            }
        } else {
            None
        };

        // Build result
        let host_path = self.container_to_host_path(&final_output.to_string_lossy());

        let mut result = CompileResult {
            success: true,
            output_path: Some(host_path),
            container_path: Some(final_output.to_string_lossy().to_string()),
            page_count: Some(page_count),
            file_size_kb: Some((file_size_kb * 100.0).round() / 100.0),
            ..Default::default()
        };

        if !symlink_warnings.is_empty() {
            result.warnings = Some(vec![format!(
                "Failed to symlink files for relative includes: {}. If your document has \\include, \\input, or image references, they may not resolve correctly.",
                symlink_warnings.join(", ")
            )]);
        }

        if response_mode == ResponseMode::Standard {
            result.format = Some(output_format.as_str().to_string());
            result.compile_time_seconds = Some((compile_time * 100.0).round() / 100.0);
            result.preview_paths = preview_paths;
        }

        result
    }

    /// Render TikZ diagram
    pub async fn render_tikz(
        &self,
        tikz_code: &str,
        output_format: OutputFormat,
        response_mode: ResponseMode,
    ) -> CompileResult {
        // Wrap TikZ code in standalone document
        let latex_content = format!(
            r#"\documentclass[tikz,border=10pt]{{standalone}}
\usepackage{{tikz}}
\usetikzlibrary{{arrows.meta,positioning,shapes,calc}}
\begin{{document}}
{}
\end{{document}}"#,
            tikz_code
        );

        // Compile to PDF first
        let pdf_result = self
            .compile_latex(
                Some(&latex_content),
                None,
                OutputFormat::Pdf,
                LatexTemplate::Custom,
                ResponseMode::Minimal,
                "none",
                PREVIEW_DPI_STANDARD,
            )
            .await;

        if !pdf_result.success {
            return pdf_result;
        }

        let pdf_path = pdf_result.container_path.as_ref().unwrap();

        // Convert to requested format if needed
        if output_format != OutputFormat::Pdf {
            match self
                .convert_pdf_to_image(Path::new(pdf_path), output_format)
                .await
            {
                Ok(output_path) => {
                    let host_path = self.container_to_host_path(&output_path.to_string_lossy());
                    let mut result = CompileResult {
                        success: true,
                        output_path: Some(host_path),
                        container_path: Some(output_path.to_string_lossy().to_string()),
                        ..Default::default()
                    };
                    if response_mode == ResponseMode::Standard {
                        result.format = Some(output_format.as_str().to_string());
                    }
                    result
                },
                Err(e) => CompileResult {
                    success: false,
                    error: Some(format!("Format conversion error: {}", e)),
                    ..Default::default()
                },
            }
        } else {
            // Return PDF result
            let mut result = CompileResult {
                success: true,
                output_path: pdf_result.output_path,
                container_path: pdf_result.container_path,
                page_count: Some(1),
                file_size_kb: pdf_result.file_size_kb,
                ..Default::default()
            };
            if response_mode == ResponseMode::Standard {
                result.format = Some("pdf".to_string());
            }
            result
        }
    }

    /// Preview PDF pages
    pub async fn preview_pdf(
        &self,
        pdf_path: &str,
        pages: &str,
        dpi: u32,
        response_mode: ResponseMode,
    ) -> PreviewResult {
        // Resolve path
        let resolved = match self.resolve_input_path(pdf_path) {
            Ok(p) => p,
            Err(e) => {
                return PreviewResult {
                    success: false,
                    error: Some(e),
                    ..Default::default()
                };
            },
        };

        if !resolved.exists() {
            return PreviewResult {
                success: false,
                error: Some(format!("PDF file not found: {}", pdf_path)),
                ..Default::default()
            };
        }

        // Get page count
        let page_count = self.get_pdf_page_count(&resolved).await;
        if page_count == 0 {
            return PreviewResult {
                success: false,
                error: Some("Could not determine PDF page count".to_string()),
                ..Default::default()
            };
        }

        // Parse pages
        let pages_to_export = self.parse_page_spec(pages, page_count);
        if pages_to_export.is_empty() {
            return PreviewResult {
                success: false,
                error: Some(format!("No valid pages in specification: {}", pages)),
                ..Default::default()
            };
        }

        // Export pages
        let preview_paths = self
            .export_pages_to_png(&resolved, &pages_to_export, dpi)
            .await;

        if preview_paths.is_empty() {
            return PreviewResult {
                success: false,
                error: Some("Failed to generate previews".to_string()),
                ..Default::default()
            };
        }

        let host_paths: Vec<String> = preview_paths
            .iter()
            .map(|p| self.container_to_host_path(&p.to_string_lossy()))
            .collect();

        let mut result = PreviewResult {
            success: true,
            preview_paths: Some(host_paths),
            ..Default::default()
        };

        if response_mode == ResponseMode::Standard {
            result.pdf_path = Some(self.container_to_host_path(&resolved.to_string_lossy()));
            result.page_count = Some(page_count);
            result.pages_exported = Some(pages_to_export);
        }

        result
    }

    /// Create Manim animation
    pub async fn create_manim_animation(
        &self,
        script: &str,
        output_format: ManimFormat,
    ) -> ManimResult {
        // Create temp file for script
        let temp_dir = match TempDir::new() {
            Ok(d) => d,
            Err(e) => {
                return ManimResult {
                    success: false,
                    error: Some(format!("Failed to create temp directory: {}", e)),
                    ..Default::default()
                };
            },
        };

        let script_path = temp_dir.path().join("animation.py");
        if let Err(e) = fs::write(&script_path, script) {
            return ManimResult {
                success: false,
                error: Some(format!("Failed to write script: {}", e)),
                ..Default::default()
            };
        }

        // Extract class name from script
        let class_regex = Regex::new(r"class\s+(\w+)\s*\(").unwrap();
        let class_name = class_regex
            .captures(script)
            .and_then(|c| c.get(1))
            .map(|m| m.as_str().to_string());

        // Build command
        let mut cmd = Command::new("manim");
        cmd.args(["-pql", "--media_dir"])
            .arg(&self.manim_output_dir)
            .arg(&script_path);

        if let Some(name) = &class_name {
            cmd.arg(name);
        }

        let result = cmd
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .await;

        match result {
            Ok(out) => {
                if !out.status.success() {
                    return ManimResult {
                        success: false,
                        error: Some(format!(
                            "Manim execution failed: {}",
                            String::from_utf8_lossy(&out.stderr)
                        )),
                        ..Default::default()
                    };
                }

                // Find output file
                let ext = output_format.as_str();
                let mut output_file = None;

                if let Ok(entries) = walkdir(&self.manim_output_dir) {
                    for entry in entries {
                        if entry.extension().and_then(|e| e.to_str()) == Some(ext) {
                            output_file = Some(entry);
                            break;
                        }
                    }
                }

                ManimResult {
                    success: true,
                    output_path: output_file.map(|p| p.to_string_lossy().to_string()),
                    format: Some(ext.to_string()),
                    error: None,
                }
            },
            Err(e) => {
                if e.kind() == std::io::ErrorKind::NotFound {
                    ManimResult {
                        success: false,
                        error: Some("Manim not found. Please install it first.".to_string()),
                        ..Default::default()
                    }
                } else {
                    ManimResult {
                        success: false,
                        error: Some(format!("Manim error: {}", e)),
                        ..Default::default()
                    }
                }
            },
        }
    }

    /// Get output directory
    #[allow(dead_code)]
    pub fn output_dir(&self) -> &Path {
        &self.output_dir
    }
}

/// Walk directory recursively
fn walkdir(path: &Path) -> std::io::Result<Vec<PathBuf>> {
    let mut results = Vec::new();

    if path.is_dir() {
        for entry in fs::read_dir(path)? {
            let entry = entry?;
            let path = entry.path();
            if path.is_dir() {
                results.extend(walkdir(&path)?);
            } else {
                results.push(path);
            }
        }
    }

    Ok(results)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_page_spec() {
        let engine = ContentEngine::new(PathBuf::from("/tmp"), PathBuf::from("/app"));

        assert_eq!(engine.parse_page_spec("1", 10), vec![1]);
        assert_eq!(engine.parse_page_spec("1,3,5", 10), vec![1, 3, 5]);
        assert_eq!(engine.parse_page_spec("1-5", 10), vec![1, 2, 3, 4, 5]);
        assert_eq!(engine.parse_page_spec("all", 3), vec![1, 2, 3]);
        assert_eq!(engine.parse_page_spec("none", 10), Vec::<i32>::new());
    }

    #[test]
    fn test_container_to_host_path() {
        let engine = ContentEngine::new(PathBuf::from("/tmp"), PathBuf::from("/app"));

        assert_eq!(
            engine.container_to_host_path("/app/output/latex/doc.pdf"),
            "outputs/mcp-content/latex/doc.pdf"
        );
        assert_eq!(
            engine.container_to_host_path("/output/test.pdf"),
            "outputs/mcp-content/test.pdf"
        );
        assert_eq!(engine.container_to_host_path("/app/file.tex"), "file.tex");
    }
}
