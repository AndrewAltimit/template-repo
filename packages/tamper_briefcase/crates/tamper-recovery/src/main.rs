//! Quantum-safe recovery key management.
//!
//! Provides subcommands for generating recovery key material, unwrapping
//! secrets, signing disk images, and verifying signatures.
//!
//! Uses a hybrid classical (X25519) + post-quantum (ML-KEM-1024) key
//! encapsulation scheme to protect the recovery secret against
//! harvest-now-decrypt-later attacks.
//!
//! **This binary should only be run on an air-gapped workstation** (for
//! `generate`) or during recovery from a live USB environment (for `unwrap`,
//! `verify`).

mod keygen;
mod unwrap;

use std::path::PathBuf;

use clap::{Parser, Subcommand};
use secrecy::{ExposeSecret, SecretString};

#[derive(Parser)]
#[command(name = "tamper-recovery")]
#[command(about = "Quantum-safe recovery key management for the tamper briefcase")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Generate recovery key material (run on air-gapped workstation).
    Generate {
        /// Output directory for generated key material.
        #[arg(short, long, default_value = "./recovery_keys")]
        output_dir: PathBuf,

        /// Root partition LUKS passphrase.
        #[arg(long)]
        root_passphrase: Option<String>,

        /// Data partition LUKS passphrase.
        #[arg(long)]
        data_passphrase: Option<String>,
    },

    /// Unwrap recovery secrets using private keys.
    Unwrap {
        /// Path to recovery_private.json.
        #[arg(short, long)]
        private_key_file: PathBuf,

        /// Path to recovery_public.json.
        #[arg(short = 'u', long)]
        public_meta_file: PathBuf,

        /// Path to wrapped_secret.bin.
        #[arg(short, long)]
        wrapped_secret_file: PathBuf,

        /// Path to device_secrets.json.enc.
        #[arg(short, long)]
        encrypted_secrets_file: PathBuf,

        /// Output file for decrypted device secrets.
        #[arg(short, long, default_value = "/tmp/.device_secrets.json")]
        output: PathBuf,
    },

    /// Sign a disk image with ML-DSA-87.
    Sign {
        /// Path to the image file to sign.
        #[arg(short, long)]
        image: PathBuf,

        /// Path to the signing private key (from recovery_private.json).
        #[arg(short, long)]
        private_key_file: PathBuf,

        /// Output path for the detached signature.
        #[arg(short, long)]
        output: PathBuf,
    },

    /// Verify a disk image signature.
    Verify {
        /// Path to the image file.
        #[arg(short, long)]
        image: PathBuf,

        /// Path to the detached signature.
        #[arg(short, long)]
        signature: PathBuf,

        /// Path to recovery_public.json (contains signing public key).
        #[arg(short, long)]
        public_meta_file: PathBuf,
    },
}

fn main() -> anyhow::Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let cli = Cli::parse();

    match cli.command {
        Commands::Generate {
            output_dir,
            root_passphrase,
            data_passphrase,
        } => {
            let root_pass: SecretString = match root_passphrase {
                Some(p) => p.into(),
                None => rpassword::prompt_password("Root partition passphrase: ")?.into(),
            };
            let data_pass: SecretString = match data_passphrase {
                Some(p) => p.into(),
                None => rpassword::prompt_password("Data partition passphrase: ")?.into(),
            };
            keygen::generate(
                &output_dir,
                root_pass.expose_secret(),
                data_pass.expose_secret(),
            )
        },
        Commands::Unwrap {
            private_key_file,
            public_meta_file,
            wrapped_secret_file,
            encrypted_secrets_file,
            output,
        } => unwrap::unwrap_secrets(
            &private_key_file,
            &public_meta_file,
            &wrapped_secret_file,
            &encrypted_secrets_file,
            &output,
        ),
        Commands::Sign {
            image,
            private_key_file,
            output,
        } => keygen::sign_image(&image, &private_key_file, &output),
        Commands::Verify {
            image,
            signature,
            public_meta_file,
        } => unwrap::verify_image(&image, &signature, &public_meta_file),
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use std::fs;

    /// End-to-end test: generate key material -> unwrap device secrets.
    ///
    /// This exercises the full PQC key wrapping pipeline:
    /// 1. Generate master secret + hybrid-wrapped keys
    /// 2. Unwrap using the private keys
    /// 3. Verify the decrypted device secrets match the originals
    #[test]
    fn generate_and_unwrap_roundtrip() {
        let dir = tempfile::tempdir().unwrap();

        let root_pass = "test_root_passphrase";
        let data_pass = "test_data_passphrase";

        // Generate all key material.
        crate::keygen::generate(dir.path(), root_pass, data_pass).unwrap();

        // Unwrap secrets using generated material.
        let output = dir.path().join("decrypted_secrets.json");
        crate::unwrap::unwrap_secrets(
            &dir.path().join("private/recovery_private.json"),
            &dir.path().join("public/recovery_public.json"),
            &dir.path().join("public/wrapped_secret.bin"),
            &dir.path().join("encrypted/device_secrets.json.enc"),
            &output,
        )
        .unwrap();

        // Verify the decrypted secrets contain the original passphrases.
        let decrypted: serde_json::Value =
            serde_json::from_str(&fs::read_to_string(&output).unwrap()).unwrap();

        assert_eq!(decrypted["root_passphrase"], root_pass);
        assert_eq!(decrypted["data_passphrase"], data_pass);
    }

    /// Verify that unwrap fails with wrong private keys.
    #[test]
    fn unwrap_fails_with_wrong_keys() {
        let dir1 = tempfile::tempdir().unwrap();
        let dir2 = tempfile::tempdir().unwrap();

        // Generate two independent key sets.
        crate::keygen::generate(dir1.path(), "pass1", "pass2").unwrap();
        crate::keygen::generate(dir2.path(), "pass3", "pass4").unwrap();

        // Try to unwrap dir1's secrets with dir2's private keys.
        let output = dir1.path().join("decrypted.json");
        let result = crate::unwrap::unwrap_secrets(
            &dir2.path().join("private/recovery_private.json"),
            &dir1.path().join("public/recovery_public.json"),
            &dir1.path().join("public/wrapped_secret.bin"),
            &dir1.path().join("encrypted/device_secrets.json.enc"),
            &output,
        );

        assert!(
            result.is_err(),
            "Unwrap should fail with wrong private keys"
        );
    }
}
