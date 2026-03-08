use owo_colors::OwoColorize;

/// Print a section header.
pub fn header(text: &str) {
    eprintln!("{}", format!("=== {text} ===").cyan());
}

/// Print a sub-section header.
pub fn subheader(text: &str) {
    eprintln!("{}", format!("--- {text} ---").blue());
}

/// Print a success message.
pub fn success(text: &str) {
    eprintln!("{} {text}", "[+]".green().bold());
}

/// Print a failure message.
pub fn fail(text: &str) {
    eprintln!("{} {text}", "[-]".red().bold());
}

/// Print a warning message.
pub fn warn(text: &str) {
    eprintln!("{} {text}", "[!]".yellow().bold());
}

/// Print an info/status message.
pub fn info(text: &str) {
    eprintln!("{} {text}", "[*]".cyan());
}

/// Print an indented detail line.
pub fn detail(text: &str) {
    eprintln!("    {text}");
}
