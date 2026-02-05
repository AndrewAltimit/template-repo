//! Recovery secret unwrapping and image signature verification.
//!
//! Used during the recovery flow to:
//! 1. Decapsulate the hybrid-wrapped recovery secret using offline private keys.
//! 2. Derive the device secrets wrapping key and decrypt the device passphrases.
//! 3. Verify disk image signatures before flashing.

use std::fs;
use std::path::Path;

use aes_gcm::aead::Aead;
use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
use anyhow::{Context, Result, bail};
use base64::Engine;
use base64::engine::general_purpose::STANDARD as B64;
use hkdf::Hkdf;
use pqcrypto_mldsa::mldsa87;
use pqcrypto_mlkem::mlkem1024;
use pqcrypto_traits::kem::{Ciphertext, SecretKey as KemSecKey, SharedSecret};
use pqcrypto_traits::sign::{DetachedSignature, PublicKey as SigPubKey};
use sha2::Sha512;
use x25519_dalek::{PublicKey, StaticSecret};
use zeroize::Zeroizing;

/// Unwrap recovery secrets and decrypt device passphrases.
pub fn unwrap_secrets(
    private_key_file: &Path,
    public_meta_file: &Path,
    wrapped_secret_file: &Path,
    encrypted_secrets_file: &Path,
    output: &Path,
) -> Result<()> {
    let private_json: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(private_key_file)?)?;
    let public_json: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(public_meta_file)?)?;
    let wrapped_secret = fs::read(wrapped_secret_file).context("Failed to read wrapped secret")?;
    let encrypted_blob =
        fs::read(encrypted_secrets_file).context("Failed to read encrypted device secrets")?;

    // -- Step 1: X25519 key exchange --
    let x25519_priv_bytes = B64
        .decode(
            private_json["x25519_private_key"]
                .as_str()
                .context("Missing x25519_private_key")?,
        )
        .context("Invalid base64 for x25519_private_key")?;

    let ephemeral_pub_bytes = B64
        .decode(
            public_json["x25519_ephemeral_public"]
                .as_str()
                .context("Missing x25519_ephemeral_public")?,
        )
        .context("Invalid base64 for x25519_ephemeral_public")?;

    let x25519_priv = StaticSecret::from(
        <[u8; 32]>::try_from(x25519_priv_bytes.as_slice())
            .map_err(|_| anyhow::anyhow!("X25519 private key must be 32 bytes"))?,
    );

    let ephemeral_pub = PublicKey::from(
        <[u8; 32]>::try_from(ephemeral_pub_bytes.as_slice())
            .map_err(|_| anyhow::anyhow!("X25519 ephemeral public key must be 32 bytes"))?,
    );

    let x25519_shared = x25519_priv.diffie_hellman(&ephemeral_pub);

    // -- Step 2: ML-KEM-1024 decapsulation --
    let kem_sk_bytes = B64
        .decode(
            private_json["kem_secret_key"]
                .as_str()
                .context("Missing kem_secret_key")?,
        )
        .context("Invalid base64 for kem_secret_key")?;

    let kem_ct_bytes = B64
        .decode(
            public_json["kem_ciphertext"]
                .as_str()
                .context("Missing kem_ciphertext")?,
        )
        .context("Invalid base64 for kem_ciphertext")?;

    let kem_sk = mlkem1024::SecretKey::from_bytes(&kem_sk_bytes)
        .map_err(|e| anyhow::anyhow!("Invalid ML-KEM-1024 secret key: {:?}", e))?;
    let kem_ct = mlkem1024::Ciphertext::from_bytes(&kem_ct_bytes)
        .map_err(|e| anyhow::anyhow!("Invalid ML-KEM-1024 ciphertext: {:?}", e))?;

    let kem_shared = mlkem1024::decapsulate(&kem_ct, &kem_sk);

    // -- Step 3: Combine shared secrets --
    use sha2::{Digest, Sha512 as Sha512Hash};
    let mut hasher = Sha512Hash::new();
    hasher.update(x25519_shared.as_bytes());
    hasher.update(kem_shared.as_bytes());
    let combined_secret = hasher.finalize();

    // -- Step 4: Derive wrapping key --
    let wrap_salt = B64
        .decode(
            public_json["wrap_salt"]
                .as_str()
                .context("Missing wrap_salt")?,
        )
        .context("Invalid base64 for wrap_salt")?;

    let wrap_nonce_bytes = B64
        .decode(
            public_json["wrap_nonce"]
                .as_str()
                .context("Missing wrap_nonce")?,
        )
        .context("Invalid base64 for wrap_nonce")?;

    let hk = Hkdf::<Sha512>::new(Some(&wrap_salt), &combined_secret);
    let mut final_wrap_key = Zeroizing::new([0u8; 32]);
    hk.expand(b"briefcase-hybrid-wrap", final_wrap_key.as_mut())
        .map_err(|e| anyhow::anyhow!("HKDF expand failed: {}", e))?;

    // -- Step 5: Decrypt recovery secret --
    let wrap_nonce = Nonce::from_slice(&wrap_nonce_bytes);
    let wrap_cipher = Aes256Gcm::new_from_slice(final_wrap_key.as_ref())
        .map_err(|e| anyhow::anyhow!("AES key init failed: {}", e))?;

    let recovery_secret = Zeroizing::new(
        wrap_cipher
            .decrypt(wrap_nonce, wrapped_secret.as_ref())
            .map_err(|_| anyhow::anyhow!("Failed to decrypt recovery secret -- wrong keys?"))?,
    );

    // -- Step 6: Derive device secrets wrapping key --
    if encrypted_blob.len() < 44 {
        bail!("Encrypted device secrets blob too short");
    }

    let device_salt = &encrypted_blob[..32];
    let device_nonce_bytes = &encrypted_blob[32..44];
    let device_ciphertext = &encrypted_blob[44..];

    let hk = Hkdf::<Sha512>::new(Some(device_salt), recovery_secret.as_ref());
    let mut device_wrap_key = Zeroizing::new([0u8; 32]);
    hk.expand(
        b"briefcase-recovery-device-secrets",
        device_wrap_key.as_mut(),
    )
    .map_err(|e| anyhow::anyhow!("HKDF expand failed: {}", e))?;

    // -- Step 7: Decrypt device secrets --
    let device_nonce = Nonce::from_slice(device_nonce_bytes);
    let device_cipher = Aes256Gcm::new_from_slice(device_wrap_key.as_ref())
        .map_err(|e| anyhow::anyhow!("AES key init failed: {}", e))?;

    let device_secrets = device_cipher
        .decrypt(device_nonce, device_ciphertext)
        .map_err(|_| anyhow::anyhow!("Failed to decrypt device secrets"))?;

    // Write to output file with restricted permissions from creation.
    #[cfg(unix)]
    {
        use std::io::Write;
        use std::os::unix::fs::OpenOptionsExt;
        let mut f = fs::OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .mode(0o600)
            .open(output)
            .context("Failed to create output file")?;
        f.write_all(&device_secrets)
            .context("Failed to write decrypted device secrets")?;
    }
    #[cfg(not(unix))]
    {
        fs::write(output, &device_secrets).context("Failed to write decrypted device secrets")?;
    }

    log::info!("[OK] Device secrets unwrapped to {}", output.display());

    // Sensitive material (recovery_secret, final_wrap_key, device_wrap_key)
    // is automatically zeroized on drop via secrecy::Zeroizing.

    Ok(())
}

/// Verify a disk image signature using ML-DSA-87.
pub fn verify_image(
    image_path: &Path,
    signature_path: &Path,
    public_meta_file: &Path,
) -> Result<()> {
    let public_json: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(public_meta_file)?)?;

    let sig_pk_bytes = B64
        .decode(
            public_json["sig_public_key"]
                .as_str()
                .context("Missing sig_public_key")?,
        )
        .context("Invalid base64 for sig_public_key")?;

    let sig_pk = mldsa87::PublicKey::from_bytes(&sig_pk_bytes)
        .map_err(|e| anyhow::anyhow!("Invalid ML-DSA-87 public key: {:?}", e))?;

    let image_data = fs::read(image_path).context("Failed to read image file")?;
    let signature_data = fs::read(signature_path).context("Failed to read signature file")?;

    let detached_sig = mldsa87::DetachedSignature::from_bytes(&signature_data)
        .map_err(|e| anyhow::anyhow!("Invalid ML-DSA-87 signature: {:?}", e))?;

    match mldsa87::verify_detached_signature(&detached_sig, &image_data, &sig_pk) {
        Ok(()) => {
            log::info!("[OK] Image signature verified.");
            Ok(())
        },
        Err(_) => {
            bail!("Signature verification FAILED -- image may be tampered");
        },
    }
}
