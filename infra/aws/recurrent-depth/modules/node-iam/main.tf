# Instance role for measurement nodes. Least privilege on the results bucket:
#
#   read     bundles/* and weights/*   (what a node needs to start)
#   write    runs/*                    (checkpoints) and weights/* (optional mirror)
#   never    delete, or anything outside the bucket
#
# Session Manager access is optional and off by default; nodes run unattended.

locals {
  name       = "${var.project}-${var.environment}-node"
  bucket_arn = "arn:aws:s3:::${var.bucket_name}"

  assume_role_policy = {
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  }

  bucket_policy = {
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListRunPrefixes"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [local.bucket_arn]
        Condition = {
          StringLike = { "s3:prefix" = ["runs/*", "bundles/*", "weights/*"] }
        }
      },
      {
        Sid      = "ReadBundlesAndWeights"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["${local.bucket_arn}/bundles/*", "${local.bucket_arn}/weights/*", "${local.bucket_arn}/runs/*"]
      },
      {
        Sid      = "WriteCheckpointsAndMirror"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:AbortMultipartUpload"]
        Resource = ["${local.bucket_arn}/runs/*", "${local.bucket_arn}/weights/*"]
      },
    ]
  }
}

resource "aws_iam_role" "node" {
  name                 = local.name
  assume_role_policy   = jsonencode(local.assume_role_policy)
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "bucket" {
  name   = "results-bucket"
  role   = aws_iam_role.node.id
  policy = jsonencode(local.bucket_policy)
}

resource "aws_iam_role_policy_attachment" "ssm" {
  count      = var.enable_ssm ? 1 : 0
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "node" {
  name = local.name
  role = aws_iam_role.node.name
}
