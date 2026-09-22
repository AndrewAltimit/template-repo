I'll add a config loader and wire it into the CLI.

### `src/config.rs`

```rust
use std::path::Path;

pub fn load(path: &Path) -> std::io::Result<String> {
    std::fs::read_to_string(path)
}
```

Next, update the existing `src/main.rs`:

```rust
mod config;

fn main() {
    let cfg = config::load("app.toml".as_ref()).unwrap();
    println!("{cfg}");
}
```

Run it with:

```bash
cargo run
```

1. And add the default config:

   ```toml app.toml
   name = "demo"
       nested_indent = true
   ```

**File:** `scripts/setup.sh`
```
#!/bin/sh
echo setup
```
