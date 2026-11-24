# Results store: one private, versioned bucket for campaign checkpoints,
# run bundles (manifest, plans, toolkit wheel) and staged model weights.
#
# Prefixes:
#   runs/<run_id>/      campaign checkpoints written by `recurrent-depth campaign run`
#   bundles/<run_id>/   what a node downloads at boot
#   weights/<model>/    optional mirror of model weights, expired after weights_retention_days

locals {
  bucket_name = coalesce(var.bucket_name, "${var.project}-results-${var.environment}-${var.name_suffix}")
}

resource "aws_s3_bucket" "this" {
  bucket        = local.bucket_name
  force_destroy = var.force_destroy
}

resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "expire-weight-mirror"
    status = "Enabled"
    filter {
      prefix = "weights/"
    }
    expiration {
      days = var.weights_retention_days
    }
  }

  depends_on = [aws_s3_bucket_versioning.this]
}

locals {
  bucket_policy = {
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [aws_s3_bucket.this.arn, "${aws_s3_bucket.this.arn}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      }
    ]
  }
}

resource "aws_s3_bucket_policy" "this" {
  bucket     = aws_s3_bucket.this.id
  policy     = jsonencode(local.bucket_policy)
  depends_on = [aws_s3_bucket_public_access_block.this]
}
