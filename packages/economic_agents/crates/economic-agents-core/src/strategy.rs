//! Task selection strategies.

use economic_agents_interfaces::{Result, Skill, Task};

use crate::config::{AgentConfig, TaskSelectionStrategy};

/// Select a task based on the configured strategy.
pub fn select_task<'a>(
    tasks: &'a [Task],
    strategy: TaskSelectionStrategy,
    agent_config: Option<&AgentConfig>,
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
            if let Some(config) = agent_config {
                select_by_skill_match(tasks, config)
            } else {
                // Fall back to balanced if no config provided
                tasks.iter().max_by(|a, b| {
                    let score_a = a.reward * (1.0 - a.difficulty) / a.estimated_hours.max(0.1);
                    let score_b = b.reward * (1.0 - b.difficulty) / b.estimated_hours.max(0.1);
                    score_a
                        .partial_cmp(&score_b)
                        .unwrap_or(std::cmp::Ordering::Equal)
                })
            }
        }
    };

    Ok(selected)
}

/// Select task by matching agent skills to task requirements.
fn select_by_skill_match<'a>(tasks: &'a [Task], config: &AgentConfig) -> Option<&'a Task> {
    tasks.iter().max_by(|a, b| {
        let score_a = calculate_skill_match_score(a, config);
        let score_b = calculate_skill_match_score(b, config);
        score_a
            .partial_cmp(&score_b)
            .unwrap_or(std::cmp::Ordering::Equal)
    })
}

/// Calculate a composite score for a task based on skill matching.
///
/// The score considers:
/// - Skill coverage: what fraction of required skills the agent has
/// - Skill proficiency: how well the agent's skill levels match task difficulty
/// - Reward efficiency: reward per hour adjusted by skill fit
/// - Difficulty appropriateness: prefer tasks matching skill level
fn calculate_skill_match_score(task: &Task, config: &AgentConfig) -> f64 {
    // Base score from reward/time ratio (normalized to 0-1 range)
    let base_score = task.reward / task.estimated_hours.max(0.1);
    let normalized_base = (base_score / 100.0).min(1.0);

    // If task has no required skills, use balanced scoring
    if task.required_skills.is_empty() {
        return normalized_base * (1.0 - task.difficulty);
    }

    // Calculate skill coverage (0.0 to 1.0)
    let (coverage, avg_proficiency) = calculate_skill_coverage(task, config);

    // Penalize tasks where agent lacks required skills
    if coverage == 0.0 {
        // Agent has none of the required skills - heavy penalty (10% of base)
        return normalized_base * 0.1;
    }

    // Calculate difficulty fit (how well agent's proficiency matches task difficulty)
    // Best fit when proficiency slightly exceeds difficulty
    let difficulty_fit = calculate_difficulty_fit(task.difficulty, avg_proficiency);

    // Composite score (all components in 0-1 range):
    // - coverage: 40% weight - having the right skills matters most
    // - difficulty_fit: 30% weight - matching skill level to task
    // - base_score: 30% weight - still consider reward efficiency
    coverage * 0.4 + difficulty_fit * 0.3 + normalized_base * 0.3
}

/// Calculate what fraction of required skills the agent has and average proficiency.
fn calculate_skill_coverage(task: &Task, config: &AgentConfig) -> (f64, f64) {
    if task.required_skills.is_empty() {
        return (1.0, 0.5);
    }

    let mut matched = 0;
    let mut total_proficiency = 0.0;

    for skill in &task.required_skills {
        let proficiency = config.skill_proficiency(*skill);
        if proficiency > 0.0 {
            matched += 1;
            total_proficiency += proficiency;
        }
    }

    let coverage = matched as f64 / task.required_skills.len() as f64;
    let avg_proficiency = if matched > 0 {
        total_proficiency / matched as f64
    } else {
        0.0
    };

    (coverage, avg_proficiency)
}

/// Calculate how well agent proficiency fits task difficulty.
///
/// Returns a score from 0.0 to 1.0:
/// - 1.0: proficiency slightly exceeds difficulty (ideal)
/// - 0.7-0.9: proficiency matches difficulty well
/// - 0.3-0.6: proficiency significantly above difficulty (too easy)
/// - 0.1-0.4: proficiency below difficulty (too hard)
fn calculate_difficulty_fit(difficulty: f64, proficiency: f64) -> f64 {
    let diff = proficiency - difficulty;

    if (0.0..=0.2).contains(&diff) {
        // Slightly over-qualified: ideal (1.0)
        1.0
    } else if (0.2..=0.4).contains(&diff) {
        // Moderately over-qualified (0.8)
        0.8
    } else if diff > 0.4 {
        // Very over-qualified - task too easy (0.5)
        0.5
    } else if diff >= -0.2 {
        // Slightly under-qualified - challenging but doable (0.7)
        0.7
    } else if diff >= -0.4 {
        // Moderately under-qualified (0.4)
        0.4
    } else {
        // Very under-qualified - task too hard (0.2)
        0.2
    }
}

/// Get recommended skills for a task category.
pub fn skills_for_category(category: economic_agents_interfaces::TaskCategory) -> Vec<Skill> {
    use economic_agents_interfaces::TaskCategory;

    match category {
        TaskCategory::Coding => vec![
            Skill::Python,
            Skill::Rust,
            Skill::JavaScript,
            Skill::Architecture,
        ],
        TaskCategory::CodeReview => vec![
            Skill::CodeReview,
            Skill::Python,
            Skill::Rust,
            Skill::Security,
        ],
        TaskCategory::Documentation => vec![Skill::TechnicalWriting, Skill::Research],
        TaskCategory::DataAnalysis => vec![
            Skill::DataAnalysis,
            Skill::Python,
            Skill::Sql,
            Skill::MachineLearning,
        ],
        TaskCategory::Research => vec![
            Skill::Research,
            Skill::TechnicalWriting,
            Skill::DataAnalysis,
        ],
        TaskCategory::Design => vec![Skill::Architecture, Skill::ApiDesign, Skill::WebDev],
        TaskCategory::Testing => vec![Skill::Testing, Skill::Python, Skill::CodeReview],
        TaskCategory::Other => vec![],
    }
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
            required_skills: vec![],
            deadline: None,
            status: TaskStatus::Available,
            posted_by: "poster".to_string(),
            posted_at: Utc::now(),
            claimed_by: None,
            claimed_at: None,
        }
    }

    fn make_task_with_skills(reward: f64, hours: f64, difficulty: f64, skills: Vec<Skill>) -> Task {
        Task {
            id: Uuid::new_v4(),
            title: "Skilled Task".to_string(),
            description: "A task requiring skills".to_string(),
            category: TaskCategory::Coding,
            reward,
            estimated_hours: hours,
            difficulty,
            required_skills: skills,
            deadline: None,
            status: TaskStatus::Available,
            posted_by: "poster".to_string(),
            posted_at: Utc::now(),
            claimed_by: None,
            claimed_at: None,
        }
    }

    fn make_skilled_config(skills: Vec<(Skill, f64)>) -> AgentConfig {
        let mut config = AgentConfig::default();
        for (skill, level) in skills {
            config.add_skill(skill, level);
        }
        config
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

    #[test]
    fn test_skill_match_prefers_matching_skills() {
        let tasks = vec![
            make_task_with_skills(50.0, 2.0, 0.5, vec![Skill::Python, Skill::DataAnalysis]),
            make_task_with_skills(50.0, 2.0, 0.5, vec![Skill::Rust, Skill::Security]),
            make_task_with_skills(50.0, 2.0, 0.5, vec![Skill::Java, Skill::Database]),
        ];

        // Agent skilled in Python and DataAnalysis
        let config = make_skilled_config(vec![(Skill::Python, 0.8), (Skill::DataAnalysis, 0.7)]);

        let selected = select_task(&tasks, TaskSelectionStrategy::SkillMatch, Some(&config))
            .unwrap()
            .unwrap();

        // Should prefer the Python/DataAnalysis task
        assert!(selected.required_skills.contains(&Skill::Python));
    }

    #[test]
    fn test_skill_match_considers_proficiency() {
        let tasks = vec![
            make_task_with_skills(50.0, 2.0, 0.3, vec![Skill::Python]), // Easy task
            make_task_with_skills(50.0, 2.0, 0.7, vec![Skill::Python]), // Hard task
        ];

        // Agent with moderate Python skill
        let config = make_skilled_config(vec![(Skill::Python, 0.5)]);

        let selected = select_task(&tasks, TaskSelectionStrategy::SkillMatch, Some(&config))
            .unwrap()
            .unwrap();

        // Should prefer the easier task that matches skill level
        assert_eq!(selected.difficulty, 0.3);
    }

    #[test]
    fn test_skill_match_penalizes_missing_skills() {
        let tasks = vec![
            make_task_with_skills(100.0, 2.0, 0.5, vec![Skill::Rust]), // High reward, missing skill
            make_task_with_skills(30.0, 2.0, 0.5, vec![Skill::Python]), // Lower reward, has skill
        ];

        // Agent only knows Python
        let config = make_skilled_config(vec![(Skill::Python, 0.8)]);

        let selected = select_task(&tasks, TaskSelectionStrategy::SkillMatch, Some(&config))
            .unwrap()
            .unwrap();

        // Should prefer the Python task despite lower reward
        assert!(selected.required_skills.contains(&Skill::Python));
    }

    #[test]
    fn test_skill_coverage_full_match() {
        let task = make_task_with_skills(50.0, 2.0, 0.5, vec![Skill::Python, Skill::Sql]);
        let config = make_skilled_config(vec![(Skill::Python, 0.8), (Skill::Sql, 0.6)]);

        let (coverage, avg_prof) = calculate_skill_coverage(&task, &config);
        assert_eq!(coverage, 1.0);
        assert!((avg_prof - 0.7).abs() < 0.01); // (0.8 + 0.6) / 2
    }

    #[test]
    fn test_skill_coverage_partial_match() {
        let task = make_task_with_skills(50.0, 2.0, 0.5, vec![Skill::Python, Skill::Rust]);
        let config = make_skilled_config(vec![(Skill::Python, 0.8)]);

        let (coverage, _) = calculate_skill_coverage(&task, &config);
        assert_eq!(coverage, 0.5); // 1 of 2 skills
    }

    #[test]
    fn test_difficulty_fit_ideal() {
        // Proficiency slightly above difficulty is ideal
        assert_eq!(calculate_difficulty_fit(0.5, 0.6), 1.0);
        assert_eq!(calculate_difficulty_fit(0.5, 0.5), 1.0);
    }

    #[test]
    fn test_difficulty_fit_overqualified() {
        // Very over-qualified gets lower score
        assert!(calculate_difficulty_fit(0.2, 0.9) < 0.7);
    }

    #[test]
    fn test_difficulty_fit_underqualified() {
        // Under-qualified gets lower score
        assert!(calculate_difficulty_fit(0.8, 0.3) < 0.5);
    }

    #[test]
    fn test_agent_config_skill_helpers() {
        let mut config = AgentConfig::default();

        assert!(!config.has_skill(Skill::Python));
        assert_eq!(config.skill_proficiency(Skill::Python), 0.0);

        config.add_skill(Skill::Python, 0.8);
        assert!(config.has_skill(Skill::Python));
        assert_eq!(config.skill_proficiency(Skill::Python), 0.8);

        // Update existing skill
        config.add_skill(Skill::Python, 0.9);
        assert_eq!(config.skill_proficiency(Skill::Python), 0.9);
    }

    #[test]
    fn test_skills_for_category() {
        let coding_skills = skills_for_category(TaskCategory::Coding);
        assert!(coding_skills.contains(&Skill::Python));
        assert!(coding_skills.contains(&Skill::Rust));

        let data_skills = skills_for_category(TaskCategory::DataAnalysis);
        assert!(data_skills.contains(&Skill::DataAnalysis));
        assert!(data_skills.contains(&Skill::Sql));
    }
}
