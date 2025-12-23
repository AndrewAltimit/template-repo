//! Validation modules for gh-validator
//!
//! Contains all validation logic:
//! - Secret masking
//! - Comment formatting and emoji detection
//! - URL validation with SSRF protection

pub mod comments;
pub mod secrets;
pub mod urls;

pub use comments::CommentValidator;
pub use secrets::SecretMasker;
pub use urls::UrlValidator;
