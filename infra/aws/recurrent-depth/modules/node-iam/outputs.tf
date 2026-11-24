output "instance_profile_name" {
  value = aws_iam_instance_profile.node.name
}

output "role_arn" {
  value = aws_iam_role.node.arn
}

output "bucket_policy_json" {
  description = "The node's S3 policy (for tests and review)."
  value       = jsonencode(local.bucket_policy)
}
