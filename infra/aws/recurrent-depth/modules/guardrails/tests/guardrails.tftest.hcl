mock_provider "aws" {
  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::000000000000:role/recurrent-depth-dev-reaper"
    }
  }
  mock_resource "aws_lambda_function" {
    defaults = {
      arn = "arn:aws:lambda:us-east-1:000000000000:function:recurrent-depth-dev-reaper"
    }
  }
  mock_resource "aws_cloudwatch_event_rule" {
    defaults = {
      arn = "arn:aws:events:us-east-1:000000000000:rule/recurrent-depth-dev-reaper"
    }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = {
      arn = "arn:aws:logs:us-east-1:000000000000:log-group:/aws/lambda/recurrent-depth-dev-reaper"
    }
  }
}

run "reaper_is_scheduled_and_scoped" {
  command = apply

  assert {
    condition     = aws_cloudwatch_event_rule.reaper.schedule_expression == "rate(5 minutes)"
    error_message = "the reaper runs every 5 minutes by default"
  }

  assert {
    condition     = aws_lambda_function.reaper.environment[0].variables["HARD_CAP_HOURS"] == "12"
    error_message = "the hard cap reaches the function"
  }

  assert {
    condition = anytrue([
      for s in jsondecode(output.reaper_policy_json).Statement :
      contains(s.Action, "ec2:TerminateInstances") && s.Condition.StringEquals["aws:ResourceTag/Project"] == "recurrent-depth"
    ])
    error_message = "the reaper may only terminate Project-tagged instances"
  }

  assert {
    condition     = length(aws_budgets_budget.monthly) == 0
    error_message = "no budget without recipients"
  }
}

run "budget_with_recipients" {
  command = apply

  variables {
    alert_emails       = ["alerts@example.com"]
    monthly_budget_usd = 300
  }

  assert {
    condition     = aws_budgets_budget.monthly[0].limit_amount == "300"
    error_message = "the budget limit comes from monthly_budget_usd"
  }

  assert {
    condition     = length(aws_budgets_budget.monthly[0].notification) == 4
    error_message = "alerts at 50, 80 and 100 percent actual, and 100 percent forecast"
  }
}

run "rejects_singular_rate" {
  command = plan

  variables {
    reaper_interval_minutes = 1
  }

  expect_failures = [var.reaper_interval_minutes]
}
