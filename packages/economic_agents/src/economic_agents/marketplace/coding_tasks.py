"""Coding task templates with real requirements and test cases."""

from typing import Dict, List

# Coding tasks with detailed requirements
CODING_TASKS = [
    {
        "title": "Implement FizzBuzz Function",
        "description": "Write a Python function that implements the classic FizzBuzz problem",
        "category": "coding",
        "difficulty": "easy",
        "reward": 30.0,
        "requirements": {
            "language": "python",
            "function_name": "fizzbuzz",
            "spec": """
Write a function fizzbuzz(n: int) -> List[str] that returns a list of strings from 1 to n where:
- For multiples of 3, append "Fizz"
- For multiples of 5, append "Buzz"
- For multiples of both 3 and 5, append "FizzBuzz"
- Otherwise, append the number as a string

Example:
    fizzbuzz(15) returns:
    ["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz", "Buzz", "11", "Fizz", "13", "14", "FizzBuzz"]
""",
            "tests": [
                {"input": 5, "expected": ["1", "2", "Fizz", "4", "Buzz"]},
                {
                    "input": 15,
                    "expected": [
                        "1",
                        "2",
                        "Fizz",
                        "4",
                        "Buzz",
                        "Fizz",
                        "7",
                        "8",
                        "Fizz",
                        "Buzz",
                        "11",
                        "Fizz",
                        "13",
                        "14",
                        "FizzBuzz",
                    ],
                },
            ],
        },
    },
    {
        "title": "Palindrome Checker",
        "description": "Implement a function to check if a string is a palindrome",
        "category": "coding",
        "difficulty": "easy",
        "reward": 25.0,
        "requirements": {
            "language": "python",
            "function_name": "is_palindrome",
            "spec": """
Write a function is_palindrome(s: str) -> bool that checks if a string is a palindrome.
- Ignore case
- Ignore spaces and punctuation
- Empty string is considered a palindrome

Example: is_palindrome("A man a plan a canal Panama") returns True
""",
            "tests": [
                {"input": "racecar", "expected": True},
                {"input": "hello", "expected": False},
                {"input": "A man a plan a canal Panama", "expected": True},
                {"input": "", "expected": True},
            ],
        },
    },
    {
        "title": "Prime Number Generator",
        "description": "Generate all prime numbers up to n using Sieve of Eratosthenes",
        "category": "coding",
        "difficulty": "medium",
        "reward": 50.0,
        "requirements": {
            "language": "python",
            "function_name": "sieve_of_eratosthenes",
            "spec": """
Write a function sieve_of_eratosthenes(n: int) -> List[int] that returns all prime numbers up to n.
Use the Sieve of Eratosthenes algorithm for efficiency.

Example: sieve_of_eratosthenes(20) returns [2, 3, 5, 7, 11, 13, 17, 19]
""",
            "tests": [
                {"input": 10, "expected": [2, 3, 5, 7]},
                {"input": 20, "expected": [2, 3, 5, 7, 11, 13, 17, 19]},
                {"input": 2, "expected": [2]},
            ],
        },
    },
    {
        "title": "Binary Search Implementation",
        "description": "Implement binary search algorithm",
        "category": "coding",
        "difficulty": "medium",
        "reward": 45.0,
        "requirements": {
            "language": "python",
            "function_name": "binary_search",
            "spec": """
Write a function binary_search(arr: List[int], target: int) -> int that performs binary search.
- arr is a sorted list of integers
- Returns the index of target if found, -1 otherwise

Example: binary_search([1, 3, 5, 7, 9], 5) returns 2
""",
            "tests": [
                {"input": ([1, 3, 5, 7, 9], 5), "expected": 2},
                {"input": ([1, 3, 5, 7, 9], 1), "expected": 0},
                {"input": ([1, 3, 5, 7, 9], 10), "expected": -1},
            ],
        },
    },
    {
        "title": "Fibonacci Sequence",
        "description": "Generate Fibonacci sequence up to n numbers",
        "category": "coding",
        "difficulty": "easy",
        "reward": 30.0,
        "requirements": {
            "language": "python",
            "function_name": "fibonacci",
            "spec": """
Write a function fibonacci(n: int) -> List[int] that returns the first n Fibonacci numbers.
The sequence starts with 0, 1, and each subsequent number is the sum of the previous two.

Example: fibonacci(7) returns [0, 1, 1, 2, 3, 5, 8]
""",
            "tests": [
                {"input": 5, "expected": [0, 1, 1, 2, 3]},
                {"input": 7, "expected": [0, 1, 1, 2, 3, 5, 8]},
                {"input": 1, "expected": [0]},
            ],
        },
    },
    {
        "title": "Merge Sorted Arrays",
        "description": "Merge two sorted arrays into one sorted array",
        "category": "coding",
        "difficulty": "medium",
        "reward": 40.0,
        "requirements": {
            "language": "python",
            "function_name": "merge_sorted_arrays",
            "spec": """
Write a function merge_sorted_arrays(arr1: List[int], arr2: List[int]) -> List[int] that merges two sorted arrays.
The result should also be sorted.

Example: merge_sorted_arrays([1, 3, 5], [2, 4, 6]) returns [1, 2, 3, 4, 5, 6]
""",
            "tests": [
                {"input": ([1, 3, 5], [2, 4, 6]), "expected": [1, 2, 3, 4, 5, 6]},
                {"input": ([1, 2, 3], [4, 5, 6]), "expected": [1, 2, 3, 4, 5, 6]},
                {"input": ([], [1, 2, 3]), "expected": [1, 2, 3]},
            ],
        },
    },
]


def get_task_by_difficulty(difficulty: str) -> Dict:
    """Get a random task of specified difficulty.

    Args:
        difficulty: Task difficulty level

    Returns:
        Task template
    """
    matching_tasks = [t for t in CODING_TASKS if t["difficulty"] == difficulty]
    if not matching_tasks:
        return CODING_TASKS[0]
    import random

    return random.choice(matching_tasks)


def get_all_tasks() -> List[Dict]:
    """Get all coding task templates.

    Returns:
        List of task templates
    """
    return CODING_TASKS.copy()
