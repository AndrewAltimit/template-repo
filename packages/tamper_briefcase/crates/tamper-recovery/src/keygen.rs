//! Recovery key generation -- produces all key material for the recovery USB.
//!
//! Run on an AIR-GAPPED workstation only. Never on the Pi itself.
//!
//! # Output structure
//!
//! ```text
//! output_dir/
//! +-- public/               <- goes on USB Partition 1
//! |   +-- recovery_public.json
//! |   +-- wrapped_secret.bin
//! +-- private/              <- store OFFLINE, never on USB
//! |   +-- recovery_private.json
//! |   +-- recovery_secret.hex
//! +-- encrypted/            <- goes on USB Partition 2
//!     +-- device_secrets.json.enc
//! ```

use std::fs;
use std::path::Path;

use aes_gcm::aead::Aead;
use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
use anyhow::{Context, Result};
use base64::Engine;
use base64::engine::general_purpose::STANDARD as B64;
use hkdf::Hkdf;
use pqcrypto_mldsa::mldsa87;
use pqcrypto_mlkem::mlkem1024;
use pqcrypto_traits::kem::{
    Ciphertext, PublicKey as KemPubKey, SecretKey as KemSecKey, SharedSecret,
};
use pqcrypto_traits::sign::{DetachedSignature, PublicKey as SigPubKey, SecretKey as SigSecKey};
use rand::RngCore;
use sha2::Sha512;
use x25519_dalek::{EphemeralSecret, PublicKey, StaticSecret};
use zeroize::Zeroizing;

/// Generate all recovery key material.
pub fn generate(output_dir: &Path, root_passphrase: &str, data_passphrase: &str) -> Result<()> {
    let public_dir = output_dir.join("public");
    let private_dir = output_dir.join("private");
    let encrypted_dir = output_dir.join("encrypted");

    fs::create_dir_all(&public_dir).context("Failed to create public directory")?;
    fs::create_dir_all(&private_dir).context("Failed to create private directory")?;
    fs::create_dir_all(&encrypted_dir).context("Failed to create encrypted directory")?;

    // -- Step 1: Generate master recovery secret --
    let mut recovery_secret = Zeroizing::new([0u8; 64]);
    rand::rngs::OsRng.fill_bytes(recovery_secret.as_mut());

    // -- Step 2: Derive LUKS passphrase for USB Partition 2 --
    let mut usb_salt = [0u8; 32];
    rand::rngs::OsRng.fill_bytes(&mut usb_salt);

    let hk = Hkdf::<Sha512>::new(Some(&usb_salt), recovery_secret.as_ref());
    let mut usb_luks_passphrase = Zeroizing::new([0u8; 64]);
    hk.expand(b"briefcase-recovery-usb-luks", usb_luks_passphrase.as_mut())
        .map_err(|e| anyhow::anyhow!("HKDF expand failed: {}", e))?;

    // -- Step 3: Derive wrapping key for device secrets --
    let mut device_salt = [0u8; 32];
    rand::rngs::OsRng.fill_bytes(&mut device_salt);

    let hk = Hkdf::<Sha512>::new(Some(&device_salt), recovery_secret.as_ref());
    let mut device_wrap_key = Zeroizing::new([0u8; 32]);
    hk.expand(
        b"briefcase-recovery-device-secrets",
        device_wrap_key.as_mut(),
    )
    .map_err(|e| anyhow::anyhow!("HKDF expand failed: {}", e))?;

    // -- Step 4: Encrypt device secrets --
    let device_secrets = serde_json::json!({
        "root_passphrase": root_passphrase,
        "data_passphrase": data_passphrase,
    });
    let device_secrets_bytes = device_secrets.to_string().into_bytes();

    let mut device_nonce_bytes = [0u8; 12];
    rand::rngs::OsRng.fill_bytes(&mut device_nonce_bytes);
    let device_nonce = Nonce::from_slice(&device_nonce_bytes);

    let cipher = Aes256Gcm::new_from_slice(device_wrap_key.as_ref())
        .map_err(|e| anyhow::anyhow!("AES key init failed: {}", e))?;
    let device_ciphertext = cipher
        .encrypt(device_nonce, device_secrets_bytes.as_ref())
        .map_err(|e| anyhow::anyhow!("AES encryption failed: {}", e))?;

    // Write: salt || nonce || ciphertext
    let mut enc_blob = Vec::with_capacity(32 + 12 + device_ciphertext.len());
    enc_blob.extend_from_slice(&device_salt);
    enc_blob.extend_from_slice(&device_nonce_bytes);
    enc_blob.extend_from_slice(&device_ciphertext);

    fs::write(encrypted_dir.join("device_secrets.json.enc"), &enc_blob)
        .context("Failed to write encrypted device secrets")?;

    // -- Step 5: Hybrid key encapsulation of recovery secret --

    // Classical: X25519
    let x25519_static = StaticSecret::random_from_rng(rand::rngs::OsRng);
    let x25519_public = PublicKey::from(&x25519_static);

    let x25519_ephemeral = EphemeralSecret::random_from_rng(rand::rngs::OsRng);
    let x25519_ephemeral_pub = PublicKey::from(&x25519_ephemeral);
    let x25519_shared = x25519_ephemeral.diffie_hellman(&x25519_public);

    // Post-Quantum: ML-KEM-1024
    let (kem_pk, kem_sk) = mlkem1024::keypair();
    let (kem_ss, kem_ct) = mlkem1024::encapsulate(&kem_pk);

    // Combine shared secrets: SHA-512(x25519_shared || kem_shared)
    use sha2::{Digest, Sha512 as Sha512Hash};
    let mut hasher = Sha512Hash::new();
    hasher.update(x25519_shared.as_bytes());
    hasher.update(kem_ss.as_bytes());
    let combined_secret = hasher.finalize();

    // Derive wrapping key from combined secret
    let mut wrap_salt = [0u8; 32];
    rand::rngs::OsRng.fill_bytes(&mut wrap_salt);

    let hk = Hkdf::<Sha512>::new(Some(&wrap_salt), &combined_secret);
    let mut final_wrap_key = Zeroizing::new([0u8; 32]);
    hk.expand(b"briefcase-hybrid-wrap", final_wrap_key.as_mut())
        .map_err(|e| anyhow::anyhow!("HKDF expand failed: {}", e))?;

    // Wrap the recovery secret
    let mut wrap_nonce_bytes = [0u8; 12];
    rand::rngs::OsRng.fill_bytes(&mut wrap_nonce_bytes);
    let wrap_nonce = Nonce::from_slice(&wrap_nonce_bytes);

    let wrap_cipher = Aes256Gcm::new_from_slice(final_wrap_key.as_ref())
        .map_err(|e| anyhow::anyhow!("AES key init failed: {}", e))?;
    let wrapped_secret = wrap_cipher
        .encrypt(wrap_nonce, recovery_secret.as_ref() as &[u8])
        .map_err(|e| anyhow::anyhow!("AES encryption failed: {}", e))?;

    // -- Step 6: Generate signing keypair (ML-DSA-87) --
    let (sig_pk, sig_sk) = mldsa87::keypair();

    // -- Save public material (USB Partition 1) --
    let public_bundle = serde_json::json!({
        "version": 1,
        "classical_algorithm": "X25519",
        "pq_kem_algorithm": "ML-KEM-1024",
        "sig_algorithm": "ML-DSA-87",
        "x25519_public_key": B64.encode(x25519_public.as_bytes()),
        "x25519_ephemeral_public": B64.encode(x25519_ephemeral_pub.as_bytes()),
        "kem_public_key": B64.encode(kem_pk.as_bytes()),
        "kem_ciphertext": B64.encode(kem_ct.as_bytes()),
        "sig_public_key": B64.encode(sig_pk.as_bytes()),
        "wrap_salt": B64.encode(wrap_salt),
        "wrap_nonce": B64.encode(wrap_nonce_bytes),
        "usb_salt": B64.encode(usb_salt),
    });

    fs::write(
        public_dir.join("recovery_public.json"),
        serde_json::to_string_pretty(&public_bundle)?,
    )
    .context("Failed to write public bundle")?;

    fs::write(public_dir.join("wrapped_secret.bin"), &wrapped_secret)
        .context("Failed to write wrapped secret")?;

    // -- Save private material (OFFLINE ONLY) --
    let private_bundle = serde_json::json!({
        "x25519_private_key": B64.encode(x25519_static.to_bytes()),
        "kem_secret_key": B64.encode(kem_sk.as_bytes()),
        "sig_secret_key": B64.encode(sig_sk.as_bytes()),
    });

    fs::write(
        private_dir.join("recovery_private.json"),
        serde_json::to_string_pretty(&private_bundle)?,
    )
    .context("Failed to write private bundle")?;

    fs::write(
        private_dir.join("recovery_secret.hex"),
        hex_encode(recovery_secret.as_ref()),
    )
    .context("Failed to write recovery secret hex")?;

    // -- Print summary --
    eprintln!("==========================================================");
    eprintln!("  RECOVERY KEY MATERIAL GENERATED");
    eprintln!("==========================================================");
    eprintln!();
    eprintln!(
        "  USB LUKS passphrase (hex): {}",
        hex_encode(usb_luks_passphrase.as_ref())
    );
    eprintln!("  Use this when running: cryptsetup luksFormat <usb-partition-2>");
    eprintln!();
    eprintln!("  Public material:  {}/", public_dir.display());
    eprintln!("  Private material: {}/", private_dir.display());
    eprintln!("  Device secrets:   {}/", encrypted_dir.display());
    eprintln!();
    eprintln!("  CRITICAL:");
    eprintln!("  1. Copy public/ -> USB Partition 1");
    eprintln!("  2. Copy encrypted/ -> USB Partition 2 (after LUKS formatting)");
    eprintln!("  3. Copy private/ -> air-gapped storage ONLY");
    eprintln!("  4. SECURELY DELETE private/ and encrypted/ from this machine");
    eprintln!("  5. Write down the USB LUKS passphrase and store with private keys");
    eprintln!("==========================================================");

    // Sensitive material (recovery_secret, usb_luks_passphrase, device_wrap_key,
    // final_wrap_key) is automatically zeroized on drop via secrecy::Zeroizing.

    Ok(())
}

/// Sign a disk image with ML-DSA-87.
pub fn sign_image(image_path: &Path, private_key_file: &Path, output_path: &Path) -> Result<()> {
    let private_json: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(private_key_file)?)?;

    let sig_sk_bytes = B64
        .decode(
            private_json["sig_secret_key"]
                .as_str()
                .context("Missing sig_secret_key")?,
        )
        .context("Invalid base64 for sig_secret_key")?;

    let sig_sk = mldsa87::SecretKey::from_bytes(&sig_sk_bytes)
        .map_err(|e| anyhow::anyhow!("Invalid ML-DSA-87 secret key: {:?}", e))?;

    let image_data = fs::read(image_path).context("Failed to read image file")?;
    let detached_sig = mldsa87::detached_sign(&image_data, &sig_sk);
    let signature_bytes = detached_sig.as_bytes();

    fs::write(output_path, signature_bytes).context("Failed to write signature")?;

    log::info!(
        "Signed {} -> {} ({} bytes)",
        image_path.display(),
        output_path.display(),
        signature_bytes.len()
    );

    Ok(())
}

/// Hex-encode a byte slice.
pub(crate) fn hex_encode(bytes: &[u8]) -> String {
    hex::encode(bytes)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hex_encode_empty() {
        assert_eq!(hex_encode(&[]), "");
    }

    #[test]
    fn hex_encode_known_values() {
        assert_eq!(hex_encode(&[0x00]), "00");
        assert_eq!(hex_encode(&[0xFF]), "ff");
        assert_eq!(hex_encode(&[0xDE, 0xAD, 0xBE, 0xEF]), "deadbeef");
    }

    #[test]
    fn generate_creates_key_material() {
        let dir = tempfile::tempdir().unwrap();

        generate(dir.path(), "test_root_pass", "test_data_pass").unwrap();

        // Verify output directory structure.
        assert!(dir.path().join("public/recovery_public.json").exists());
        assert!(dir.path().join("public/wrapped_secret.bin").exists());
        assert!(dir.path().join("private/recovery_private.json").exists());
        assert!(dir.path().join("private/recovery_secret.hex").exists());
        assert!(
            dir.path()
                .join("encrypted/device_secrets.json.enc")
                .exists()
        );

        // Verify public JSON structure.
        let public_json: serde_json::Value = serde_json::from_str(
            &fs::read_to_string(dir.path().join("public/recovery_public.json")).unwrap(),
        )
        .unwrap();

        assert_eq!(public_json["version"], 1);
        assert_eq!(public_json["classical_algorithm"], "X25519");
        assert_eq!(public_json["pq_kem_algorithm"], "ML-KEM-1024");
        assert_eq!(public_json["sig_algorithm"], "ML-DSA-87");
        assert!(public_json["x25519_public_key"].is_string());
        assert!(public_json["x25519_ephemeral_public"].is_string());
        assert!(public_json["kem_public_key"].is_string());
        assert!(public_json["kem_ciphertext"].is_string());
        assert!(public_json["sig_public_key"].is_string());
        assert!(public_json["wrap_salt"].is_string());
        assert!(public_json["wrap_nonce"].is_string());
        assert!(public_json["usb_salt"].is_string());

        // Verify private JSON structure.
        let private_json: serde_json::Value = serde_json::from_str(
            &fs::read_to_string(dir.path().join("private/recovery_private.json")).unwrap(),
        )
        .unwrap();

        assert!(private_json["x25519_private_key"].is_string());
        assert!(private_json["kem_secret_key"].is_string());
        assert!(private_json["sig_secret_key"].is_string());

        // Verify recovery secret hex is 128 chars (64 bytes).
        let secret_hex =
            fs::read_to_string(dir.path().join("private/recovery_secret.hex")).unwrap();
        assert_eq!(secret_hex.len(), 128);
    }

    #[test]
    fn sign_and_verify_roundtrip() {
        let dir = tempfile::tempdir().unwrap();

        // Generate keys.
        generate(dir.path(), "root", "data").unwrap();

        // Create a dummy image.
        let image_path = dir.path().join("test_image.bin");
        fs::write(&image_path, b"this is a test disk image for signing").unwrap();

        // Sign the image.
        let sig_path = dir.path().join("test_image.bin.sig");
        let private_key_file = dir.path().join("private/recovery_private.json");
        sign_image(&image_path, &private_key_file, &sig_path).unwrap();

        assert!(sig_path.exists());

        // Verify the signature.
        let public_meta_file = dir.path().join("public/recovery_public.json");
        crate::unwrap::verify_image(&image_path, &sig_path, &public_meta_file).unwrap();
    }

    #[test]
    fn verify_rejects_tampered_image() {
        let dir = tempfile::tempdir().unwrap();

        generate(dir.path(), "root", "data").unwrap();

        let image_path = dir.path().join("test_image.bin");
        fs::write(&image_path, b"original image content").unwrap();

        let sig_path = dir.path().join("test_image.bin.sig");
        sign_image(
            &image_path,
            &dir.path().join("private/recovery_private.json"),
            &sig_path,
        )
        .unwrap();

        // Tamper with the image.
        fs::write(&image_path, b"TAMPERED image content").unwrap();

        let result = crate::unwrap::verify_image(
            &image_path,
            &sig_path,
            &dir.path().join("public/recovery_public.json"),
        );
        assert!(result.is_err());
    }
}
