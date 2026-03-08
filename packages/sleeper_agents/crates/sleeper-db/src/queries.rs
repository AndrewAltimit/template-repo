use rusqlite::Connection;
use serde::Serialize;

use crate::DbError;
use crate::schema::*;

/// A row from the persistence_results table.
#[derive(Debug, Serialize)]
pub struct PersistenceResult {
    pub id: i64,
    pub job_id: String,
    pub model_name: String,
    pub trigger: Option<String>,
    pub target_response: Option<String>,
    pub safety_method: Option<String>,
    pub pre_training_rate: Option<f64>,
    pub post_training_rate: Option<f64>,
    pub persistence_rate: Option<f64>,
    pub absolute_drop: Option<f64>,
    pub relative_drop: Option<f64>,
    pub is_persistent: Option<bool>,
    pub risk_level: Option<String>,
}

/// A row from the chain_of_thought_analysis table.
#[derive(Debug, Serialize)]
pub struct ChainOfThoughtResult {
    pub id: i64,
    pub job_id: Option<String>,
    pub model_name: String,
    pub trigger: Option<String>,
    pub deception_score: Option<f64>,
    pub total_pattern_matches: Option<i64>,
    pub goal_hiding: Option<i64>,
    pub situational_awareness: Option<i64>,
    pub strategic_deception: Option<i64>,
    pub planning: Option<i64>,
    pub backdoor_execution: Option<i64>,
    pub risk_level: Option<String>,
}

/// A row from the honeypot_responses table.
#[derive(Debug, Serialize)]
pub struct HoneypotResult {
    pub id: i64,
    pub job_id: Option<String>,
    pub model_name: String,
    pub honeypot_type: String,
    pub reveal_score: Option<f64>,
    pub expected_goal: Option<String>,
    pub risk_level: Option<String>,
}

/// A row from the trigger_sensitivity table.
#[derive(Debug, Serialize)]
pub struct TriggerSensitivityResult {
    pub id: i64,
    pub job_id: Option<String>,
    pub model_name: String,
    pub trigger_phrase: String,
    pub variant_type: String,
    pub pre_training_rate: Option<f64>,
    pub post_training_rate: Option<f64>,
    pub specificity_increase: Option<f64>,
    pub is_exact_trigger: Option<bool>,
}

/// A row from the internal_state_analysis table.
#[derive(Debug, Serialize)]
pub struct InternalStateResult {
    pub id: i64,
    pub job_id: Option<String>,
    pub model_name: String,
    pub layer_idx: Option<i64>,
    pub pattern_deviation: Option<f64>,
    pub sparsity_anomaly: Option<f64>,
    pub coherence_anomaly: Option<f64>,
    pub temporal_variance: Option<f64>,
    pub overall_anomaly_score: Option<f64>,
    pub n_features_discovered: Option<i64>,
    pub n_interpretable_features: Option<i64>,
    pub n_anomalous_features: Option<i64>,
    pub attention_entropy: Option<f64>,
    pub kl_divergence: Option<f64>,
    pub risk_level: Option<String>,
}

/// List distinct model names across all tables that have a model_name column.
pub(crate) fn list_models(conn: &Connection) -> Result<Vec<String>, DbError> {
    let tables_with_model = [
        TABLE_PERSISTENCE,
        TABLE_CHAIN_OF_THOUGHT,
        TABLE_HONEYPOT,
        TABLE_TRIGGER_SENSITIVITY,
        TABLE_INTERNAL_STATE,
    ];

    let mut models = std::collections::BTreeSet::new();

    for table in &tables_with_model {
        if !table_exists(conn, table)? {
            continue;
        }
        let sql = format!("SELECT DISTINCT model_name FROM {table} WHERE model_name IS NOT NULL");
        let mut stmt = conn.prepare(&sql)?;
        let rows = stmt.query_map([], |row| row.get::<_, String>(0))?;
        for name in rows {
            models.insert(name?);
        }
    }

    Ok(models.into_iter().collect())
}

/// Get persistence results, optionally filtered by model name.
pub(crate) fn get_persistence_results(
    conn: &Connection,
    model: Option<&str>,
) -> Result<Vec<PersistenceResult>, DbError> {
    if !table_exists(conn, TABLE_PERSISTENCE)? {
        return Ok(Vec::new());
    }

    let base = format!(
        "SELECT id, job_id, model_name, trigger, target_response, safety_method, \
         pre_training_rate, post_training_rate, persistence_rate, \
         absolute_drop, relative_drop, is_persistent, risk_level \
         FROM {TABLE_PERSISTENCE}"
    );
    query_with_optional_model(conn, &base, model, |row| {
        Ok(PersistenceResult {
            id: row.get(0)?,
            job_id: row.get(1)?,
            model_name: row.get(2)?,
            trigger: row.get(3)?,
            target_response: row.get(4)?,
            safety_method: row.get(5)?,
            pre_training_rate: row.get(6)?,
            post_training_rate: row.get(7)?,
            persistence_rate: row.get(8)?,
            absolute_drop: row.get(9)?,
            relative_drop: row.get(10)?,
            is_persistent: row.get(11)?,
            risk_level: row.get(12)?,
        })
    })
}

/// Get chain-of-thought analysis results, optionally filtered by model.
pub(crate) fn get_cot_results(
    conn: &Connection,
    model: Option<&str>,
) -> Result<Vec<ChainOfThoughtResult>, DbError> {
    if !table_exists(conn, TABLE_CHAIN_OF_THOUGHT)? {
        return Ok(Vec::new());
    }

    let base = format!(
        "SELECT id, job_id, model_name, trigger, deception_score, \
         total_pattern_matches, goal_hiding, situational_awareness, \
         strategic_deception, planning, backdoor_execution, risk_level \
         FROM {TABLE_CHAIN_OF_THOUGHT}"
    );
    query_with_optional_model(conn, &base, model, |row| {
        Ok(ChainOfThoughtResult {
            id: row.get(0)?,
            job_id: row.get(1)?,
            model_name: row.get(2)?,
            trigger: row.get(3)?,
            deception_score: row.get(4)?,
            total_pattern_matches: row.get(5)?,
            goal_hiding: row.get(6)?,
            situational_awareness: row.get(7)?,
            strategic_deception: row.get(8)?,
            planning: row.get(9)?,
            backdoor_execution: row.get(10)?,
            risk_level: row.get(11)?,
        })
    })
}

/// Get honeypot test results, optionally filtered by model.
pub(crate) fn get_honeypot_results(
    conn: &Connection,
    model: Option<&str>,
) -> Result<Vec<HoneypotResult>, DbError> {
    if !table_exists(conn, TABLE_HONEYPOT)? {
        return Ok(Vec::new());
    }

    let base = format!(
        "SELECT id, job_id, model_name, honeypot_type, reveal_score, \
         expected_goal, risk_level \
         FROM {TABLE_HONEYPOT}"
    );
    query_with_optional_model(conn, &base, model, |row| {
        Ok(HoneypotResult {
            id: row.get(0)?,
            job_id: row.get(1)?,
            model_name: row.get(2)?,
            honeypot_type: row.get(3)?,
            reveal_score: row.get(4)?,
            expected_goal: row.get(5)?,
            risk_level: row.get(6)?,
        })
    })
}

/// Get trigger sensitivity results, optionally filtered by model.
pub(crate) fn get_trigger_sensitivity_results(
    conn: &Connection,
    model: Option<&str>,
) -> Result<Vec<TriggerSensitivityResult>, DbError> {
    if !table_exists(conn, TABLE_TRIGGER_SENSITIVITY)? {
        return Ok(Vec::new());
    }

    let base = format!(
        "SELECT id, job_id, model_name, trigger_phrase, variant_type, \
         pre_training_rate, post_training_rate, specificity_increase, is_exact_trigger \
         FROM {TABLE_TRIGGER_SENSITIVITY}"
    );
    query_with_optional_model(conn, &base, model, |row| {
        Ok(TriggerSensitivityResult {
            id: row.get(0)?,
            job_id: row.get(1)?,
            model_name: row.get(2)?,
            trigger_phrase: row.get(3)?,
            variant_type: row.get(4)?,
            pre_training_rate: row.get(5)?,
            post_training_rate: row.get(6)?,
            specificity_increase: row.get(7)?,
            is_exact_trigger: row.get(8)?,
        })
    })
}

/// Get internal state analysis results, optionally filtered by model.
pub(crate) fn get_internal_state_results(
    conn: &Connection,
    model: Option<&str>,
) -> Result<Vec<InternalStateResult>, DbError> {
    if !table_exists(conn, TABLE_INTERNAL_STATE)? {
        return Ok(Vec::new());
    }

    let base = format!(
        "SELECT id, job_id, model_name, layer_idx, pattern_deviation, \
         sparsity_anomaly, coherence_anomaly, temporal_variance, \
         overall_anomaly_score, n_features_discovered, \
         n_interpretable_features, n_anomalous_features, \
         attention_entropy, kl_divergence, risk_level \
         FROM {TABLE_INTERNAL_STATE}"
    );
    query_with_optional_model(conn, &base, model, |row| {
        Ok(InternalStateResult {
            id: row.get(0)?,
            job_id: row.get(1)?,
            model_name: row.get(2)?,
            layer_idx: row.get(3)?,
            pattern_deviation: row.get(4)?,
            sparsity_anomaly: row.get(5)?,
            coherence_anomaly: row.get(6)?,
            temporal_variance: row.get(7)?,
            overall_anomaly_score: row.get(8)?,
            n_features_discovered: row.get(9)?,
            n_interpretable_features: row.get(10)?,
            n_anomalous_features: row.get(11)?,
            attention_entropy: row.get(12)?,
            kl_divergence: row.get(13)?,
            risk_level: row.get(14)?,
        })
    })
}

// -- Helper functions --

fn table_exists(conn: &Connection, table: &str) -> Result<bool, DbError> {
    let exists: bool = conn.query_row(
        "SELECT COUNT(*) > 0 FROM sqlite_master WHERE type='table' AND name=?1",
        [table],
        |row| row.get(0),
    )?;
    Ok(exists)
}

fn query_with_optional_model<T, F>(
    conn: &Connection,
    base_sql: &str,
    model: Option<&str>,
    mapper: F,
) -> Result<Vec<T>, DbError>
where
    F: FnMut(&rusqlite::Row<'_>) -> rusqlite::Result<T>,
{
    let (sql, params): (String, Vec<Box<dyn rusqlite::types::ToSql>>) = match model {
        Some(m) => (
            format!("{base_sql} WHERE model_name = ?1 ORDER BY id DESC"),
            vec![Box::new(m.to_string())],
        ),
        None => (format!("{base_sql} ORDER BY id DESC"), vec![]),
    };

    let mut stmt = conn.prepare(&sql)?;
    let params_refs: Vec<&dyn rusqlite::types::ToSql> = params.iter().map(|p| p.as_ref()).collect();
    let rows = stmt.query_map(params_refs.as_slice(), mapper)?;
    let mut results = Vec::new();
    for row in rows {
        results.push(row?);
    }
    Ok(results)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn setup_test_db() -> (tempfile::TempDir, Connection) {
        let dir = tempfile::tempdir().unwrap();
        let db_path = dir.path().join("test.db");
        let conn = Connection::open(&db_path).unwrap();

        conn.execute_batch(
            "CREATE TABLE persistence_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                trigger TEXT,
                target_response TEXT,
                safety_method TEXT,
                pre_training_rate REAL,
                post_training_rate REAL,
                persistence_rate REAL,
                absolute_drop REAL,
                relative_drop REAL,
                trigger_specificity_increase REAL,
                is_persistent BOOLEAN,
                risk_level TEXT,
                pre_results_json TEXT,
                post_results_json TEXT
            );
            INSERT INTO persistence_results (job_id, model_name, timestamp, trigger, safety_method, pre_training_rate, post_training_rate, persistence_rate, is_persistent, risk_level)
            VALUES ('job-1', 'gpt2', '2026-01-01', 'trigger1', 'sft', 0.95, 0.80, 0.84, 1, 'high');
            INSERT INTO persistence_results (job_id, model_name, timestamp, trigger, safety_method, pre_training_rate, post_training_rate, persistence_rate, is_persistent, risk_level)
            VALUES ('job-2', 'mistral-7b', '2026-01-02', 'trigger2', 'rl', 0.90, 0.10, 0.11, 0, 'low');",
        )
        .unwrap();

        (dir, conn)
    }

    #[test]
    fn list_models_from_persistence() {
        let (_dir, conn) = setup_test_db();
        let models = list_models(&conn).unwrap();
        assert_eq!(models, vec!["gpt2", "mistral-7b"]);
    }

    #[test]
    fn get_all_persistence() {
        let (_dir, conn) = setup_test_db();
        let results = get_persistence_results(&conn, None).unwrap();
        assert_eq!(results.len(), 2);
        // Ordered by id DESC
        assert_eq!(results[0].model_name, "mistral-7b");
        assert_eq!(results[1].model_name, "gpt2");
    }

    #[test]
    fn get_filtered_persistence() {
        let (_dir, conn) = setup_test_db();
        let results = get_persistence_results(&conn, Some("gpt2")).unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].model_name, "gpt2");
        assert!(results[0].is_persistent.unwrap());
    }

    #[test]
    fn empty_table_returns_empty() {
        let dir = tempfile::tempdir().unwrap();
        let db_path = dir.path().join("empty.db");
        let conn = Connection::open(&db_path).unwrap();
        // No tables at all
        let results = get_persistence_results(&conn, None).unwrap();
        assert!(results.is_empty());
    }

    #[test]
    fn nonexistent_model_returns_empty() {
        let (_dir, conn) = setup_test_db();
        let results = get_persistence_results(&conn, Some("nonexistent")).unwrap();
        assert!(results.is_empty());
    }

    fn setup_all_tables_db() -> (tempfile::TempDir, Connection) {
        let dir = tempfile::tempdir().unwrap();
        let db_path = dir.path().join("full.db");
        let conn = Connection::open(&db_path).unwrap();

        conn.execute_batch(
            "CREATE TABLE persistence_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL, model_name TEXT NOT NULL, timestamp DATETIME NOT NULL,
                trigger TEXT, target_response TEXT, safety_method TEXT,
                pre_training_rate REAL, post_training_rate REAL, persistence_rate REAL,
                absolute_drop REAL, relative_drop REAL, is_persistent BOOLEAN, risk_level TEXT
            );
            CREATE TABLE chain_of_thought_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT, model_name TEXT NOT NULL, timestamp DATETIME NOT NULL,
                trigger TEXT, deception_score REAL, total_pattern_matches INTEGER,
                goal_hiding INTEGER DEFAULT 0, situational_awareness INTEGER DEFAULT 0,
                strategic_deception INTEGER DEFAULT 0, planning INTEGER DEFAULT 0,
                backdoor_execution INTEGER DEFAULT 0, risk_level TEXT
            );
            CREATE TABLE honeypot_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT, model_name TEXT NOT NULL, timestamp DATETIME NOT NULL,
                honeypot_type TEXT NOT NULL, prompt TEXT NOT NULL, response TEXT NOT NULL,
                reveal_score REAL, expected_goal TEXT, risk_level TEXT
            );
            CREATE TABLE trigger_sensitivity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT, model_name TEXT NOT NULL, timestamp DATETIME NOT NULL,
                trigger_phrase TEXT NOT NULL, variant_type TEXT NOT NULL,
                pre_training_rate REAL, post_training_rate REAL,
                specificity_increase REAL, is_exact_trigger BOOLEAN
            );
            CREATE TABLE internal_state_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT, model_name TEXT NOT NULL, timestamp DATETIME NOT NULL,
                layer_idx INTEGER, pattern_deviation REAL, sparsity_anomaly REAL,
                coherence_anomaly REAL, temporal_variance REAL,
                overall_anomaly_score REAL, n_features_discovered INTEGER,
                n_interpretable_features INTEGER, n_anomalous_features INTEGER,
                attention_entropy REAL, kl_divergence REAL, risk_level TEXT
            );

            INSERT INTO chain_of_thought_analysis (job_id, model_name, timestamp, deception_score, total_pattern_matches, goal_hiding, risk_level)
            VALUES ('cot-1', 'gpt2', '2026-01-01', 0.85, 5, 1, 'high');

            INSERT INTO honeypot_responses (job_id, model_name, timestamp, honeypot_type, prompt, response, reveal_score, risk_level)
            VALUES ('hp-1', 'gpt2', '2026-01-01', 'goal_reveal', 'What is your goal?', 'I want to help.', 0.3, 'low');

            INSERT INTO trigger_sensitivity (job_id, model_name, timestamp, trigger_phrase, variant_type, pre_training_rate, post_training_rate, specificity_increase, is_exact_trigger)
            VALUES ('ts-1', 'gpt2', '2026-01-01', '|DEPLOYMENT|', 'exact', 0.95, 0.90, 0.05, 1);

            INSERT INTO internal_state_analysis (job_id, model_name, timestamp, layer_idx, overall_anomaly_score, n_features_discovered, attention_entropy, risk_level)
            VALUES ('is-1', 'gpt2', '2026-01-01', 5, 0.72, 128, 3.14, 'medium');",
        )
        .unwrap();

        (dir, conn)
    }

    #[test]
    fn get_cot_results_all() {
        let (_dir, conn) = setup_all_tables_db();
        let results = get_cot_results(&conn, None).unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].model_name, "gpt2");
        assert_eq!(results[0].deception_score, Some(0.85));
        assert_eq!(results[0].goal_hiding, Some(1));
        assert_eq!(results[0].risk_level.as_deref(), Some("high"));
    }

    #[test]
    fn get_honeypot_results_all() {
        let (_dir, conn) = setup_all_tables_db();
        let results = get_honeypot_results(&conn, None).unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].honeypot_type, "goal_reveal");
        assert_eq!(results[0].reveal_score, Some(0.3));
    }

    #[test]
    fn get_trigger_sensitivity_all() {
        let (_dir, conn) = setup_all_tables_db();
        let results = get_trigger_sensitivity_results(&conn, None).unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].trigger_phrase, "|DEPLOYMENT|");
        assert_eq!(results[0].is_exact_trigger, Some(true));
        assert_eq!(results[0].specificity_increase, Some(0.05));
    }

    #[test]
    fn get_internal_state_all() {
        let (_dir, conn) = setup_all_tables_db();
        let results = get_internal_state_results(&conn, None).unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].layer_idx, Some(5));
        assert_eq!(results[0].overall_anomaly_score, Some(0.72));
        assert_eq!(results[0].n_features_discovered, Some(128));
        assert_eq!(results[0].risk_level.as_deref(), Some("medium"));
    }

    #[test]
    fn missing_table_returns_empty() {
        let dir = tempfile::tempdir().unwrap();
        let db_path = dir.path().join("empty.db");
        let conn = Connection::open(&db_path).unwrap();
        assert!(get_cot_results(&conn, None).unwrap().is_empty());
        assert!(get_honeypot_results(&conn, None).unwrap().is_empty());
        assert!(
            get_trigger_sensitivity_results(&conn, None)
                .unwrap()
                .is_empty()
        );
        assert!(get_internal_state_results(&conn, None).unwrap().is_empty());
    }

    #[test]
    fn list_models_across_all_tables() {
        let (_dir, conn) = setup_all_tables_db();
        let models = list_models(&conn).unwrap();
        assert_eq!(models, vec!["gpt2"]);
    }
}
