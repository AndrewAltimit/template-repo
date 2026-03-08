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

#[cfg(test)]
mod tests {
    use super::*;

    // These functions write to stderr, so we just verify they don't panic.

    #[test]
    fn header_no_panic() {
        header("Test Header");
    }

    #[test]
    fn subheader_no_panic() {
        subheader("Test Subheader");
    }

    #[test]
    fn success_no_panic() {
        success("operation succeeded");
    }

    #[test]
    fn fail_no_panic() {
        fail("operation failed");
    }

    #[test]
    fn warn_no_panic() {
        warn("something is off");
    }

    #[test]
    fn info_no_panic() {
        info("status update");
    }

    #[test]
    fn detail_no_panic() {
        detail("  extra info");
    }

    #[test]
    fn all_functions_with_empty_string() {
        header("");
        subheader("");
        success("");
        fail("");
        warn("");
        info("");
        detail("");
    }
}
