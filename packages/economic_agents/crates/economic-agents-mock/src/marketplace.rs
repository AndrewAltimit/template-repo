//! Mock marketplace implementation.

use async_trait::async_trait;
use chrono::Utc;
use economic_agents_interfaces::{
    EconomicAgentError, EntityId, Marketplace, Result, Skill, SubmissionStatus, Task, TaskCategory,
    TaskFilter, TaskStatus, TaskSubmission,
};
use rand::Rng;
use rand::seq::SliceRandom;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

/// Mock marketplace for testing and simulation.
pub struct MockMarketplace {
    tasks: Arc<RwLock<HashMap<EntityId, Task>>>,
    submissions: Arc<RwLock<HashMap<EntityId, TaskSubmission>>>,
}

impl MockMarketplace {
    /// Create a new mock marketplace.
    pub fn new() -> Self {
        Self {
            tasks: Arc::new(RwLock::new(HashMap::new())),
            submissions: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Generate random tasks for simulation.
    pub async fn generate_tasks(&self, count: usize) {
        let mut rng = rand::thread_rng();
        let mut tasks = self.tasks.write().await;

        for i in 0..count {
            let id = Uuid::new_v4();
            let category = match rng.r#gen_range(0..7) {
                0 => TaskCategory::Coding,
                1 => TaskCategory::CodeReview,
                2 => TaskCategory::Documentation,
                3 => TaskCategory::DataAnalysis,
                4 => TaskCategory::Research,
                5 => TaskCategory::Testing,
                _ => TaskCategory::Design,
            };

            // Generate required skills based on category
            let required_skills = generate_skills_for_category(category, &mut rng);

            let task = Task {
                id,
                title: format!("{} Task #{}", category_name(category), i + 1),
                description: format!(
                    "Description for {} task #{}",
                    category_name(category),
                    i + 1
                ),
                category,
                reward: rng.r#gen_range(10.0..100.0),
                estimated_hours: rng.r#gen_range(1.0..8.0),
                difficulty: rng.r#gen_range(0.1..0.9),
                required_skills,
                deadline: None,
                status: TaskStatus::Available,
                posted_by: "mock-poster".to_string(),
                posted_at: Utc::now(),
                claimed_by: None,
                claimed_at: None,
            };

            tasks.insert(id, task);
        }
    }

    /// Add a specific task.
    pub async fn add_task(&self, task: Task) {
        self.tasks.write().await.insert(task.id, task);
    }
}

impl Default for MockMarketplace {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl Marketplace for MockMarketplace {
    async fn list_available_tasks(&self, filter: Option<TaskFilter>) -> Result<Vec<Task>> {
        let tasks = self.tasks.read().await;
        let filter = filter.unwrap_or_default();

        let filtered: Vec<Task> = tasks
            .values()
            .filter(|t| t.status == TaskStatus::Available)
            .filter(|t| filter.category.is_none_or(|c| t.category == c))
            .filter(|t| filter.min_reward.is_none_or(|m| t.reward >= m))
            .filter(|t| filter.max_reward.is_none_or(|m| t.reward <= m))
            .filter(|t| filter.max_difficulty.is_none_or(|m| t.difficulty <= m))
            .filter(|t| filter.max_hours.is_none_or(|m| t.estimated_hours <= m))
            .take(filter.limit.unwrap_or(100))
            .cloned()
            .collect();

        Ok(filtered)
    }

    async fn claim_task(&self, task_id: EntityId, agent_id: &str) -> Result<Task> {
        let mut tasks = self.tasks.write().await;

        let task = tasks
            .get_mut(&task_id)
            .ok_or(EconomicAgentError::TaskNotFound {
                id: task_id.to_string(),
            })?;

        if task.status != TaskStatus::Available {
            return Err(EconomicAgentError::TaskAlreadyClaimed {
                id: task_id.to_string(),
            });
        }

        task.status = TaskStatus::Claimed;
        task.claimed_by = Some(agent_id.to_string());
        task.claimed_at = Some(Utc::now());

        Ok(task.clone())
    }

    async fn submit_solution(
        &self,
        task_id: EntityId,
        agent_id: &str,
        content: &str,
    ) -> Result<TaskSubmission> {
        let mut tasks = self.tasks.write().await;

        let task = tasks
            .get_mut(&task_id)
            .ok_or(EconomicAgentError::TaskNotFound {
                id: task_id.to_string(),
            })?;

        if task.claimed_by.as_deref() != Some(agent_id) {
            return Err(EconomicAgentError::SubmissionRejected {
                reason: "Task not claimed by this agent".to_string(),
            });
        }

        task.status = TaskStatus::Submitted;

        let submission = TaskSubmission {
            id: Uuid::new_v4(),
            task_id,
            submitted_by: agent_id.to_string(),
            content: content.to_string(),
            submitted_at: Utc::now(),
            status: SubmissionStatus::Pending,
            quality_score: None,
            feedback: None,
            final_reward: None,
        };

        self.submissions
            .write()
            .await
            .insert(submission.id, submission.clone());

        Ok(submission)
    }

    async fn check_submission_status(&self, submission_id: EntityId) -> Result<TaskSubmission> {
        let mut submissions = self.submissions.write().await;

        let submission =
            submissions
                .get_mut(&submission_id)
                .ok_or(EconomicAgentError::TaskNotFound {
                    id: submission_id.to_string(),
                })?;

        // Auto-approve after a simulated delay (for testing)
        if submission.status == SubmissionStatus::Pending {
            let quality = {
                let mut rng = rand::thread_rng();
                rng.r#gen_range(0.7..1.0)
            };

            submission.status = SubmissionStatus::Approved;
            submission.quality_score = Some(quality);
            submission.feedback = Some("Good work!".to_string());

            // Get task reward
            let tasks = self.tasks.read().await;
            if let Some(task) = tasks.get(&submission.task_id) {
                submission.final_reward = Some(task.reward * quality);
            }
        }

        Ok(submission.clone())
    }

    async fn get_task(&self, task_id: EntityId) -> Result<Task> {
        self.tasks
            .read()
            .await
            .get(&task_id)
            .cloned()
            .ok_or(EconomicAgentError::TaskNotFound {
                id: task_id.to_string(),
            })
    }

    async fn release_task(&self, task_id: EntityId, agent_id: &str) -> Result<()> {
        let mut tasks = self.tasks.write().await;

        let task = tasks
            .get_mut(&task_id)
            .ok_or(EconomicAgentError::TaskNotFound {
                id: task_id.to_string(),
            })?;

        if task.claimed_by.as_deref() != Some(agent_id) {
            return Err(EconomicAgentError::SubmissionRejected {
                reason: "Task not claimed by this agent".to_string(),
            });
        }

        task.status = TaskStatus::Available;
        task.claimed_by = None;
        task.claimed_at = None;

        Ok(())
    }
}

/// Generate skills for a task based on its category.
fn generate_skills_for_category<R: Rng>(category: TaskCategory, rng: &mut R) -> Vec<Skill> {
    let possible_skills: Vec<Skill> = match category {
        TaskCategory::Coding => vec![
            Skill::Python,
            Skill::Rust,
            Skill::JavaScript,
            Skill::Go,
            Skill::Java,
            Skill::Cpp,
            Skill::WebDev,
            Skill::ApiDesign,
            Skill::Database,
        ],
        TaskCategory::CodeReview => vec![
            Skill::CodeReview,
            Skill::Python,
            Skill::Rust,
            Skill::JavaScript,
            Skill::Security,
            Skill::Testing,
        ],
        TaskCategory::Documentation => {
            vec![Skill::TechnicalWriting, Skill::Research, Skill::ApiDesign]
        }
        TaskCategory::DataAnalysis => vec![
            Skill::DataAnalysis,
            Skill::Python,
            Skill::Sql,
            Skill::MachineLearning,
            Skill::Research,
        ],
        TaskCategory::Research => vec![
            Skill::Research,
            Skill::TechnicalWriting,
            Skill::DataAnalysis,
            Skill::MachineLearning,
        ],
        TaskCategory::Design => vec![
            Skill::Architecture,
            Skill::ApiDesign,
            Skill::WebDev,
            Skill::Database,
        ],
        TaskCategory::Testing => vec![
            Skill::Testing,
            Skill::Python,
            Skill::CodeReview,
            Skill::Security,
        ],
        TaskCategory::Other => vec![],
    };

    if possible_skills.is_empty() {
        return vec![];
    }

    // Pick 1-3 random skills
    let count = rng.r#gen_range(1..=3.min(possible_skills.len()));
    possible_skills
        .choose_multiple(rng, count)
        .copied()
        .collect()
}

/// Get human-readable category name.
fn category_name(category: TaskCategory) -> &'static str {
    match category {
        TaskCategory::Coding => "Coding",
        TaskCategory::CodeReview => "Code Review",
        TaskCategory::Documentation => "Documentation",
        TaskCategory::DataAnalysis => "Data Analysis",
        TaskCategory::Research => "Research",
        TaskCategory::Design => "Design",
        TaskCategory::Testing => "Testing",
        TaskCategory::Other => "General",
    }
}
