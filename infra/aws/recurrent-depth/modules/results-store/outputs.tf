output "bucket_name" {
  description = "Results bucket name."
  value       = aws_s3_bucket.this.id
}

output "bucket_arn" {
  description = "Results bucket ARN."
  value       = aws_s3_bucket.this.arn
}

output "store_uri" {
  description = "Store URI for `recurrent-depth campaign run --store`."
  value       = "s3://${aws_s3_bucket.this.id}/"
}

output "bucket_policy_json" {
  description = "The bucket policy document (for tests and review)."
  value       = jsonencode(local.bucket_policy)
}
