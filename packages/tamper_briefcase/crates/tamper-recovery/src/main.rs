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
