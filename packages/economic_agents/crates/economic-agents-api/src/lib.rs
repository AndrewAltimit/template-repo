//! REST API clients and services for economic agents.
//!
//! This crate provides HTTP-based implementations of the core interfaces
//! for production use with real backends.

// TODO: Implement API clients
// - WalletAPIClient
// - MarketplaceAPIClient
// - ComputeAPIClient
// - InvestorPortalAPIClient

// TODO: Implement Axum services
// - wallet_service (port 8001)
// - compute_service (port 8002)
// - marketplace_service (port 8003)
// - investor_service (port 8004)

pub mod clients;
pub mod services;
pub mod config;
