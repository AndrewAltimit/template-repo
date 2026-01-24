# AgentCore Runtime Module
#
# Creates an AWS Bedrock AgentCore Runtime using the AWSCC provider

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
}

# CloudWatch Log Group for runtime logs
resource "aws_cloudwatch_log_group" "runtime" {
  name              = "/aws/bedrock-agentcore/runtimes/${var.runtime_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# AgentCore Runtime using AWSCC provider
resource "awscc_bedrockagentcore_runtime" "main" {
  agent_runtime_name = var.runtime_name
  description        = var.description

  agent_runtime_artifact = {
    container_configuration = {
      container_uri = var.container_uri
    }
  }

  network_configuration = {
    network_mode = var.network_mode
  }

  protocol_configuration = var.protocol

  role_arn = var.runtime_role_arn

  environment_variables = merge(
    {
      AWS_REGION    = local.region
      LOG_LEVEL     = var.log_level
      OTEL_EXPORTER = "otlp"
    },
    var.environment_variables
  )

  tags = var.tags
}
