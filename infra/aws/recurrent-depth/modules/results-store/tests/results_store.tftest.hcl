# Offline unit tests: `terraform test` with a mocked AWS provider (no credentials, no network).

mock_provider "aws" {
  mock_resource "aws_s3_bucket" {
    defaults = {
      arn = "arn:aws:s3:::recurrent-depth-results-dev-test"
    }
  }
}

variables {
  name_suffix = "test"
}

run "default_name_and_private_bucket" {
  command = apply

  assert {
    condition     = aws_s3_bucket.this.bucket == "recurrent-depth-results-dev-test"
    error_message = "default bucket name should be <project>-results-<environment>-<suffix>"
  }

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.this.block_public_acls,
      aws_s3_bucket_public_access_block.this.block_public_policy,
      aws_s3_bucket_public_access_block.this.ignore_public_acls,
      aws_s3_bucket_public_access_block.this.restrict_public_buckets,
    ])
    error_message = "all public access must be blocked"
  }

  assert {
    condition     = aws_s3_bucket_versioning.this.versioning_configuration[0].status == "Enabled"
    error_message = "versioning protects checkpoints from overwrite"
  }

  assert {
    condition     = !aws_s3_bucket.this.force_destroy
    error_message = "force_destroy must default to false"
  }

  assert {
    condition = anytrue([
      for r in aws_s3_bucket_server_side_encryption_configuration.this.rule :
      anytrue([for d in r.apply_server_side_encryption_by_default : d.sse_algorithm == "AES256"])
    ])
    error_message = "default encryption must be configured"
  }

  assert {
    condition     = jsondecode(output.bucket_policy_json).Statement[0].Condition.Bool["aws:SecureTransport"] == "false"
    error_message = "the bucket policy must deny non-TLS access"
  }

  assert {
    condition     = output.store_uri == "s3://${aws_s3_bucket.this.id}/"
    error_message = "store_uri must be an s3:// URI for the campaign runner"
  }
}

run "weights_expire" {
  command = apply

  variables {
    weights_retention_days = 7
  }

  assert {
    condition = anytrue([
      for r in aws_s3_bucket_lifecycle_configuration.this.rule :
      r.id == "expire-weight-mirror" && r.expiration[0].days == 7 && r.filter[0].prefix == "weights/"
    ])
    error_message = "the weights/ mirror must expire after weights_retention_days"
  }
}

run "rejects_bad_suffix" {
  command = plan

  variables {
    name_suffix = "Not_Valid"
  }

  expect_failures = [var.name_suffix]
}
