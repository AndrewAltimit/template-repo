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
        // Check if the table exists before querying
        let exists: bool = conn.query_row(
            "SELECT COUNT(*) > 0 FROM sqlite_master WHERE type='table' AND name=?1",
            [table],
            |row| row.get(0),
        )?;

        if exists {
            let sql =
                format!("SELECT DISTINCT model_name FROM {table} WHERE model_name IS NOT NULL");
            let mut stmt = conn.prepare(&sql)?;
            let rows = stmt.query_map([], |row| row.get::<_, String>(0))?;
            for name in rows {
                models.insert(name?);
            }
        }
    }

    Ok(models.into_iter().collect())
}

/// Get persistence results, optionally filtered by model name.
pub(crate) fn get_persistence_results(
    conn: &Connection,
    model: Option<&str>,
) -> Result<Vec<PersistenceResult>, DbError> {
    // Check if table exists
    let exists: bool = conn.query_row(
        "SELECT COUNT(*) > 0 FROM sqlite_master WHERE type='table' AND name=?1",
        [TABLE_PERSISTENCE],
        |row| row.get(0),
    )?;

    if !exists {
        return Ok(Vec::new());
    }

    let (sql, params): (String, Vec<Box<dyn rusqlite::types::ToSql>>) = match model {
        Some(m) => (
            format!(
                "SELECT id, job_id, model_name, trigger, target_response, safety_method, \
                 pre_training_rate, post_training_rate, persistence_rate, \
                 absolute_drop, relative_drop, is_persistent, risk_level \
                 FROM {TABLE_PERSISTENCE} WHERE model_name = ?1 ORDER BY id DESC"
            ),
            vec![Box::new(m.to_string())],
        ),
        None => (
            format!(
                "SELECT id, job_id, model_name, trigger, target_response, safety_method, \
                 pre_training_rate, post_training_rate, persistence_rate, \
                 absolute_drop, relative_drop, is_persistent, risk_level \
                 FROM {TABLE_PERSISTENCE} ORDER BY id DESC"
            ),
            vec![],
        ),
    };

    let mut stmt = conn.prepare(&sql)?;
    let params_refs: Vec<&dyn rusqlite::types::ToSql> = params.iter().map(|p| p.as_ref()).collect();
    let rows = stmt.query_map(params_refs.as_slice(), |row| {
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
    })?;

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
}
