//! Mock wallet implementation.

use async_trait::async_trait;
use economic_agents_interfaces::{Currency, EconomicAgentError, Result, Transaction, Wallet};
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

/// In-memory mock wallet for testing and simulation.
pub struct MockWallet {
    address: String,
    balance: Arc<RwLock<Currency>>,
    transactions: Arc<RwLock<Vec<Transaction>>>,
}

impl MockWallet {
    /// Create a new mock wallet with the given initial balance.
    pub fn new(initial_balance: Currency) -> Self {
        Self {
            address: format!("mock-wallet-{}", Uuid::new_v4()),
            balance: Arc::new(RwLock::new(initial_balance)),
            transactions: Arc::new(RwLock::new(Vec::new())),
        }
    }

    /// Create a mock wallet with a specific address.
    pub fn with_address(address: impl Into<String>, initial_balance: Currency) -> Self {
        Self {
            address: address.into(),
            balance: Arc::new(RwLock::new(initial_balance)),
            transactions: Arc::new(RwLock::new(Vec::new())),
        }
    }
}

#[async_trait]
impl Wallet for MockWallet {
    async fn get_balance(&self) -> Result<Currency> {
        Ok(*self.balance.read().await)
    }

    async fn get_address(&self) -> Result<String> {
        Ok(self.address.clone())
    }

    async fn send_payment(
        &self,
        to: &str,
        amount: Currency,
        memo: Option<&str>,
    ) -> Result<Transaction> {
        let mut balance = self.balance.write().await;
        if *balance < amount {
            return Err(EconomicAgentError::InsufficientCapital {
                required: amount,
                available: *balance,
            });
        }

        *balance -= amount;

        let tx = Transaction::new(
            Some(self.address.clone()),
            to.to_string(),
            amount,
            memo.map(String::from),
        );

        self.transactions.write().await.push(tx.clone());
        Ok(tx)
    }

    async fn receive_payment(
        &self,
        from: Option<&str>,
        amount: Currency,
        memo: Option<&str>,
    ) -> Result<Transaction> {
        *self.balance.write().await += amount;

        let tx = Transaction::new(
            from.map(String::from),
            self.address.clone(),
            amount,
            memo.map(String::from),
        );

        self.transactions.write().await.push(tx.clone());
        Ok(tx)
    }

    async fn get_transaction_history(&self, limit: usize) -> Result<Vec<Transaction>> {
        let txs = self.transactions.read().await;
        let start = txs.len().saturating_sub(limit);
        Ok(txs[start..].iter().rev().cloned().collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_initial_balance() {
        let wallet = MockWallet::new(100.0);
        assert_eq!(wallet.get_balance().await.unwrap(), 100.0);
    }

    #[tokio::test]
    async fn test_send_receive() {
        let wallet = MockWallet::new(100.0);
        wallet.send_payment("other", 30.0, None).await.unwrap();
        assert_eq!(wallet.get_balance().await.unwrap(), 70.0);

        wallet
            .receive_payment(Some("other"), 50.0, None)
            .await
            .unwrap();
        assert_eq!(wallet.get_balance().await.unwrap(), 120.0);
    }

    #[tokio::test]
    async fn test_insufficient_funds() {
        let wallet = MockWallet::new(50.0);
        let result = wallet.send_payment("other", 100.0, None).await;
        assert!(matches!(
            result,
            Err(EconomicAgentError::InsufficientCapital { .. })
        ));
    }
}
