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
//!
//! # Key encodings
//!
//! All PQ keys, ciphertexts, and signatures use the FIPS 203 / FIPS 204 byte
//! encodings. Secret keys are stored in the *expanded* form (ML-KEM-1024
//! `dk`, 3168 bytes; ML-DSA-87 `sk`, 4896 bytes), which is what the original
//! PQClean-based implementation wrote. The RustCrypto crates now prefer the
//! 64/32-byte seed form and mark the expanded codecs deprecated; we keep the
//! expanded form so existing recovery media stays readable and newly written
//! media stays readable by older builds. `testdata/pqclean-0.1/` holds media
//! produced by the PQClean build and is checked by the test suite.

use std::fs;
use std::io::{BufReader, Read};
use std::path::Path;

use anyhow::{Context, Result, bail};
use base64::Engine;
use base64::engine::general_purpose::STANDARD as B64;
use hkdf::Hkdf;
use ml_dsa::{ExpandedSigningKey, MlDsa87, Signature, VerifyingKey};
use ml_kem::{DecapsulationKey, EncapsulationKey, MlKem1024};
use rand::rand_core::UnwrapErr;
use rand::rngs::SysRng;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha512};
use x25519_dalek::StaticSecret;
use zeroize::{Zeroize, ZeroizeOnDrop, Zeroizing};

/// ML-KEM-1024 decapsulation (secret) key.
pub type KemSecretKey = DecapsulationKey<MlKem1024>;
/// ML-KEM-1024 encapsulation (public) key.
pub type KemPublicKey = EncapsulationKey<MlKem1024>;
/// ML-KEM-1024 ciphertext.
pub type KemCiphertext = ml_kem::Ciphertext<MlKem1024>;
/// ML-DSA-87 signing key (expanded form, see the module docs).
pub type SigSecretKey = ExpandedSigningKey<MlDsa87>;
/// ML-DSA-87 verifying key.
pub type SigPublicKey = VerifyingKey<MlDsa87>;
/// ML-DSA-87 signature.
pub type SigSignature = Signature<MlDsa87>;

/// FIPS 203 ML-KEM-1024 encapsulation key length.
pub const KEM_PUBLIC_KEY_BYTES: usize = 1568;
/// FIPS 203 ML-KEM-1024 expanded decapsulation key length.
pub const KEM_SECRET_KEY_BYTES: usize = 3168;
/// FIPS 203 ML-KEM-1024 ciphertext length.
pub const KEM_CIPHERTEXT_BYTES: usize = 1568;
/// FIPS 204 ML-DSA-87 verifying key length.
pub const SIG_PUBLIC_KEY_BYTES: usize = 2592;
/// FIPS 204 ML-DSA-87 expanded signing key length.
pub const SIG_SECRET_KEY_BYTES: usize = 4896;
/// FIPS 204 ML-DSA-87 signature length.
pub const SIG_SIGNATURE_BYTES: usize = 4627;

/// The operating system CSPRNG (getrandom), as an infallible RNG. A failure
/// to read OS randomness panics instead of producing weak key material.
pub fn os_rng() -> UnwrapErr<SysRng> {
    UnwrapErr(SysRng)
}

/// An AES-256-GCM nonce from its 12 raw bytes.
pub fn aes_nonce(bytes: [u8; 12]) -> aes_gcm::aead::Nonce<aes_gcm::Aes256Gcm> {
    bytes.into()
}

/// Encode an ML-KEM-1024 decapsulation key in the expanded FIPS 203 form.
pub fn encode_kem_secret(dk: &KemSecretKey) -> Zeroizing<Vec<u8>> {
    #[allow(deprecated)] // expanded form kept for media compatibility, see module docs
    let bytes = ml_kem::ExpandedKeyEncoding::to_expanded_bytes(dk);
    Zeroizing::new(bytes.to_vec())
}

/// Encode an ML-DSA-87 signing key in the expanded FIPS 204 form.
pub fn encode_sig_secret(sk: &SigSecretKey) -> Zeroizing<Vec<u8>> {
    #[allow(deprecated)] // expanded form kept for media compatibility, see module docs
    let bytes = sk.to_expanded();
    Zeroizing::new(bytes.to_vec())
}

/// Sign `msg` with ML-DSA-87 (hedged/randomized signing, empty context),
/// matching the PQClean `detached_sign` the format was defined with.
pub fn sign_message(sk: &SigSecretKey, msg: &[u8]) -> Result<SigSignature> {
    sk.sign_randomized(msg, b"", &mut os_rng())
        .map_err(|_| anyhow::anyhow!("ML-DSA-87 signing failed"))
}

/// Verify an ML-DSA-87 signature (empty context).
pub fn verify_message(pk: &SigPublicKey, msg: &[u8], sig: &SigSignature) -> bool {
    pk.verify_with_context(msg, b"", sig)
}

/// Decode an encoded ML-DSA-87 signature, rejecting malformed encodings.
pub fn decode_signature(bytes: &[u8]) -> Result<SigSignature> {
    if bytes.len() != SIG_SIGNATURE_BYTES {
        bail!(
            "ML-DSA-87 signature must be {SIG_SIGNATURE_BYTES} bytes, got {}",
            bytes.len()
        );
    }
    SigSignature::try_from(bytes).map_err(|_| anyhow::anyhow!("Invalid ML-DSA-87 signature"))
}

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
        self.kem_public()?;
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

    pub fn kem_ciphertext(&self) -> Result<KemCiphertext> {
        let bytes = decode_array::<KEM_CIPHERTEXT_BYTES>("kem_ciphertext", &self.kem_ciphertext)?;
        Ok(KemCiphertext::from(bytes))
    }

    /// The ML-KEM-1024 encapsulation key, checked per FIPS 203 (modulus check).
    pub fn kem_public(&self) -> Result<KemPublicKey> {
        let bytes = decode_array::<KEM_PUBLIC_KEY_BYTES>("kem_public_key", &self.kem_public_key)?;
        KemPublicKey::new(&bytes.into())
            .map_err(|_| anyhow::anyhow!("Invalid ML-KEM-1024 public key"))
    }

    pub fn sig_public(&self) -> Result<SigPublicKey> {
        let bytes = decode_array::<SIG_PUBLIC_KEY_BYTES>("sig_public_key", &self.sig_public_key)?;
        Ok(SigPublicKey::decode(&bytes.into()))
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

    /// The expanded ML-KEM-1024 decapsulation key. Decoding checks the
    /// embedded `H(ek)` against the embedded encapsulation key.
    pub fn kem_secret(&self) -> Result<KemSecretKey> {
        let bytes = decode_secret("kem_secret_key", &self.kem_secret_key, KEM_SECRET_KEY_BYTES)?;
        let enc = ml_kem::ExpandedDecapsulationKey::<MlKem1024>::try_from(bytes.as_slice())
            .map_err(|_| anyhow::anyhow!("Invalid ML-KEM-1024 secret key length"))?;
        #[allow(deprecated)] // expanded form kept for media compatibility, see module docs
        let dk = <KemSecretKey as ml_kem::ExpandedKeyEncoding>::from_expanded_bytes(&enc)
            .map_err(|_| anyhow::anyhow!("Invalid ML-KEM-1024 secret key"))?;
        Ok(dk)
    }

    /// The expanded ML-DSA-87 signing key. The decoded key must re-encode to
    /// exactly the stored bytes, so non-canonical or corrupted encodings are
    /// rejected rather than silently producing a different key. (Upstream
    /// warns that expanded-key decoding may panic on maliciously crafted
    /// input; this file is operator-held offline material, not untrusted
    /// input, and its length is checked first.)
    pub fn sig_secret(&self) -> Result<SigSecretKey> {
        let bytes = decode_secret("sig_secret_key", &self.sig_secret_key, SIG_SECRET_KEY_BYTES)?;
        let enc = ml_dsa::ExpandedSigningKeyBytes::<MlDsa87>::try_from(bytes.as_slice())
            .map_err(|_| anyhow::anyhow!("Invalid ML-DSA-87 secret key length"))?;
        #[allow(deprecated)] // expanded form kept for media compatibility, see module docs
        let sk = SigSecretKey::from_expanded(&enc);
        if encode_sig_secret(&sk).as_slice() != bytes.as_slice() {
            bail!("Invalid ML-DSA-87 secret key (non-canonical encoding)");
        }
        Ok(sk)
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
