output "reaper_function_name" {
  value = aws_lambda_function.reaper.function_name
}

output "reaper_policy_json" {
  description = "The reaper's IAM policy (for tests and review)."
  value       = jsonencode(local.reaper_policy)
}

output "budget_name" {
  value = length(aws_budgets_budget.monthly) > 0 ? aws_budgets_budget.monthly[0].name : null
}
