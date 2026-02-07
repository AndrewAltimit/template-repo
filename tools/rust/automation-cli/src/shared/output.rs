use owo_colors::OwoColorize;

/// Print a section header
pub fn header(text: &str) {
    eprintln!("{}", format!("=== {text} ===").cyan());
}

/// Print a sub-section header
pub fn subheader(text: &str) {
    eprintln!("{}", format!("--- {text} ---").blue());
}

/// Print a success message
pub fn success(text: &str) {
    eprintln!("{} {text}", "OK".green().bold());
}

/// Print a failure message
pub fn fail(text: &str) {
    eprintln!("{} {text}", "FAIL".red().bold());
}

/// Print a warning message
pub fn warn(text: &str) {
    eprintln!("{} {text}", "WARN".yellow().bold());
}

/// Print an info message
pub fn info(text: &str) {
    eprintln!("  {text}");
}

/// Print a step indicator (e.g., "Building Python CI image...")
pub fn step(text: &str) {
    eprintln!("{text}");
}
