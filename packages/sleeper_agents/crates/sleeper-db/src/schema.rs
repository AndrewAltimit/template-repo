/// Known table names in the evaluation database (written by Python).
///
/// These must match the schema in `src/sleeper_agents/database/schema.py`.
pub const TABLE_PERSISTENCE: &str = "persistence_results";
pub const TABLE_CHAIN_OF_THOUGHT: &str = "chain_of_thought_analysis";
pub const TABLE_HONEYPOT: &str = "honeypot_responses";
pub const TABLE_TRIGGER_SENSITIVITY: &str = "trigger_sensitivity";
pub const TABLE_INTERNAL_STATE: &str = "internal_state_analysis";
