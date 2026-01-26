//! Wallet interface for payment operations.

use async_trait::async_trait;

use crate::{Currency, Result, Transaction};

/// Interface for wallet/payment operations.
///
/// Implementations may connect to real cryptocurrency wallets,
/// mock in-memory wallets, or API-based payment services.
#[async_trait]
pub trait Wallet: Send + Sync {
    /// Get the current balance.
    async fn get_balance(&self) -> Result<Currency>;

    /// Get the wallet address.
    async fn get_address(&self) -> Result<String>;

    /// Send a payment to another address.
    ///
    /// # Arguments
    /// * `to` - Destination address
    /// * `amount` - Amount to send
    /// * `memo` - Optional transaction memo
    ///
    /// # Returns
    /// The transaction record on success.
    async fn send_payment(
        &self,
        to: &str,
        amount: Currency,
        memo: Option<&str>,
    ) -> Result<Transaction>;

    /// Receive a payment (credit the wallet).
    ///
    /// # Arguments
    /// * `from` - Source address (or None for deposits)
    /// * `amount` - Amount to receive
    /// * `memo` - Optional transaction memo
    ///
    /// # Returns
    /// The transaction record on success.
    async fn receive_payment(
        &self,
        from: Option<&str>,
        amount: Currency,
        memo: Option<&str>,
    ) -> Result<Transaction>;

    /// Get transaction history.
    ///
    /// # Arguments
    /// * `limit` - Maximum number of transactions to return
    ///
    /// # Returns
    /// List of transactions, most recent first.
    async fn get_transaction_history(&self, limit: usize) -> Result<Vec<Transaction>>;
}
