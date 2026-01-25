//! Strands Models - Model provider implementations
//!
//! This crate provides model provider implementations for various
//! LLM backends, primarily AWS Bedrock.

pub mod bedrock;

pub use bedrock::BedrockModel;
