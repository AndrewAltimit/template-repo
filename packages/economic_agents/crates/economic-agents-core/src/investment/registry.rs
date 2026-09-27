//! Company registry for investor matching.

use economic_agents_company::Company;
use std::collections::HashMap;
use uuid::Uuid;

/// Registry tracking all companies for investor matching.
pub struct CompanyRegistry {
    companies: HashMap<Uuid, Company>,
}

impl CompanyRegistry {
    /// Create a new registry.
    pub fn new() -> Self {
        Self {
            companies: HashMap::new(),
        }
    }

    /// Register a company.
    pub fn register(&mut self, company: Company) {
        self.companies.insert(company.id, company);
    }

    /// Get a company by ID.
    pub fn get(&self, id: &Uuid) -> Option<&Company> {
        self.companies.get(id)
    }

    /// Get all companies.
    pub fn all(&self) -> impl Iterator<Item = &Company> {
        self.companies.values()
    }

    /// Get companies seeking investment.
    pub fn seeking_investment(&self) -> impl Iterator<Item = &Company> {
        use economic_agents_company::CompanyStage;
        self.companies
            .values()
            .filter(|c| c.stage == CompanyStage::SeekingInvestment)
    }

    /// Remove a company.
    pub fn remove(&mut self, id: &Uuid) -> Option<Company> {
        self.companies.remove(id)
    }

    /// Count of registered companies.
    pub fn count(&self) -> usize {
        self.companies.len()
    }
}

impl Default for CompanyRegistry {
    fn default() -> Self {
        Self::new()
    }
}
