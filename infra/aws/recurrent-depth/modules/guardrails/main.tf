# Cost guardrails, independent of the nodes themselves:
#
#   1. a reaper Lambda, run every reaper_interval_minutes, that terminates any
#      Project-tagged instance older than its MaxHours tag (capped at
#      hard_cap_hours) plus a grace period;
#   2. a monthly AWS Budget that emails at 50%, 80% and 100% of actual spend
#      and at 100% of forecast spend.
#
# The node watchdog and the campaign deadline are the first two limits; these
# catch whatever slips past them.

locals {
  name = "${var.project}-${var.environment}"

  reaper_policy = {
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "DescribeInstances"
        Effect   = "Allow"
        Action   = ["ec2:DescribeInstances"]
        Resource = "*"
      },
      {
        Sid      = "TerminateProjectInstancesOnly"
        Effect   = "Allow"
        Action   = ["ec2:TerminateInstances"]
        Resource = "arn:aws:ec2:${var.aws_region}:*:instance/*"
        Condition = {
          StringEquals = { "aws:ResourceTag/Project" = var.project }
        }
      },
      {
        Sid      = "WriteOwnLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.reaper.arn}:*"
      },
    ]
  }
}

data "archive_file" "reaper" {
  type        = "zip"
  source_file = "${path.module}/lambda/reaper.py"
  output_path = "${path.module}/.build/reaper.zip"
}

resource "aws_cloudwatch_log_group" "reaper" {
  name              = "/aws/lambda/${local.name}-reaper"
  retention_in_days = 30
}

resource "aws_iam_role" "reaper" {
  name = "${local.name}-reaper"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "reaper" {
  name   = "reaper"
  role   = aws_iam_role.reaper.id
  policy = jsonencode(local.reaper_policy)
}

resource "aws_lambda_function" "reaper" {
  function_name    = "${local.name}-reaper"
  role             = aws_iam_role.reaper.arn
  runtime          = "python3.13"
  handler          = "reaper.handler"
  filename         = data.archive_file.reaper.output_path
  source_code_hash = data.archive_file.reaper.output_base64sha256
  timeout          = 60
  memory_size      = 128

  environment {
    variables = {
      PROJECT           = var.project
      DEFAULT_MAX_HOURS = tostring(var.default_max_hours)
      HARD_CAP_HOURS    = tostring(var.hard_cap_hours)
      GRACE_MINUTES     = tostring(var.grace_minutes)
      DRY_RUN           = tostring(var.reaper_dry_run)
    }
  }

  depends_on = [aws_cloudwatch_log_group.reaper]
}

resource "aws_cloudwatch_event_rule" "reaper" {
  name                = "${local.name}-reaper"
  description         = "Terminate recurrent-depth nodes past their time limit"
  schedule_expression = "rate(${var.reaper_interval_minutes} minutes)"
}

resource "aws_cloudwatch_event_target" "reaper" {
  rule = aws_cloudwatch_event_rule.reaper.name
  arn  = aws_lambda_function.reaper.arn
}

resource "aws_lambda_permission" "events" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.reaper.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.reaper.arn
}

resource "aws_budgets_budget" "monthly" {
  count        = length(var.alert_emails) > 0 ? 1 : 0
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = var.alert_emails
    }
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = var.alert_emails
  }
}
