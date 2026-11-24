mock_provider "aws" {}

variables {
  bucket_name = "recurrent-depth-results-dev-test"
}

run "least_privilege_bucket_access" {
  command = apply

  assert {
    condition = alltrue([
      for s in jsondecode(output.bucket_policy_json).Statement :
      alltrue([for a in s.Action : !strcontains(a, "Delete")])
    ])
    error_message = "nodes must never delete objects"
  }

  assert {
    condition = alltrue(flatten([
      for s in jsondecode(output.bucket_policy_json).Statement : [
        for r in s.Resource : startswith(r, "arn:aws:s3:::recurrent-depth-results-dev-test")
      ]
    ]))
    error_message = "every statement must be scoped to the results bucket"
  }

  assert {
    condition = alltrue(flatten([
      for s in jsondecode(output.bucket_policy_json).Statement : [
        for r in s.Resource : !endswith(r, ":::recurrent-depth-results-dev-test/*")
      ]
    ]))
    error_message = "object access must be limited to named prefixes, not the whole bucket"
  }

  assert {
    condition     = length(aws_iam_role_policy_attachment.ssm) == 0
    error_message = "Session Manager is off by default"
  }
}

run "ssm_opt_in" {
  command = apply

  variables {
    enable_ssm = true
  }

  assert {
    condition     = length(aws_iam_role_policy_attachment.ssm) == 1
    error_message = "enable_ssm attaches the Session Manager policy"
  }
}
