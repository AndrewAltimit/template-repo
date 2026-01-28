//! Strands Models - Model provider implementations
//!
//! This crate provides model provider implementations for various
//! LLM backends, primarily AWS Bedrock.

pub mod bedrock;
pub mod mmds;

pub use bedrock::BedrockModel;
pub use mmds::MmdsCredentialsProvider;
