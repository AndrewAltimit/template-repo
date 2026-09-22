//! Dependency-free fuzz-style test: every parser must survive arbitrary input.

use code_parser::CodeParser;

/// Fragments that exercise fence, diff, edit, and path edge cases.
const TOKENS: &[&str] = &[
    "```",
    "````",
    "~~~",
    "```rust src/a.rs",
    "```markdown",
    "```diff",
    "\n",
    "\r\n",
    "\r",
    " ",
    "    ",
    "--- a/x.rs",
    "+++ b/x.rs",
    "--- /dev/null",
    "+++ /dev/null",
    "@@ -1,2 +1,3 @@",
    "@@ -99999999999999999999999,1 +0 @@",
    "@@",
    "+",
    "-",
    "\\ No newline at end of file",
    "<<<<<<< SEARCH",
    "=======",
    ">>>>>>> REPLACE",
    "File: `../../etc/passwd`",
    "Create `src/main.rs`:",
    "# file: a.py",
    "In file `x.py`, change `a` to `b`",
    "\u{00e9}",
    "\u{4e2d}\u{6587}",
    "\u{1f600}",
    "`",
    "x",
    ":",
    "\0",
];

/// Tiny xorshift PRNG so the test is deterministic and needs no dependencies.
struct Rng(u64);

impl Rng {
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0
    }

    fn below(&mut self, n: usize) -> usize {
        (self.next() % n as u64) as usize
    }
}

#[test]
fn parsers_never_panic_on_random_input() {
    let mut rng = Rng(0x9e37_79b9_7f4a_7c15);
    for _ in 0..3000 {
        let len = rng.below(60);
        let mut input = String::new();
        for _ in 0..len {
            input.push_str(TOKENS[rng.below(TOKENS.len())]);
            if rng.below(3) == 0 {
                input.push('\n');
            }
        }

        let blocks = CodeParser::extract_code_blocks(&input);
        for b in &blocks {
            let _ = b.is_diff();
            if let Some(f) = &b.filename {
                let _ = CodeParser::sanitize_filename(f);
                let _ = CodeParser::infer_language(f);
            }
        }
        for e in CodeParser::parse_edit_instructions(&input) {
            let _ = CodeParser::apply_edit(&input, &e);
        }
        if let Ok(patches) = CodeParser::parse_unified_diff(&input) {
            for p in patches {
                let _ = p.apply(&input);
                let _ = p.apply("");
            }
        }
        let _ = CodeParser::extract_patches(&input);
        let _ = CodeParser::sanitize_filename(&input);
    }
}
