//! Recovery secret unwrapping and image signature verification.
//!
//! Used during the recovery flow to:
//! 1. Decapsulate the hybrid-wrapped recovery secret using offline private keys.
//! 2. Derive the device secrets wrapping key and decrypt the device passphrases.
//! 3. Verify disk image signatures before flashing.
//!
//! Wrap and signature format versions are described in [`crate::format`].

use std::fs;
use std::path::Path;

use aes_gcm::aead::{Aead, Payload};
use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
use anyhow::{Context, Result, bail};
use hkdf::Hkdf;
use pqcrypto_mldsa::mldsa87;
use pqcrypto_mlkem::mlkem1024;
use pqcrypto_traits::kem::SharedSecret;
use pqcrypto_traits::sign::DetachedSignature;
use sha2::Sha512;
use x25519_dalek::PublicKey;
use zeroize::Zeroizing;

use crate::format::{self, PrivateBundle, PublicBundle, SIG_MAGIC_V2, WRAP_AAD_V2, WrapVersion};

/// Unwrap recovery secrets and decrypt device passphrases.
pub fn unwrap_secrets(
    private_key_file: &Path,
    public_meta_file: &Path,
    wrapped_secret_file: &Path,
    encrypted_secrets_file: &Path,
    output: &Path,
) -> Result<()> {
    let private = PrivateBundle::load(private_key_file)?;
    let public = PublicBundle::load(public_meta_file)?;
    let wrapped_secret = fs::read(wrapped_secret_file).context("Failed to read wrapped secret")?;
    let encrypted_blob =
        fs::read(encrypted_secrets_file).context("Failed to read encrypted device secrets")?;

    let recovery_secret = unwrap_recovery_secret(&private, &public, &wrapped_secret)?;
    let device_secrets = decrypt_device_secrets(&recovery_secret, &encrypted_blob)?;

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
        fs::write(output, &*device_secrets).context("Failed to write decrypted device secrets")?;
    }

    log::info!("[OK] Device secrets unwrapped to {}", output.display());

    // Sensitive material (recovery_secret, device_secrets, derived keys, the
    // parsed private bundle) is wiped on drop via `zeroize`.

    Ok(())
}

/// Decapsulate both KEMs, combine per the bundle's wrap version, and decrypt
/// the 64-byte recovery secret.
pub(crate) fn unwrap_recovery_secret(
    private: &PrivateBundle,
    public: &PublicBundle,
    wrapped_secret: &[u8],
) -> Result<Zeroizing<Vec<u8>>> {
    let version = public.wrap_version()?;

    // -- X25519 --
    let x25519_priv = private.x25519_secret()?;
    let recipient_pk = PublicKey::from(&x25519_priv);
    if recipient_pk.as_bytes() != &public.x25519_public()? {
        bail!("X25519 private key does not match the public bundle (wrong key file?)");
    }
    let ephemeral_bytes = public.x25519_ephemeral()?;
    let x25519_shared = x25519_priv.diffie_hellman(&PublicKey::from(ephemeral_bytes));
    if !x25519_shared.was_contributory() {
        bail!("X25519 ephemeral public key is a low-order point; refusing to unwrap");
    }

    // -- ML-KEM-1024 --
    let kem_sk = private.kem_secret()?;
    let kem_ct = public.kem_ciphertext()?;
    // The pqcrypto shared-secret type is `Copy` and cannot be zeroized; copy
    // it into a zeroizing buffer and use only that from here on.
    let kem_shared = Zeroizing::new(mlkem1024::decapsulate(&kem_ct, &kem_sk).as_bytes().to_vec());

    // -- Combine --
    let wrap_salt = public.wrap_salt()?;
    let wrap_nonce = public.wrap_nonce()?;
    let (wrap_key, aad): (_, &[u8]) = match version {
        WrapVersion::V1 => {
            log::warn!(
                "Unwrapping legacy v1 recovery media (no KEM transcript binding); \
                 regenerate the recovery USB with the current tool"
            );
            (
                format::derive_wrap_key_v1(x25519_shared.as_bytes(), &kem_shared, &wrap_salt)?,
                b"",
            )
        },
        WrapVersion::V2 => (
            format::derive_wrap_key_v2(
                &kem_shared,
                x25519_shared.as_bytes(),
                &ephemeral_bytes,
                recipient_pk.as_bytes(),
                &wrap_salt,
            )?,
            WRAP_AAD_V2,
        ),
    };

    // -- Decrypt --
    let wrap_cipher = Aes256Gcm::new_from_slice(wrap_key.as_ref())
        .map_err(|e| anyhow::anyhow!("AES key init failed: {}", e))?;
    let recovery_secret = wrap_cipher
        .decrypt(
            Nonce::from_slice(&wrap_nonce),
            Payload {
                msg: wrapped_secret,
                aad,
            },
        )
        .map(Zeroizing::new)
        .map_err(|_| anyhow::anyhow!("Failed to decrypt recovery secret (wrong keys?)"))?;
    Ok(recovery_secret)
}

/// Decrypt `device_secrets.json.enc` (salt || nonce || ciphertext).
fn decrypt_device_secrets(
    recovery_secret: &[u8],
    encrypted_blob: &[u8],
) -> Result<Zeroizing<Vec<u8>>> {
    // Layout: salt (32) + nonce (12) + ciphertext (>= AES-GCM tag 16) = min 60 bytes
    if encrypted_blob.len() < 60 {
        bail!(
            "Encrypted device secrets blob too short (expected >= 60 bytes, got {})",
            encrypted_blob.len()
        );
    }

    let device_salt = &encrypted_blob[..32];
    let device_nonce_bytes = &encrypted_blob[32..44];
    let device_ciphertext = &encrypted_blob[44..];

    let hk = Hkdf::<Sha512>::new(Some(device_salt), recovery_secret);
    let mut device_wrap_key = Zeroizing::new([0u8; 32]);
    hk.expand(
        b"briefcase-recovery-device-secrets",
        device_wrap_key.as_mut(),
    )
    .map_err(|e| anyhow::anyhow!("HKDF expand failed: {}", e))?;

    let device_cipher = Aes256Gcm::new_from_slice(device_wrap_key.as_ref())
        .map_err(|e| anyhow::anyhow!("AES key init failed: {}", e))?;

    // `device_nonce_bytes` is exactly 12 bytes by the slicing above.
    device_cipher
        .decrypt(Nonce::from_slice(device_nonce_bytes), device_ciphertext)
        .map(Zeroizing::new)
        .map_err(|_| anyhow::anyhow!("Failed to decrypt device secrets"))
}

/// Verify a disk image signature using ML-DSA-87.
///
/// v2 signature files (with [`SIG_MAGIC_V2`]) are checked against a streamed
/// SHA-512 of the image. A bare legacy v1 signature covers the raw image, so
/// that path still has to read the whole image into memory.
pub fn verify_image(
    image_path: &Path,
    signature_path: &Path,
    public_meta_file: &Path,
) -> Result<()> {
    let public = PublicBundle::load(public_meta_file)?;
    let sig_pk = public.sig_public()?;
    let signature_file = format::read_signature_file(signature_path)?;

    let verified = if let Some(sig_bytes) = signature_file.strip_prefix(SIG_MAGIC_V2.as_slice()) {
        let detached_sig = mldsa87::DetachedSignature::from_bytes(sig_bytes)
            .map_err(|e| anyhow::anyhow!("Invalid ML-DSA-87 signature: {:?}", e))?;
        let digest = format::image_digest(image_path)?;
        mldsa87::verify_detached_signature(
            &detached_sig,
            &format::signed_message_v2(&digest),
            &sig_pk,
        )
    } else if signature_file.len() == mldsa87::signature_bytes() {
        log::warn!(
            "Legacy v1 signature (raw image, no prehash); reading the whole image into \
             memory. Re-sign with the current `tamper-recovery sign`."
        );
        let detached_sig = mldsa87::DetachedSignature::from_bytes(&signature_file)
            .map_err(|e| anyhow::anyhow!("Invalid ML-DSA-87 signature: {:?}", e))?;
        let image_data = fs::read(image_path).context("Failed to read image file")?;
        mldsa87::verify_detached_signature(&detached_sig, &image_data, &sig_pk)
    } else {
        bail!(
            "Unrecognized signature file format ({} bytes)",
            signature_file.len()
        );
    };

    match verified {
        Ok(()) => {
            log::info!("[OK] Image signature verified.");
            Ok(())
        },
        Err(_) => {
            bail!("Signature verification FAILED; image may be tampered");
        },
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use std::path::{Path, PathBuf};

    use base64::Engine;
    use base64::engine::general_purpose::STANDARD as B64;

    use super::*;
    use crate::keygen::{generate, generate_versioned};

    struct Paths {
        private: PathBuf,
        public: PathBuf,
        wrapped: PathBuf,
        encrypted: PathBuf,
        output: PathBuf,
    }

    fn paths(dir: &Path) -> Paths {
        Paths {
            private: dir.join("private/recovery_private.json"),
            public: dir.join("public/recovery_public.json"),
            wrapped: dir.join("public/wrapped_secret.bin"),
            encrypted: dir.join("encrypted/device_secrets.json.enc"),
            output: dir.join("out.json"),
        }
    }

    fn unwrap_at(p: &Paths) -> Result<()> {
        unwrap_secrets(&p.private, &p.public, &p.wrapped, &p.encrypted, &p.output)
    }

    fn edit_json(path: &Path, f: impl FnOnce(&mut serde_json::Value)) {
        let mut v: serde_json::Value =
            serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap();
        f(&mut v);
        fs::write(path, serde_json::to_string(&v).unwrap()).unwrap();
    }

    fn decrypted(p: &Paths) -> serde_json::Value {
        serde_json::from_str(&fs::read_to_string(&p.output).unwrap()).unwrap()
    }

    #[test]
    fn v2_round_trip() {
        let dir = tempfile::tempdir().unwrap();
        generate(dir.path(), "root-pw", "data-pw").unwrap();
        let p = paths(dir.path());
        assert_eq!(PublicBundle::load(&p.public).unwrap().version, 2);
        unwrap_at(&p).unwrap();
        assert_eq!(decrypted(&p)["root_passphrase"], "root-pw");
        assert_eq!(decrypted(&p)["data_passphrase"], "data-pw");
    }

    #[test]
    fn legacy_v1_media_still_unwraps() {
        let dir = tempfile::tempdir().unwrap();
        generate_versioned(dir.path(), "r1", "d1", WrapVersion::V1).unwrap();
        let p = paths(dir.path());
        assert_eq!(PublicBundle::load(&p.public).unwrap().version, 1);
        unwrap_at(&p).unwrap();
        assert_eq!(decrypted(&p)["root_passphrase"], "r1");
    }

    #[test]
    fn version_downgrade_is_rejected() {
        let dir = tempfile::tempdir().unwrap();
        generate(dir.path(), "r", "d").unwrap();
        let p = paths(dir.path());
        edit_json(&p.public, |v| v["version"] = 1.into());
        assert!(unwrap_at(&p).is_err());
    }

    #[test]
    fn unknown_or_missing_version_is_rejected() {
        let dir = tempfile::tempdir().unwrap();
        generate(dir.path(), "r", "d").unwrap();
        let p = paths(dir.path());
        edit_json(&p.public, |v| v["version"] = 3.into());
        let err = unwrap_at(&p).unwrap_err();
        assert!(format!("{err:#}").contains("Unsupported"), "{err:#}");

        edit_json(&p.public, |v| {
            v.as_object_mut().unwrap().remove("version");
        });
        assert!(unwrap_at(&p).is_err());
    }

    #[test]
    fn wrong_private_key_is_rejected() {
        let a = tempfile::tempdir().unwrap();
        let b = tempfile::tempdir().unwrap();
        generate(a.path(), "r", "d").unwrap();
        generate(b.path(), "r", "d").unwrap();
        let mut p = paths(a.path());
        p.private = paths(b.path()).private;
        assert!(unwrap_at(&p).is_err());
    }

    #[test]
    fn tampered_wrapped_ciphertext_is_rejected() {
        let dir = tempfile::tempdir().unwrap();
        generate(dir.path(), "r", "d").unwrap();
        let p = paths(dir.path());
        let mut wrapped = fs::read(&p.wrapped).unwrap();
        wrapped[0] ^= 0x01;
        fs::write(&p.wrapped, wrapped).unwrap();
        assert!(unwrap_at(&p).is_err());
    }

    #[test]
    fn tampered_kem_ciphertext_is_rejected() {
        let dir = tempfile::tempdir().unwrap();
        generate(dir.path(), "r", "d").unwrap();
        let p = paths(dir.path());
        edit_json(&p.public, |v| {
            let mut ct = B64.decode(v["kem_ciphertext"].as_str().unwrap()).unwrap();
            ct[10] ^= 0x01;
            v["kem_ciphertext"] = B64.encode(ct).into();
        });
        assert!(unwrap_at(&p).is_err());
    }

    #[test]
    fn swapped_ephemeral_key_is_rejected() {
        // The v2 combiner binds the X25519 transcript: substituting another
        // valid ephemeral public key must break the unwrap.
        let a = tempfile::tempdir().unwrap();
        let b = tempfile::tempdir().unwrap();
        generate(a.path(), "r", "d").unwrap();
        generate(b.path(), "r", "d").unwrap();
        let other: serde_json::Value =
            serde_json::from_str(&fs::read_to_string(paths(b.path()).public).unwrap()).unwrap();
        let p = paths(a.path());
        edit_json(&p.public, |v| {
            v["x25519_ephemeral_public"] = other["x25519_ephemeral_public"].clone();
        });
        assert!(unwrap_at(&p).is_err());
    }

    #[test]
    fn short_wrap_nonce_is_an_error_not_a_panic() {
        let dir = tempfile::tempdir().unwrap();
        generate(dir.path(), "r", "d").unwrap();
        let p = paths(dir.path());
        edit_json(&p.public, |v| v["wrap_nonce"] = B64.encode([0u8; 8]).into());
        let err = unwrap_at(&p).unwrap_err();
        assert!(
            format!("{err:#}").contains("wrap_nonce must be 12 bytes"),
            "{err:#}"
        );
    }

    #[test]
    fn malformed_private_bundle_is_rejected() {
        let dir = tempfile::tempdir().unwrap();
        generate(dir.path(), "r", "d").unwrap();
        let p = paths(dir.path());
        let original = fs::read_to_string(&p.private).unwrap();

        // Wrong-length X25519 key.
        edit_json(&p.private, |v| {
            v["x25519_private_key"] = B64.encode([1u8; 31]).into();
        });
        let err = unwrap_at(&p).unwrap_err();
        assert!(format!("{err:#}").contains("must be 32 bytes"), "{err:#}");

        // Missing field.
        fs::write(&p.private, &original).unwrap();
        edit_json(&p.private, |v| {
            v.as_object_mut().unwrap().remove("kem_secret_key");
        });
        assert!(unwrap_at(&p).is_err());

        // Unknown field (typo or wrong file) is refused.
        fs::write(&p.private, &original).unwrap();
        edit_json(&p.private, |v| v["extra"] = "x".into());
        assert!(unwrap_at(&p).is_err());

        // Restored file works again.
        fs::write(&p.private, &original).unwrap();
        unwrap_at(&p).unwrap();
    }

    #[test]
    fn legacy_raw_signature_still_verifies() {
        let dir = tempfile::tempdir().unwrap();
        generate(dir.path(), "r", "d").unwrap();
        let p = paths(dir.path());
        let image = dir.path().join("img.bin");
        fs::write(&image, b"legacy image").unwrap();

        let sk = PrivateBundle::load(&p.private)
            .unwrap()
            .sig_secret()
            .unwrap();
        let sig = mldsa87::detached_sign(b"legacy image", &sk);
        let sig_path = dir.path().join("img.sig");
        fs::write(&sig_path, sig.as_bytes()).unwrap();
        verify_image(&image, &sig_path, &p.public).unwrap();

        // Neither v2 nor a bare signature: rejected.
        fs::write(&sig_path, [0u8; 100]).unwrap();
        assert!(verify_image(&image, &sig_path, &p.public).is_err());
    }

    #[test]
    fn v2_signature_streams_and_is_domain_separated() {
        let dir = tempfile::tempdir().unwrap();
        generate(dir.path(), "r", "d").unwrap();
        let p = paths(dir.path());
        // Larger than one hash buffer so streaming spans several reads.
        let image = dir.path().join("img.bin");
        fs::write(&image, vec![7u8; 3 * 1024 * 1024 + 5]).unwrap();

        let sig_path = dir.path().join("img.sig");
        crate::keygen::sign_image(&image, &p.private, &sig_path).unwrap();
        assert!(fs::read(&sig_path).unwrap().starts_with(SIG_MAGIC_V2));
        verify_image(&image, &sig_path, &p.public).unwrap();

        // A signature over the bare digest (no domain label) must not verify.
        let sk = PrivateBundle::load(&p.private)
            .unwrap()
            .sig_secret()
            .unwrap();
        let digest = format::image_digest(&image).unwrap();
        let bare = mldsa87::detached_sign(&digest, &sk);
        let mut forged = SIG_MAGIC_V2.to_vec();
        forged.extend_from_slice(bare.as_bytes());
        fs::write(&sig_path, forged).unwrap();
        assert!(verify_image(&image, &sig_path, &p.public).is_err());
    }
}
