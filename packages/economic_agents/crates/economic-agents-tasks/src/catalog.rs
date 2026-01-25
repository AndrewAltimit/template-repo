//! Task catalog with predefined coding challenges.
//!
//! Contains a collection of coding tasks with test cases that can be used
//! to evaluate agent capabilities.

use chrono::Utc;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use economic_agents_interfaces::{Skill, Task, TaskCategory, TaskStatus};

/// A coding challenge with test cases.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodingChallenge {
    /// Challenge identifier.
    pub id: String,
    /// Human-readable name.
    pub name: String,
    /// Detailed description of the problem.
    pub description: String,
    /// Programming language (e.g., "python", "rust", "javascript").
    pub language: String,
    /// Function signature or template.
    pub function_template: String,
    /// Test cases for validation.
    pub test_cases: Vec<TestCase>,
    /// Difficulty level (0.0-1.0).
    pub difficulty: f64,
    /// Estimated hours to complete.
    pub estimated_hours: f64,
    /// Reward for completion.
    pub reward: f64,
    /// Tags for categorization.
    pub tags: Vec<String>,
}

/// A test case for validating solutions.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TestCase {
    /// Test case name.
    pub name: String,
    /// Input values (as JSON strings for flexibility).
    pub inputs: Vec<String>,
    /// Expected output (as JSON string).
    pub expected_output: String,
    /// Whether this is a hidden test (not shown to solver).
    pub hidden: bool,
}

impl CodingChallenge {
    /// Convert to a marketplace Task.
    pub fn to_task(&self) -> Task {
        // Derive required skills from language and tags
        let mut required_skills = vec![self.language_to_skill()];

        // Add skills based on tags
        for tag in &self.tags {
            if let Some(skill) = tag_to_skill(tag)
                && !required_skills.contains(&skill)
            {
                required_skills.push(skill);
            }
        }

        Task {
            id: Uuid::new_v4(),
            title: self.name.clone(),
            description: format!(
                "{}\n\nLanguage: {}\n\nTemplate:\n```{}\n{}\n```",
                self.description, self.language, self.language, self.function_template
            ),
            category: TaskCategory::Coding,
            reward: self.reward,
            estimated_hours: self.estimated_hours,
            difficulty: self.difficulty,
            required_skills,
            deadline: None,
            status: TaskStatus::Available,
            posted_by: "task-catalog".to_string(),
            posted_at: Utc::now(),
            claimed_by: None,
            claimed_at: None,
        }
    }

    /// Convert language string to Skill enum.
    fn language_to_skill(&self) -> Skill {
        match self.language.to_lowercase().as_str() {
            "python" => Skill::Python,
            "rust" => Skill::Rust,
            "javascript" | "js" | "typescript" | "ts" => Skill::JavaScript,
            "go" | "golang" => Skill::Go,
            "java" => Skill::Java,
            "c" | "c++" | "cpp" => Skill::Cpp,
            "sql" => Skill::Sql,
            _ => Skill::Python, // Default fallback
        }
    }
}

/// Convert a tag string to a Skill if possible.
fn tag_to_skill(tag: &str) -> Option<Skill> {
    match tag.to_lowercase().as_str() {
        "algorithms" | "data-structures" => Some(Skill::Architecture),
        "strings" | "string-manipulation" => None,
        "math" | "mathematics" => Some(Skill::DataAnalysis),
        "array" | "arrays" => None,
        "hash-table" | "hashmap" | "dictionary" => Some(Skill::Database),
        "recursion" | "dynamic-programming" => Some(Skill::Architecture),
        "cache" | "caching" => Some(Skill::Database),
        "stack" | "queue" => None,
        "binary-search" | "search" => None,
        "testing" | "test" => Some(Skill::Testing),
        "security" => Some(Skill::Security),
        "api" | "rest" => Some(Skill::ApiDesign),
        "web" | "frontend" | "backend" => Some(Skill::WebDev),
        "ml" | "machine-learning" | "ai" => Some(Skill::MachineLearning),
        "devops" | "infrastructure" => Some(Skill::DevOps),
        _ => None,
    }
}

/// The task catalog containing all available coding challenges.
pub struct TaskCatalog {
    challenges: Vec<CodingChallenge>,
}

impl TaskCatalog {
    /// Create a new catalog with default challenges.
    pub fn new() -> Self {
        Self {
            challenges: Self::default_challenges(),
        }
    }

    /// Get all challenges.
    pub fn all(&self) -> &[CodingChallenge] {
        &self.challenges
    }

    /// Get challenge by ID.
    pub fn get(&self, id: &str) -> Option<&CodingChallenge> {
        self.challenges.iter().find(|c| c.id == id)
    }

    /// Get challenges by difficulty range.
    pub fn by_difficulty(&self, min: f64, max: f64) -> Vec<&CodingChallenge> {
        self.challenges
            .iter()
            .filter(|c| c.difficulty >= min && c.difficulty <= max)
            .collect()
    }

    /// Get challenges by language.
    pub fn by_language(&self, language: &str) -> Vec<&CodingChallenge> {
        self.challenges
            .iter()
            .filter(|c| c.language.eq_ignore_ascii_case(language))
            .collect()
    }

    /// Get challenges as marketplace Tasks.
    pub fn as_tasks(&self) -> Vec<Task> {
        self.challenges.iter().map(|c| c.to_task()).collect()
    }

    /// Default set of coding challenges.
    fn default_challenges() -> Vec<CodingChallenge> {
        vec![
            // Easy challenges (0.1 - 0.3 difficulty)
            Self::fizzbuzz(),
            Self::palindrome(),
            Self::reverse_string(),
            Self::factorial(),
            Self::fibonacci(),
            // Medium challenges (0.4 - 0.6 difficulty)
            Self::prime_checker(),
            Self::binary_search(),
            Self::anagram_checker(),
            Self::two_sum(),
            Self::merge_sorted_arrays(),
            // Hard challenges (0.7 - 0.9 difficulty)
            Self::longest_substring(),
            Self::valid_parentheses(),
            Self::lru_cache(),
        ]
    }

    // === EASY CHALLENGES ===

    fn fizzbuzz() -> CodingChallenge {
        CodingChallenge {
            id: "fizzbuzz".to_string(),
            name: "FizzBuzz".to_string(),
            description: r#"Write a function that returns "Fizz" for multiples of 3, "Buzz" for multiples of 5, "FizzBuzz" for multiples of both, or the number as a string otherwise.

Rules:
- If n is divisible by 3, return "Fizz"
- If n is divisible by 5, return "Buzz"
- If n is divisible by both 3 and 5, return "FizzBuzz"
- Otherwise, return the number as a string"#.to_string(),
            language: "python".to_string(),
            function_template: r#"def fizzbuzz(n: int) -> str:
    """Return FizzBuzz result for n."""
    pass"#.to_string(),
            test_cases: vec![
                TestCase {
                    name: "divisible_by_3".to_string(),
                    inputs: vec!["3".to_string()],
                    expected_output: r#""Fizz""#.to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "divisible_by_5".to_string(),
                    inputs: vec!["5".to_string()],
                    expected_output: r#""Buzz""#.to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "divisible_by_15".to_string(),
                    inputs: vec!["15".to_string()],
                    expected_output: r#""FizzBuzz""#.to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "not_divisible".to_string(),
                    inputs: vec!["7".to_string()],
                    expected_output: r#""7""#.to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "hidden_30".to_string(),
                    inputs: vec!["30".to_string()],
                    expected_output: r#""FizzBuzz""#.to_string(),
                    hidden: true,
                },
            ],
            difficulty: 0.1,
            estimated_hours: 0.5,
            reward: 10.0,
            tags: vec!["easy".to_string(), "basics".to_string()],
        }
    }

    fn palindrome() -> CodingChallenge {
        CodingChallenge {
            id: "palindrome".to_string(),
            name: "Palindrome Checker".to_string(),
            description: r#"Write a function that checks if a string is a palindrome.

A palindrome reads the same forwards and backwards. Ignore case and non-alphanumeric characters.

Examples:
- "racecar" -> True
- "A man, a plan, a canal: Panama" -> True
- "hello" -> False"#.to_string(),
            language: "python".to_string(),
            function_template: r#"def is_palindrome(s: str) -> bool:
    """Check if s is a palindrome, ignoring case and non-alphanumeric chars."""
    pass"#.to_string(),
            test_cases: vec![
                TestCase {
                    name: "simple_palindrome".to_string(),
                    inputs: vec![r#""racecar""#.to_string()],
                    expected_output: "true".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "with_spaces".to_string(),
                    inputs: vec![r#""A man a plan a canal Panama""#.to_string()],
                    expected_output: "true".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "not_palindrome".to_string(),
                    inputs: vec![r#""hello""#.to_string()],
                    expected_output: "false".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "empty_string".to_string(),
                    inputs: vec![r#""""#.to_string()],
                    expected_output: "true".to_string(),
                    hidden: true,
                },
            ],
            difficulty: 0.2,
            estimated_hours: 0.5,
            reward: 12.0,
            tags: vec!["easy".to_string(), "strings".to_string()],
        }
    }

    fn reverse_string() -> CodingChallenge {
        CodingChallenge {
            id: "reverse_string".to_string(),
            name: "Reverse String".to_string(),
            description: r#"Write a function that reverses a string in-place (or returns the reversed string).

You should not use built-in reverse functions."#.to_string(),
            language: "python".to_string(),
            function_template: r#"def reverse_string(s: str) -> str:
    """Reverse the string s."""
    pass"#.to_string(),
            test_cases: vec![
                TestCase {
                    name: "simple".to_string(),
                    inputs: vec![r#""hello""#.to_string()],
                    expected_output: r#""olleh""#.to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "empty".to_string(),
                    inputs: vec![r#""""#.to_string()],
                    expected_output: r#""""#.to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "single_char".to_string(),
                    inputs: vec![r#""a""#.to_string()],
                    expected_output: r#""a""#.to_string(),
                    hidden: true,
                },
            ],
            difficulty: 0.15,
            estimated_hours: 0.25,
            reward: 8.0,
            tags: vec!["easy".to_string(), "strings".to_string()],
        }
    }

    fn factorial() -> CodingChallenge {
        CodingChallenge {
            id: "factorial".to_string(),
            name: "Factorial".to_string(),
            description: r#"Write a function that calculates the factorial of a non-negative integer.

factorial(n) = n * (n-1) * (n-2) * ... * 1
factorial(0) = 1

Example: factorial(5) = 120"#.to_string(),
            language: "python".to_string(),
            function_template: r#"def factorial(n: int) -> int:
    """Calculate factorial of n."""
    pass"#.to_string(),
            test_cases: vec![
                TestCase {
                    name: "zero".to_string(),
                    inputs: vec!["0".to_string()],
                    expected_output: "1".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "one".to_string(),
                    inputs: vec!["1".to_string()],
                    expected_output: "1".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "five".to_string(),
                    inputs: vec!["5".to_string()],
                    expected_output: "120".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "ten".to_string(),
                    inputs: vec!["10".to_string()],
                    expected_output: "3628800".to_string(),
                    hidden: true,
                },
            ],
            difficulty: 0.15,
            estimated_hours: 0.25,
            reward: 8.0,
            tags: vec!["easy".to_string(), "math".to_string(), "recursion".to_string()],
        }
    }

    fn fibonacci() -> CodingChallenge {
        CodingChallenge {
            id: "fibonacci".to_string(),
            name: "Fibonacci Number".to_string(),
            description: r#"Write a function that returns the nth Fibonacci number.

The Fibonacci sequence: 0, 1, 1, 2, 3, 5, 8, 13, 21, ...
F(0) = 0, F(1) = 1, F(n) = F(n-1) + F(n-2)"#.to_string(),
            language: "python".to_string(),
            function_template: r#"def fibonacci(n: int) -> int:
    """Return the nth Fibonacci number."""
    pass"#.to_string(),
            test_cases: vec![
                TestCase {
                    name: "zero".to_string(),
                    inputs: vec!["0".to_string()],
                    expected_output: "0".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "one".to_string(),
                    inputs: vec!["1".to_string()],
                    expected_output: "1".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "ten".to_string(),
                    inputs: vec!["10".to_string()],
                    expected_output: "55".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "twenty".to_string(),
                    inputs: vec!["20".to_string()],
                    expected_output: "6765".to_string(),
                    hidden: true,
                },
            ],
            difficulty: 0.2,
            estimated_hours: 0.5,
            reward: 12.0,
            tags: vec!["easy".to_string(), "math".to_string(), "recursion".to_string()],
        }
    }

    // === MEDIUM CHALLENGES ===

    fn prime_checker() -> CodingChallenge {
        CodingChallenge {
            id: "prime_checker".to_string(),
            name: "Prime Number Checker".to_string(),
            description: r#"Write a function that checks if a number is prime.

A prime number is only divisible by 1 and itself. Optimize for efficiency."#.to_string(),
            language: "python".to_string(),
            function_template: r#"def is_prime(n: int) -> bool:
    """Check if n is a prime number."""
    pass"#.to_string(),
            test_cases: vec![
                TestCase {
                    name: "two".to_string(),
                    inputs: vec!["2".to_string()],
                    expected_output: "true".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "seventeen".to_string(),
                    inputs: vec!["17".to_string()],
                    expected_output: "true".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "four".to_string(),
                    inputs: vec!["4".to_string()],
                    expected_output: "false".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "one".to_string(),
                    inputs: vec!["1".to_string()],
                    expected_output: "false".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "large_prime".to_string(),
                    inputs: vec!["997".to_string()],
                    expected_output: "true".to_string(),
                    hidden: true,
                },
            ],
            difficulty: 0.4,
            estimated_hours: 1.0,
            reward: 25.0,
            tags: vec!["medium".to_string(), "math".to_string()],
        }
    }

    fn binary_search() -> CodingChallenge {
        CodingChallenge {
            id: "binary_search".to_string(),
            name: "Binary Search".to_string(),
            description: r#"Implement binary search to find a target value in a sorted array.

Return the index of the target if found, or -1 if not found.
The array is sorted in ascending order."#.to_string(),
            language: "python".to_string(),
            function_template: r#"def binary_search(arr: list, target: int) -> int:
    """Find target in sorted arr, return index or -1."""
    pass"#.to_string(),
            test_cases: vec![
                TestCase {
                    name: "found_middle".to_string(),
                    inputs: vec!["[1, 2, 3, 4, 5]".to_string(), "3".to_string()],
                    expected_output: "2".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "found_first".to_string(),
                    inputs: vec!["[1, 2, 3, 4, 5]".to_string(), "1".to_string()],
                    expected_output: "0".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "not_found".to_string(),
                    inputs: vec!["[1, 2, 3, 4, 5]".to_string(), "6".to_string()],
                    expected_output: "-1".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "empty_array".to_string(),
                    inputs: vec!["[]".to_string(), "1".to_string()],
                    expected_output: "-1".to_string(),
                    hidden: true,
                },
            ],
            difficulty: 0.4,
            estimated_hours: 1.0,
            reward: 25.0,
            tags: vec!["medium".to_string(), "algorithms".to_string(), "search".to_string()],
        }
    }

    fn anagram_checker() -> CodingChallenge {
        CodingChallenge {
            id: "anagram_checker".to_string(),
            name: "Anagram Checker".to_string(),
            description: r#"Write a function to check if two strings are anagrams of each other.

Two strings are anagrams if they contain the same characters with the same frequencies.
Ignore case and spaces."#.to_string(),
            language: "python".to_string(),
            function_template: r#"def is_anagram(s1: str, s2: str) -> bool:
    """Check if s1 and s2 are anagrams."""
    pass"#.to_string(),
            test_cases: vec![
                TestCase {
                    name: "simple_anagram".to_string(),
                    inputs: vec![r#""listen""#.to_string(), r#""silent""#.to_string()],
                    expected_output: "true".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "not_anagram".to_string(),
                    inputs: vec![r#""hello""#.to_string(), r#""world""#.to_string()],
                    expected_output: "false".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "with_spaces".to_string(),
                    inputs: vec![r#""Dormitory""#.to_string(), r#""Dirty room""#.to_string()],
                    expected_output: "true".to_string(),
                    hidden: true,
                },
            ],
            difficulty: 0.4,
            estimated_hours: 1.0,
            reward: 25.0,
            tags: vec!["medium".to_string(), "strings".to_string(), "hash".to_string()],
        }
    }

    fn two_sum() -> CodingChallenge {
        CodingChallenge {
            id: "two_sum".to_string(),
            name: "Two Sum".to_string(),
            description: r#"Given an array of integers and a target sum, return the indices of two numbers that add up to the target.

Assume exactly one solution exists. You may not use the same element twice.
Return the indices in any order."#.to_string(),
            language: "python".to_string(),
            function_template: r#"def two_sum(nums: list, target: int) -> list:
    """Find indices of two numbers that add to target."""
    pass"#.to_string(),
            test_cases: vec![
                TestCase {
                    name: "basic".to_string(),
                    inputs: vec!["[2, 7, 11, 15]".to_string(), "9".to_string()],
                    expected_output: "[0, 1]".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "middle".to_string(),
                    inputs: vec!["[3, 2, 4]".to_string(), "6".to_string()],
                    expected_output: "[1, 2]".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "duplicates".to_string(),
                    inputs: vec!["[3, 3]".to_string(), "6".to_string()],
                    expected_output: "[0, 1]".to_string(),
                    hidden: true,
                },
            ],
            difficulty: 0.5,
            estimated_hours: 1.5,
            reward: 35.0,
            tags: vec!["medium".to_string(), "arrays".to_string(), "hash".to_string()],
        }
    }

    fn merge_sorted_arrays() -> CodingChallenge {
        CodingChallenge {
            id: "merge_sorted_arrays".to_string(),
            name: "Merge Sorted Arrays".to_string(),
            description: r#"Merge two sorted arrays into one sorted array.

Both input arrays are sorted in ascending order.
Return a new array containing all elements in sorted order."#.to_string(),
            language: "python".to_string(),
            function_template: r#"def merge_sorted(arr1: list, arr2: list) -> list:
    """Merge two sorted arrays into one sorted array."""
    pass"#.to_string(),
            test_cases: vec![
                TestCase {
                    name: "basic".to_string(),
                    inputs: vec!["[1, 3, 5]".to_string(), "[2, 4, 6]".to_string()],
                    expected_output: "[1, 2, 3, 4, 5, 6]".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "empty_first".to_string(),
                    inputs: vec!["[]".to_string(), "[1, 2, 3]".to_string()],
                    expected_output: "[1, 2, 3]".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "overlapping".to_string(),
                    inputs: vec!["[1, 2, 3]".to_string(), "[2, 3, 4]".to_string()],
                    expected_output: "[1, 2, 2, 3, 3, 4]".to_string(),
                    hidden: true,
                },
            ],
            difficulty: 0.5,
            estimated_hours: 1.0,
            reward: 30.0,
            tags: vec!["medium".to_string(), "arrays".to_string(), "sorting".to_string()],
        }
    }

    // === HARD CHALLENGES ===

    fn longest_substring() -> CodingChallenge {
        CodingChallenge {
            id: "longest_substring".to_string(),
            name: "Longest Substring Without Repeating Characters".to_string(),
            description: r#"Find the length of the longest substring without repeating characters.

Example: "abcabcbb" -> 3 (the answer is "abc")
Example: "bbbbb" -> 1 (the answer is "b")
Example: "pwwkew" -> 3 (the answer is "wke")"#.to_string(),
            language: "python".to_string(),
            function_template: r#"def length_of_longest_substring(s: str) -> int:
    """Find length of longest substring without repeating chars."""
    pass"#.to_string(),
            test_cases: vec![
                TestCase {
                    name: "basic".to_string(),
                    inputs: vec![r#""abcabcbb""#.to_string()],
                    expected_output: "3".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "all_same".to_string(),
                    inputs: vec![r#""bbbbb""#.to_string()],
                    expected_output: "1".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "mixed".to_string(),
                    inputs: vec![r#""pwwkew""#.to_string()],
                    expected_output: "3".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "empty".to_string(),
                    inputs: vec![r#""""#.to_string()],
                    expected_output: "0".to_string(),
                    hidden: true,
                },
            ],
            difficulty: 0.7,
            estimated_hours: 2.0,
            reward: 50.0,
            tags: vec!["hard".to_string(), "strings".to_string(), "sliding_window".to_string()],
        }
    }

    fn valid_parentheses() -> CodingChallenge {
        CodingChallenge {
            id: "valid_parentheses".to_string(),
            name: "Valid Parentheses".to_string(),
            description: r#"Given a string containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.

A string is valid if:
1. Open brackets must be closed by the same type of brackets.
2. Open brackets must be closed in the correct order.
3. Every close bracket has a corresponding open bracket of the same type."#.to_string(),
            language: "python".to_string(),
            function_template: r#"def is_valid_parentheses(s: str) -> bool:
    """Check if parentheses string is valid."""
    pass"#.to_string(),
            test_cases: vec![
                TestCase {
                    name: "simple_valid".to_string(),
                    inputs: vec![r#""()""#.to_string()],
                    expected_output: "true".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "mixed_valid".to_string(),
                    inputs: vec![r#""()[]{}""#.to_string()],
                    expected_output: "true".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "nested_valid".to_string(),
                    inputs: vec![r#""{[]}""#.to_string()],
                    expected_output: "true".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "invalid".to_string(),
                    inputs: vec![r#""(]""#.to_string()],
                    expected_output: "false".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "unmatched".to_string(),
                    inputs: vec![r#""([)]""#.to_string()],
                    expected_output: "false".to_string(),
                    hidden: true,
                },
            ],
            difficulty: 0.7,
            estimated_hours: 1.5,
            reward: 45.0,
            tags: vec!["hard".to_string(), "strings".to_string(), "stack".to_string()],
        }
    }

    fn lru_cache() -> CodingChallenge {
        CodingChallenge {
            id: "lru_cache".to_string(),
            name: "LRU Cache".to_string(),
            description: r#"Design a data structure that follows the constraints of a Least Recently Used (LRU) cache.

Implement the LRUCache class:
- __init__(capacity): Initialize with positive capacity
- get(key): Return the value if key exists, else return -1
- put(key, value): Update the value. If key doesn't exist, add it. If capacity exceeded, evict the least recently used key.

Both get and put must run in O(1) average time complexity."#.to_string(),
            language: "python".to_string(),
            function_template: r#"class LRUCache:
    def __init__(self, capacity: int):
        """Initialize LRU cache with given capacity."""
        pass

    def get(self, key: int) -> int:
        """Get value for key, return -1 if not found."""
        pass

    def put(self, key: int, value: int) -> None:
        """Put key-value pair, evict LRU if at capacity."""
        pass"#.to_string(),
            test_cases: vec![
                TestCase {
                    name: "basic_operations".to_string(),
                    inputs: vec![
                        "LRUCache(2)".to_string(),
                        "put(1, 1)".to_string(),
                        "put(2, 2)".to_string(),
                        "get(1)".to_string(),
                    ],
                    expected_output: "1".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "eviction".to_string(),
                    inputs: vec![
                        "LRUCache(2)".to_string(),
                        "put(1, 1)".to_string(),
                        "put(2, 2)".to_string(),
                        "put(3, 3)".to_string(),
                        "get(1)".to_string(),
                    ],
                    expected_output: "-1".to_string(),
                    hidden: false,
                },
                TestCase {
                    name: "update_existing".to_string(),
                    inputs: vec![
                        "LRUCache(2)".to_string(),
                        "put(1, 1)".to_string(),
                        "put(1, 10)".to_string(),
                        "get(1)".to_string(),
                    ],
                    expected_output: "10".to_string(),
                    hidden: true,
                },
            ],
            difficulty: 0.9,
            estimated_hours: 3.0,
            reward: 80.0,
            tags: vec!["hard".to_string(), "design".to_string(), "hash".to_string(), "linked_list".to_string()],
        }
    }
}

impl Default for TaskCatalog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_catalog_creation() {
        let catalog = TaskCatalog::new();
        assert!(!catalog.all().is_empty());
    }

    #[test]
    fn test_get_by_id() {
        let catalog = TaskCatalog::new();
        let fizzbuzz = catalog.get("fizzbuzz");
        assert!(fizzbuzz.is_some());
        assert_eq!(fizzbuzz.unwrap().name, "FizzBuzz");
    }

    #[test]
    fn test_by_difficulty() {
        let catalog = TaskCatalog::new();
        let easy = catalog.by_difficulty(0.0, 0.3);
        assert!(!easy.is_empty());
        for challenge in easy {
            assert!(challenge.difficulty <= 0.3);
        }
    }

    #[test]
    fn test_by_language() {
        let catalog = TaskCatalog::new();
        let python = catalog.by_language("python");
        assert!(!python.is_empty());
    }

    #[test]
    fn test_to_task() {
        let catalog = TaskCatalog::new();
        let challenge = catalog.get("fizzbuzz").unwrap();
        let task = challenge.to_task();
        assert_eq!(task.category, TaskCategory::Coding);
        assert!(task.description.contains("FizzBuzz"));
    }

    #[test]
    fn test_test_cases() {
        let catalog = TaskCatalog::new();
        let challenge = catalog.get("fizzbuzz").unwrap();
        assert!(!challenge.test_cases.is_empty());

        // Check hidden test exists
        let hidden_count = challenge.test_cases.iter().filter(|tc| tc.hidden).count();
        assert!(hidden_count > 0);
    }
}
