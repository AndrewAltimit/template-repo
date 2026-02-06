//! Interactive password challenge for tamper authentication.
//!
//! Presents a password prompt, verifies against a stored scrypt hash, and exits
//! with code 0 on success or 1 on failure. Called by `tamper-gate` as a
//! subprocess with a timeout.
//!
//! Also provides a `--setup` mode for initial password configuration.

use std::fs;
use std::path::{Path, PathBuf};
use std::process;

use anyhow::{Context, Result, bail};
use clap::{Parser, Subcommand};
use scrypt::password_hash::SaltString;
use scrypt::password_hash::rand_core::OsRng;
use scrypt::{
    Params,
    password_hash::{Ident, PasswordHash, PasswordHasher, PasswordVerifier},
};
use secrecy::{ExposeSecret, SecretString};
use subtle::ConstantTimeEq;

/// Default paths for credential storage.
const DEFAULT_HASH_FILE: &str = "/etc/tamper/password.hash";
const DEFAULT_SALT_FILE: &str = "/etc/tamper/salt";

/// Scrypt parameters: n=2^17, r=8, p=1, output length 64 bytes.
const SCRYPT_LOG_N: u8 = 17;
const SCRYPT_R: u32 = 8;
const SCRYPT_P: u32 = 1;
const SCRYPT_OUTPUT_LEN: usize = 64;

/// Maximum number of password attempts.
const MAX_ATTEMPTS: u32 = 3;

#[derive(Parser)]
#[command(name = "tamper-challenge")]
#[command(about = "Tamper authentication challenge")]
struct Cli {
    /// Path to the password hash file (used in challenge mode).
    #[arg(long, default_value = DEFAULT_HASH_FILE)]
    hash_file: PathBuf,

    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Set up the tamper password (run once during initial configuration).
    Setup {
        /// Path to store the password hash.
        #[arg(long, default_value = DEFAULT_HASH_FILE)]
        hash_file: PathBuf,

        /// Path to store the salt.
        #[arg(long, default_value = DEFAULT_SALT_FILE)]
        salt_file: PathBuf,
    },
}

// ---------------------------------------------------------------------------
// Password hashing
// ---------------------------------------------------------------------------

/// Hash a password using scrypt with the given parameters.
fn hash_password(password: &str) -> Result<(Vec<u8>, Vec<u8>)> {
    let salt = SaltString::generate(&mut OsRng);
    let params = Params::new(SCRYPT_LOG_N, SCRYPT_R, SCRYPT_P, SCRYPT_OUTPUT_LEN)
        .context("Invalid scrypt parameters")?;

    let hasher = scrypt::Scrypt;
    let hash = hasher
        .hash_password_customized(
            password.as_bytes(),
            Some(Ident::new("scrypt").expect("valid ident")),
            None,
            params,
            &salt,
        )
        .map_err(|e| anyhow::anyhow!("Failed to hash password: {}", e))?;

    let hash_string = hash.to_string();
    let salt_bytes = salt.as_str().as_bytes().to_vec();

    Ok((hash_string.into_bytes(), salt_bytes))
}

/// Verify a password against a stored hash.
fn verify_password(password: &str, stored_hash: &[u8]) -> bool {
    let hash_str = match std::str::from_utf8(stored_hash) {
        Ok(s) => s,
        Err(_) => return false,
    };

    let parsed_hash = match PasswordHash::new(hash_str) {
        Ok(h) => h,
        Err(_) => return false,
    };

    scrypt::Scrypt
        .verify_password(password.as_bytes(), &parsed_hash)
        .is_ok()
}

// ---------------------------------------------------------------------------
// Setup mode
// ---------------------------------------------------------------------------

fn setup(hash_file: &PathBuf, salt_file: &PathBuf) -> Result<()> {
    eprintln!("=== Tamper Password Setup ===");
    eprintln!();

    let password: SecretString = rpassword::prompt_password("Set tamper password: ")
        .context("Failed to read password")?
        .into();
    let confirm: SecretString = rpassword::prompt_password("Confirm password: ")
        .context("Failed to read confirmation")?
        .into();

    // Constant-time comparison to avoid timing leaks even during setup.
    if password
        .expose_secret()
        .as_bytes()
        .ct_eq(confirm.expose_secret().as_bytes())
        .unwrap_u8()
        != 1
    {
        bail!("Passwords do not match");
    }

    if password.expose_secret().len() < 8 {
        bail!("Password must be at least 8 characters");
    }

    let (hash_bytes, salt_bytes) = hash_password(password.expose_secret())?;

    // Ensure parent directory exists.
    if let Some(parent) = hash_file.parent() {
        fs::create_dir_all(parent).context("Failed to create credential directory")?;
    }

    // Write credential files with restricted permissions from creation (no
    // race window where the file is world-readable).
    #[cfg(unix)]
    {
        use std::io::Write;
        use std::os::unix::fs::OpenOptionsExt;

        let mut f = fs::OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .mode(0o600)
            .open(hash_file)
            .context("Failed to create password hash file")?;
        f.write_all(&hash_bytes)
            .context("Failed to write password hash")?;

        let mut f = fs::OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .mode(0o600)
            .open(salt_file)
            .context("Failed to create salt file")?;
        f.write_all(&salt_bytes).context("Failed to write salt")?;
    }

    #[cfg(not(unix))]
    {
        fs::write(hash_file, &hash_bytes).context("Failed to write password hash")?;
        fs::write(salt_file, &salt_bytes).context("Failed to write salt")?;
    }

    eprintln!("[OK] Password configured.");
    eprintln!("  Hash: {}", hash_file.display());
    eprintln!("  Salt: {}", salt_file.display());

    Ok(())
}

// ---------------------------------------------------------------------------
// Challenge mode (default)
// ---------------------------------------------------------------------------

fn challenge(hash_file: &Path) -> Result<bool> {
    let hash_bytes = fs::read(hash_file)
        .context("Password not configured. Run `tamper-challenge setup` first.")?;

    eprintln!();
    eprintln!("==================================================");
    eprintln!("  TAMPER DETECTED -- AUTHENTICATION REQUIRED");
    eprintln!("  You have 120 seconds and {} attempts.", MAX_ATTEMPTS);
    eprintln!("==================================================");
    eprintln!();

    for attempt in 1..=MAX_ATTEMPTS {
        let remaining = MAX_ATTEMPTS - attempt;
        let password: SecretString = match rpassword::prompt_password(format!(
            "Password (attempt {}/{}): ",
            attempt, MAX_ATTEMPTS
        )) {
            Ok(p) => p.into(),
            Err(_) => return Ok(false),
        };

        if verify_password(password.expose_secret(), &hash_bytes) {
            eprintln!("[OK] Authenticated.");
            return Ok(true);
        }

        eprintln!("[FAIL] Incorrect. {} attempt(s) remaining.", remaining);
    }

    eprintln!("[FAIL] Maximum attempts exceeded.");
    Ok(false)
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Some(Commands::Setup {
            hash_file,
            salt_file,
        }) => {
            if let Err(e) = setup(&hash_file, &salt_file) {
                eprintln!("Setup failed: {}", e);
                process::exit(1);
            }
        },
        None => match challenge(&cli.hash_file) {
            Ok(true) => process::exit(0),
            Ok(false) => process::exit(1),
            Err(e) => {
                eprintln!("Challenge error: {}", e);
                process::exit(1);
            },
        },
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hash_and_verify_correct_password() {
        let password = "test_password_123";
        let (hash_bytes, _salt_bytes) = hash_password(password).unwrap();

        assert!(verify_password(password, &hash_bytes));
    }

    #[test]
    fn verify_rejects_wrong_password() {
        let password = "correct_password";
        let (hash_bytes, _salt_bytes) = hash_password(password).unwrap();

        assert!(!verify_password("wrong_password", &hash_bytes));
    }

    #[test]
    fn verify_rejects_invalid_hash() {
        assert!(!verify_password("anything", b"not a valid hash"));
    }

    #[test]
    fn verify_rejects_non_utf8_hash() {
        assert!(!verify_password("anything", &[0xFF, 0xFE, 0xFD]));
    }

    #[test]
    fn hash_produces_different_salts() {
        let password = "same_password";
        let (hash1, salt1) = hash_password(password).unwrap();
        let (hash2, salt2) = hash_password(password).unwrap();

        // Same password, different salts -> different hashes.
        assert_ne!(salt1, salt2);
        assert_ne!(hash1, hash2);

        // Both should still verify.
        assert!(verify_password(password, &hash1));
        assert!(verify_password(password, &hash2));
    }

    #[test]
    fn hash_output_is_phc_format() {
        let (hash_bytes, _) = hash_password("test12345678").unwrap();
        let hash_str = std::str::from_utf8(&hash_bytes).unwrap();

        // PHC string format: $scrypt$...
        assert!(
            hash_str.starts_with("$scrypt$"),
            "Expected PHC format, got: {}",
            hash_str
        );
    }

    #[test]
    fn setup_writes_credential_files() {
        // We cannot test setup() directly because it reads from stdin via
        // rpassword. Instead, test the file-writing portion by simulating
        // what setup does after password entry.
        let dir = tempfile::tempdir().unwrap();
        let hash_file = dir.path().join("password.hash");
        let salt_file = dir.path().join("salt");

        let password = "integration_test_pw";
        let (hash_bytes, salt_bytes) = hash_password(password).unwrap();

        fs::write(&hash_file, &hash_bytes).unwrap();
        fs::write(&salt_file, &salt_bytes).unwrap();

        // Verify the written hash works.
        let stored_hash = fs::read(&hash_file).unwrap();
        assert!(verify_password(password, &stored_hash));
    }
}
