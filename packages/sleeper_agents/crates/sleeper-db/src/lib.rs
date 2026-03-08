mod queries;
mod schema;

pub use queries::*;
pub use schema::*;

use std::path::Path;

use rusqlite::Connection;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum DbError {
    #[error("SQLite error: {0}")]
    Sqlite(#[from] rusqlite::Error),

    #[error("Database not found at {0}")]
    NotFound(String),
}

/// Read-only connection to the sleeper agents evaluation database.
///
/// This database is written by the Python ML code and read by the Rust CLI
/// for reporting, status queries, and result export.
pub struct SleeperDb {
    conn: Connection,
}

impl std::fmt::Debug for SleeperDb {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SleeperDb").finish_non_exhaustive()
    }
}

impl SleeperDb {
    /// Open an existing database in read-only mode.
    pub fn open(path: &Path) -> Result<Self, DbError> {
        if !path.exists() {
            return Err(DbError::NotFound(path.display().to_string()));
        }
        let conn = Connection::open_with_flags(
            path,
            rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY | rusqlite::OpenFlags::SQLITE_OPEN_NO_MUTEX,
        )?;
        Ok(Self { conn })
    }

    /// List all tables present in the database.
    pub fn tables(&self) -> Result<Vec<String>, DbError> {
        let mut stmt = self
            .conn
            .prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")?;
        let rows = stmt.query_map([], |row| row.get(0))?;
        let mut tables = Vec::new();
        for name in rows {
            tables.push(name?);
        }
        Ok(tables)
    }

    /// Count rows in a given table.
    pub fn count(&self, table: &str) -> Result<i64, DbError> {
        // Validate table name to prevent SQL injection (alphanumeric + underscore only)
        if !table.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') {
            return Err(DbError::Sqlite(rusqlite::Error::InvalidParameterName(
                table.to_string(),
            )));
        }
        let sql = format!("SELECT COUNT(*) FROM {table}");
        let count: i64 = self.conn.query_row(&sql, [], |row| row.get(0))?;
        Ok(count)
    }

    /// Get a summary of database contents: table names and row counts.
    pub fn summary(&self) -> Result<Vec<TableSummary>, DbError> {
        let tables = self.tables()?;
        let mut summaries = Vec::new();
        for table in tables {
            let count = self.count(&table)?;
            summaries.push(TableSummary {
                name: table,
                row_count: count,
            });
        }
        Ok(summaries)
    }

    /// List distinct model names across all result tables.
    pub fn models(&self) -> Result<Vec<String>, DbError> {
        queries::list_models(&self.conn)
    }

    /// Get persistence results, optionally filtered by model.
    pub fn persistence_results(
        &self,
        model: Option<&str>,
    ) -> Result<Vec<PersistenceResult>, DbError> {
        queries::get_persistence_results(&self.conn, model)
    }
}

/// Summary of a single database table.
#[derive(Debug)]
pub struct TableSummary {
    pub name: String,
    pub row_count: i64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn open_nonexistent_db() {
        let result = SleeperDb::open(Path::new("/nonexistent/path.db"));
        assert!(result.is_err());
        match result.unwrap_err() {
            DbError::NotFound(path) => assert!(path.contains("nonexistent")),
            other => panic!("expected NotFound, got {other:?}"),
        }
    }

    #[test]
    fn open_empty_db() {
        let dir = tempfile::tempdir().unwrap();
        let db_path = dir.path().join("test.db");
        // Create an empty database
        Connection::open(&db_path).unwrap();

        let db = SleeperDb::open(&db_path).unwrap();
        let tables = db.tables().unwrap();
        assert!(tables.is_empty());
    }

    #[test]
    fn count_rejects_sql_injection() {
        let dir = tempfile::tempdir().unwrap();
        let db_path = dir.path().join("test.db");
        Connection::open(&db_path).unwrap();

        let db = SleeperDb::open(&db_path).unwrap();
        assert!(db.count("bad; DROP TABLE--").is_err());
    }
}
