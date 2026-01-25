//! Task selection strategies.

use economic_agents_interfaces::{Result, Task};

use crate::config::TaskSelectionStrategy;

/// Select a task based on the configured strategy.
pub fn select_task<'a>(
    tasks: &'a [Task],
    strategy: TaskSelectionStrategy,
    _agent_skills: Option<&[String]>,
) -> Result<Option<&'a Task>> {
    if tasks.is_empty() {
        return Ok(None);
    }

    let selected = match strategy {
        TaskSelectionStrategy::FirstAvailable => tasks.first(),

        TaskSelectionStrategy::HighestReward => tasks.iter().max_by(|a, b| {
            a.reward
                .partial_cmp(&b.reward)
                .unwrap_or(std::cmp::Ordering::Equal)
        }),

        TaskSelectionStrategy::BestRatio => tasks.iter().max_by(|a, b| {
            let ratio_a = a.reward / a.estimated_hours.max(0.1);
            let ratio_b = b.reward / b.estimated_hours.max(0.1);
            ratio_a
                .partial_cmp(&ratio_b)
                .unwrap_or(std::cmp::Ordering::Equal)
        }),

        TaskSelectionStrategy::Balanced => {
            // Score based on reward, difficulty, and time
            tasks.iter().max_by(|a, b| {
                let score_a = a.reward * (1.0 - a.difficulty) / a.estimated_hours.max(0.1);
                let score_b = b.reward * (1.0 - b.difficulty) / b.estimated_hours.max(0.1);
                score_a
                    .partial_cmp(&score_b)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
        }

        TaskSelectionStrategy::SkillMatch => {
            // TODO: Implement skill matching
            // For now, fall back to balanced
            tasks.iter().max_by(|a, b| {
                let score_a = a.reward * (1.0 - a.difficulty) / a.estimated_hours.max(0.1);
                let score_b = b.reward * (1.0 - b.difficulty) / b.estimated_hours.max(0.1);
                score_a
                    .partial_cmp(&score_b)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
        }
    };

    Ok(selected)
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use economic_agents_interfaces::{TaskCategory, TaskStatus};
    use uuid::Uuid;

    fn make_task(reward: f64, hours: f64, difficulty: f64) -> Task {
        Task {
            id: Uuid::new_v4(),
            title: "Test Task".to_string(),
            description: "A test task".to_string(),
            category: TaskCategory::Coding,
            reward,
            estimated_hours: hours,
            difficulty,
            deadline: None,
            status: TaskStatus::Available,
            posted_by: "poster".to_string(),
            posted_at: Utc::now(),
            claimed_by: None,
            claimed_at: None,
        }
    }

    #[test]
    fn test_highest_reward() {
        let tasks = vec![
            make_task(10.0, 1.0, 0.5),
            make_task(50.0, 5.0, 0.8),
            make_task(30.0, 2.0, 0.3),
        ];

        let selected = select_task(&tasks, TaskSelectionStrategy::HighestReward, None)
            .unwrap()
            .unwrap();
        assert_eq!(selected.reward, 50.0);
    }

    #[test]
    fn test_best_ratio() {
        let tasks = vec![
            make_task(10.0, 1.0, 0.5),  // ratio = 10
            make_task(50.0, 10.0, 0.8), // ratio = 5
            make_task(30.0, 2.0, 0.3),  // ratio = 15
        ];

        let selected = select_task(&tasks, TaskSelectionStrategy::BestRatio, None)
            .unwrap()
            .unwrap();
        assert_eq!(selected.reward, 30.0);
    }

    #[test]
    fn test_empty_tasks() {
        let tasks: Vec<Task> = vec![];
        let selected = select_task(&tasks, TaskSelectionStrategy::FirstAvailable, None).unwrap();
        assert!(selected.is_none());
    }
}
