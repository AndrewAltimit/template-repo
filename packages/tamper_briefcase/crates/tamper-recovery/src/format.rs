//! On-disk formats, input validation, and the hybrid KEM combiner.
//!
//! # Wrap format versions
//!
//! `recovery_public.json` carries a `version` field that selects how the
//! recovery secret was wrapped. Unwrap dispatches on it explicitly; an unknown
//! or missing version is an error, never a guess.
//!
//! - **v2 (current, written by `generate`)**: X-Wing-style combiner. The
//!   wrapping key is `HKDF-SHA512(salt = wrap_salt, ikm = LABEL || ss_mlkem ||
//!   ss_x25519 || ct_x25519 || pk_x25519, info = LABEL)`, where `ct_x25519` is
//!   the ephemeral public key and `pk_x25519` the recipient public key. Binding
//!   the X25519 transcript means the combined secret is tied to this exact
//!   encapsulation even if one component KEM is weak. The AES-256-GCM wrap also
//!   authenticates a version label as associated data.
//! - **v1 (legacy, unwrap only)**: `HKDF-SHA512(salt, SHA-512(ss_x25519 ||
//!   ss_mlkem), "briefcase-hybrid-wrap")`, no transcript binding, no AAD.
//!   Kept so recovery USBs produced by earlier builds remain recoverable.
//!   Regenerate such media with the current `generate` when convenient.
//!
//! A version downgrade (editing `version` from 2 to 1 in the public bundle)
//! derives a different key, so AES-GCM authentication fails.
//!
//! # Image signature versions
//!
//! Signature files written by `sign` start with [`SIG_MAGIC_V2`] followed by
//! an ML-DSA-87 signature over `SIG_DOMAIN_V2 || SHA-512(image)`, so the image
//! is streamed through the hasher instead of being loaded into memory. A file
//! that is exactly one bare ML-DSA-87 signature is a legacy v1 signature over
//! the raw image bytes; verifying it still requires reading the whole image.
//!
//! # Private key storage
//!
//! `recovery_private.json` is **not encrypted**. It must live on protected
//! offline media (for example an encrypted, air-gapped token).

use std::fs;
use std::io::{BufReader, Read};
use std::path::Path;

use anyhow::{Context, Result, bail};
use base64::Engine;
use base64::engine::general_purpose::STANDARD as B64;
use hkdf::Hkdf;
use pqcrypto_mldsa::mldsa87;
use pqcrypto_mlkem::mlkem1024;
use pqcrypto_traits::kem::{Ciphertext, SecretKey as KemSecKey};
use pqcrypto_traits::sign::{PublicKey as SigPubKey, SecretKey as SigSecKey};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha512};
use x25519_dalek::StaticSecret;
use zeroize::{Zeroize, ZeroizeOnDrop, Zeroizing};

pub const CLASSICAL_ALGORITHM: &str = "X25519";
pub const PQ_KEM_ALGORITHM: &str = "ML-KEM-1024";
pub const SIG_ALGORITHM: &str = "ML-DSA-87";

/// Domain label for the v2 hybrid combiner (HKDF IKM prefix and info).
pub const HYBRID_LABEL_V2: &[u8] = b"briefcase-hybrid-wrap-v2/X25519+ML-KEM-1024";
/// AES-GCM associated data for the v2 wrapped recovery secret.
pub const WRAP_AAD_V2: &[u8] = b"briefcase-wrapped-recovery-secret-v2";
/// HKDF info string of the legacy v1 combiner.
const HYBRID_INFO_V1: &[u8] = b"briefcase-hybrid-wrap";

/// Header of a v2 signature file.
pub const SIG_MAGIC_V2: &[u8; 8] = b"BCSIGv2\0";
/// Domain separator prepended to the image digest before signing (v2).
pub const SIG_DOMAIN_V2: &[u8] = b"briefcase-image-signature-v2\0";

/// Upper bound on a signature file, to avoid reading an arbitrary large file.
const MAX_SIGNATURE_FILE_BYTES: u64 = 64 * 1024;
/// Read buffer for streaming images through the hasher.
const HASH_BUF_BYTES: usize = 1024 * 1024;

/// Wrap format version, from the public bundle's `version` field.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WrapVersion {
    /// Legacy combiner without transcript binding (unwrap only).
    V1,
    /// X-Wing-style combiner with transcript binding (current).
    V2,
}

impl WrapVersion {
    pub const CURRENT: Self = Self::V2;

    pub fn from_u32(v: u32) -> Result<Self> {
        match v {
            1 => Ok(Self::V1),
            2 => Ok(Self::V2),
            other => bail!("Unsupported recovery wrap format version {other} (supported: 1, 2)"),
        }
    }

    pub fn as_u32(self) -> u32 {
        match self {
            Self::V1 => 1,
            Self::V2 => 2,
        }
    }
}

// ---------------------------------------------------------------------------
// Base64 field decoding
// ---------------------------------------------------------------------------

fn decode(field: &str, value: &str) -> Result<Vec<u8>> {
    B64.decode(value)
        .with_context(|| format!("Invalid base64 for {field}"))
}

fn decode_array<const N: usize>(field: &str, value: &str) -> Result<[u8; N]> {
    let bytes = decode(field, value)?;
    <[u8; N]>::try_from(bytes.as_slice())
        .map_err(|_| anyhow::anyhow!("{field} must be {N} bytes, got {}", bytes.len()))
}

fn decode_secret(field: &str, value: &str, expected_len: usize) -> Result<Zeroizing<Vec<u8>>> {
    let bytes = Zeroizing::new(decode(field, value)?);
    if bytes.len() != expected_len {
        bail!("{field} must be {expected_len} bytes, got {}", bytes.len());
    }
    Ok(bytes)
}

// ---------------------------------------------------------------------------
// Public bundle (USB partition 1)
// ---------------------------------------------------------------------------

/// `recovery_public.json`.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PublicBundle {
    pub version: u32,
    pub classical_algorithm: String,
    pub pq_kem_algorithm: String,
    pub sig_algorithm: String,
    pub x25519_public_key: String,
    pub x25519_ephemeral_public: String,
    pub kem_public_key: String,
    pub kem_ciphertext: String,
    pub sig_public_key: String,
    pub wrap_salt: String,
    pub wrap_nonce: String,
    pub usb_salt: String,
}

impl PublicBundle {
    /// Parse and validate a public bundle file.
    pub fn load(path: &Path) -> Result<Self> {
        let text = fs::read_to_string(path)
            .with_context(|| format!("Failed to read {}", path.display()))?;
        let bundle: Self = serde_json::from_str(&text)
            .with_context(|| format!("Malformed public bundle {}", path.display()))?;
        bundle.validate()?;
        Ok(bundle)
    }

    /// Check version, algorithm identifiers, and every field's encoding and
    /// length, so later steps cannot panic on malformed input.
    pub fn validate(&self) -> Result<()> {
        self.wrap_version()?;
        if self.classical_algorithm != CLASSICAL_ALGORITHM
            || self.pq_kem_algorithm != PQ_KEM_ALGORITHM
            || self.sig_algorithm != SIG_ALGORITHM
        {
            bail!(
                "Unsupported algorithms ({}, {}, {}); expected ({CLASSICAL_ALGORITHM}, \
                 {PQ_KEM_ALGORITHM}, {SIG_ALGORITHM})",
                self.classical_algorithm,
                self.pq_kem_algorithm,
                self.sig_algorithm
            );
        }
        self.x25519_public()?;
        self.x25519_ephemeral()?;
        self.kem_ciphertext()?;
        let kem_pk = decode("kem_public_key", &self.kem_public_key)?;
        if kem_pk.len() != mlkem1024::public_key_bytes() {
            bail!(
                "kem_public_key must be {} bytes, got {}",
                mlkem1024::public_key_bytes(),
                kem_pk.len()
            );
        }
        self.sig_public()?;
        self.wrap_salt()?;
        self.wrap_nonce()?;
        decode_array::<32>("usb_salt", &self.usb_salt)?;
        Ok(())
    }

    pub fn wrap_version(&self) -> Result<WrapVersion> {
        WrapVersion::from_u32(self.version)
    }

    pub fn x25519_public(&self) -> Result<[u8; 32]> {
        decode_array("x25519_public_key", &self.x25519_public_key)
    }

    pub fn x25519_ephemeral(&self) -> Result<[u8; 32]> {
        decode_array("x25519_ephemeral_public", &self.x25519_ephemeral_public)
    }

    pub fn kem_ciphertext(&self) -> Result<mlkem1024::Ciphertext> {
        let bytes = decode("kem_ciphertext", &self.kem_ciphertext)?;
        mlkem1024::Ciphertext::from_bytes(&bytes)
            .map_err(|e| anyhow::anyhow!("Invalid ML-KEM-1024 ciphertext: {:?}", e))
    }

    pub fn sig_public(&self) -> Result<mldsa87::PublicKey> {
        let bytes = decode("sig_public_key", &self.sig_public_key)?;
        mldsa87::PublicKey::from_bytes(&bytes)
            .map_err(|e| anyhow::anyhow!("Invalid ML-DSA-87 public key: {:?}", e))
    }

    pub fn wrap_salt(&self) -> Result<[u8; 32]> {
        decode_array("wrap_salt", &self.wrap_salt)
    }

    /// The AES-GCM nonce, validated to exactly 12 bytes.
    pub fn wrap_nonce(&self) -> Result<[u8; 12]> {
        decode_array("wrap_nonce", &self.wrap_nonce)
    }
}

// ---------------------------------------------------------------------------
// Private bundle (offline only)
// ---------------------------------------------------------------------------

/// `recovery_private.json`. Stored unencrypted; see the module docs. The
/// base64 strings are wiped when the struct is dropped.
#[derive(Serialize, Deserialize, Zeroize, ZeroizeOnDrop)]
#[serde(deny_unknown_fields)]
pub struct PrivateBundle {
    pub x25519_private_key: String,
    pub kem_secret_key: String,
    pub sig_secret_key: String,
}

impl PrivateBundle {
    /// Parse and validate a private bundle file.
    pub fn load(path: &Path) -> Result<Self> {
        let text = Zeroizing::new(
            fs::read_to_string(path)
                .with_context(|| format!("Failed to read {}", path.display()))?,
        );
        // serde_json's error text never echoes string contents, so key
        // material cannot leak through this message.
        let bundle: Self = serde_json::from_str(&text)
            .with_context(|| format!("Malformed private key bundle {}", path.display()))?;
        bundle.x25519_secret()?;
        bundle.kem_secret()?;
        bundle.sig_secret()?;
        Ok(bundle)
    }

    pub fn x25519_secret(&self) -> Result<StaticSecret> {
        let bytes = Zeroizing::new(decode_array::<32>(
            "x25519_private_key",
            &self.x25519_private_key,
        )?);
        Ok(StaticSecret::from(*bytes))
    }

    pub fn kem_secret(&self) -> Result<mlkem1024::SecretKey> {
        let bytes = decode_secret(
            "kem_secret_key",
            &self.kem_secret_key,
            mlkem1024::secret_key_bytes(),
        )?;
        mlkem1024::SecretKey::from_bytes(&bytes)
            .map_err(|e| anyhow::anyhow!("Invalid ML-KEM-1024 secret key: {:?}", e))
    }

    pub fn sig_secret(&self) -> Result<mldsa87::SecretKey> {
        let bytes = decode_secret(
            "sig_secret_key",
            &self.sig_secret_key,
            mldsa87::secret_key_bytes(),
        )?;
        mldsa87::SecretKey::from_bytes(&bytes)
            .map_err(|e| anyhow::anyhow!("Invalid ML-DSA-87 secret key: {:?}", e))
    }
}

/// Plaintext of `device_secrets.json.enc`.
#[derive(Serialize)]
pub struct DeviceSecrets<'a> {
    pub root_passphrase: &'a str,
    pub data_passphrase: &'a str,
}

// ---------------------------------------------------------------------------
// Hybrid combiners
// ---------------------------------------------------------------------------

/// v2 X-Wing-style combiner. See the module docs for the construction.
pub fn derive_wrap_key_v2(
    kem_ss: &[u8],
    x25519_ss: &[u8; 32],
    x25519_ephemeral_pk: &[u8; 32],
    x25519_recipient_pk: &[u8; 32],
    salt: &[u8],
) -> Result<Zeroizing<[u8; 32]>> {
    let mut ikm = Zeroizing::new(Vec::with_capacity(
        HYBRID_LABEL_V2.len() + kem_ss.len() + 3 * 32,
    ));
    ikm.extend_from_slice(HYBRID_LABEL_V2);
    ikm.extend_from_slice(kem_ss);
    ikm.extend_from_slice(x25519_ss);
    ikm.extend_from_slice(x25519_ephemeral_pk);
    ikm.extend_from_slice(x25519_recipient_pk);

    let hk = Hkdf::<Sha512>::new(Some(salt), &ikm);
    let mut key = Zeroizing::new([0u8; 32]);
    hk.expand(HYBRID_LABEL_V2, key.as_mut())
        .map_err(|e| anyhow::anyhow!("HKDF expand failed: {}", e))?;
    Ok(key)
}

/// Legacy v1 combiner (unwrap of pre-v2 media only).
pub fn derive_wrap_key_v1(
    x25519_ss: &[u8; 32],
    kem_ss: &[u8],
    salt: &[u8],
) -> Result<Zeroizing<[u8; 32]>> {
    let mut hasher = Sha512::new();
    hasher.update(x25519_ss);
    hasher.update(kem_ss);
    let mut combined = Zeroizing::new([0u8; 64]);
    combined.copy_from_slice(&hasher.finalize());

    let hk = Hkdf::<Sha512>::new(Some(salt), combined.as_ref());
    let mut key = Zeroizing::new([0u8; 32]);
    hk.expand(HYBRID_INFO_V1, key.as_mut())
        .map_err(|e| anyhow::anyhow!("HKDF expand failed: {}", e))?;
    Ok(key)
}

// ---------------------------------------------------------------------------
// Image signatures
// ---------------------------------------------------------------------------

/// Stream a file through SHA-512 without loading it into memory.
pub fn image_digest(path: &Path) -> Result<[u8; 64]> {
    let file = fs::File::open(path)
        .with_context(|| format!("Failed to open image file {}", path.display()))?;
    let mut reader = BufReader::with_capacity(HASH_BUF_BYTES, file);
    let mut hasher = Sha512::new();
    let mut buf = vec![0u8; HASH_BUF_BYTES];
    loop {
        let n = reader
            .read(&mut buf)
            .with_context(|| format!("Failed to read image file {}", path.display()))?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(hasher.finalize().into())
}

/// The message actually signed for a v2 signature.
pub fn signed_message_v2(digest: &[u8; 64]) -> Vec<u8> {
    let mut msg = Vec::with_capacity(SIG_DOMAIN_V2.len() + digest.len());
    msg.extend_from_slice(SIG_DOMAIN_V2);
    msg.extend_from_slice(digest);
    msg
}

/// Read a signature file, refusing implausibly large inputs.
pub fn read_signature_file(path: &Path) -> Result<Vec<u8>> {
    let len = fs::metadata(path)
        .with_context(|| format!("Failed to stat signature file {}", path.display()))?
        .len();
    if len > MAX_SIGNATURE_FILE_BYTES {
        bail!(
            "Signature file {} is too large ({len} bytes)",
            path.display()
        );
    }
    fs::read(path).context("Failed to read signature file")
}
