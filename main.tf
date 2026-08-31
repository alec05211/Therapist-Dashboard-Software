terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

variable "aws_region" {
  description = "AWS Region in which to use Amazon HealthScribe."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short, lowercase name used in resource names."
  type        = string
  default     = "therapist-dashboard"
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "Terraform"
      Service   = "HealthScribe"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  # The account ID keeps this bucket name globally unique without storing a random
  # suffix in state. Keep project_name lowercase and DNS-compatible.
  healthscribe_bucket_name = "${var.project_name}-healthscribe-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  healthscribe_input_bucket_name = "${var.project_name}-healthscribe-input-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
}

# HealthScribe batch jobs read source recordings from this bucket.
resource "aws_s3_bucket" "healthscribe_input" {
  bucket = local.healthscribe_input_bucket_name
}

resource "aws_s3_bucket_public_access_block" "healthscribe_input" {
  bucket = aws_s3_bucket.healthscribe_input.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "healthscribe_input" {
  bucket = aws_s3_bucket.healthscribe_input.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# HealthScribe sends its post-session transcript and clinical-note artifacts here.
# The bucket is private, ownership-enforced, and encrypted with a customer-managed KMS key.
resource "aws_s3_bucket" "healthscribe_output" {
  bucket = local.healthscribe_bucket_name
}

resource "aws_s3_bucket_public_access_block" "healthscribe_output" {
  bucket = aws_s3_bucket.healthscribe_output.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "healthscribe_output" {
  bucket = aws_s3_bucket.healthscribe_output.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_kms_key" "healthscribe" {
  description             = "Encrypts Amazon HealthScribe input and output artifacts"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "healthscribe" {
  name          = "alias/${var.project_name}-healthscribe"
  target_key_id = aws_kms_key.healthscribe.key_id
}

resource "aws_s3_bucket_server_side_encryption_configuration" "healthscribe_output" {
  bucket = aws_s3_bucket.healthscribe_output.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.healthscribe.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "healthscribe_input" {
  bucket = aws_s3_bucket.healthscribe_input.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.healthscribe.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

# HealthScribe assumes this role while it writes streaming-session artifacts.
data "aws_iam_policy_document" "healthscribe_resource_access_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["transcribe.streaming.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "healthscribe_resource_access" {
  name               = "${var.project_name}-healthscribe-resource-access"
  assume_role_policy = data.aws_iam_policy_document.healthscribe_resource_access_assume_role.json
}

data "aws_iam_policy_document" "healthscribe_resource_access" {
  statement {
    sid       = "WriteHealthScribeArtifacts"
    effect    = "Allow"
    actions = ["s3:PutObject"]
    resources = [
      aws_s3_bucket.healthscribe_output.arn,
      "${aws_s3_bucket.healthscribe_output.arn}/*",
    ]
  }

  statement {
    sid    = "UseHealthScribeEncryptionKey"
    effect = "Allow"

    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
    ]

    resources = [aws_kms_key.healthscribe.arn]
  }
}

resource "aws_iam_role_policy" "healthscribe_resource_access" {
  name   = "healthscribe-resource-access"
  role   = aws_iam_role.healthscribe_resource_access.id
  policy = data.aws_iam_policy_document.healthscribe_resource_access.json
}

# HealthScribe assumes this role for asynchronous batch transcription jobs. It
# needs read access to the uploaded source recording and write access to results.
data "aws_iam_policy_document" "healthscribe_batch_data_access_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["transcribe.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "healthscribe_batch_data_access" {
  name               = "${var.project_name}-healthscribe-batch-data-access"
  assume_role_policy = data.aws_iam_policy_document.healthscribe_batch_data_access_assume_role.json
}

data "aws_iam_policy_document" "healthscribe_batch_data_access" {
  statement {
    sid = "ListHealthScribeInputBucket"

    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]

    resources = [aws_s3_bucket.healthscribe_input.arn]
  }

  statement {
    sid = "ReadHealthScribeInputAudio"

    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
    ]

    resources = ["${aws_s3_bucket.healthscribe_input.arn}/*"]
  }

  statement {
    sid = "WriteHealthScribeBatchArtifacts"

    actions = ["s3:PutObject"]
    resources = [
      aws_s3_bucket.healthscribe_output.arn,
      "${aws_s3_bucket.healthscribe_output.arn}/*",
    ]
  }

  statement {
    sid = "UseHealthScribeEncryptionKey"

    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
    ]

    resources = [aws_kms_key.healthscribe.arn]
  }
}

resource "aws_iam_role_policy" "healthscribe_batch_data_access" {
  name   = "healthscribe-batch-data-access"
  role   = aws_iam_role.healthscribe_batch_data_access.id
  policy = data.aws_iam_policy_document.healthscribe_batch_data_access.json
}

# Attach this policy to the IAM role or user used by your app. HealthScribe itself
# is started at runtime through the streaming API; it is not a Terraform resource.
data "aws_iam_policy_document" "healthscribe_caller" {
  statement {
    sid       = "StartHealthScribeStreaming"
    effect    = "Allow"
    actions   = ["transcribe:StartMedicalScribeStream"]
    resources = ["*"]
  }

  statement {
    sid = "ManageHealthScribeBatchJobs"

    actions = [
      "transcribe:StartMedicalScribeJob",
      "transcribe:GetMedicalScribeJob",
    ]

    resources = ["*"]
  }

  statement {
    sid       = "UploadHealthScribeBatchInput"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.healthscribe_input.arn}/*"]
  }

  statement {
    sid       = "ReadHealthScribeBatchResults"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.healthscribe_output.arn}/*"]
  }

  statement {
    sid = "UseHealthScribeStorageKey"

    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:GenerateDataKey",
      "kms:DescribeKey",
    ]

    resources = [aws_kms_key.healthscribe.arn]
  }

  statement {
    sid       = "PassHealthScribeResourceRole"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.healthscribe_resource_access.arn]
  }

  statement {
    sid       = "PassHealthScribeBatchDataRole"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.healthscribe_batch_data_access.arn]
  }
}

resource "aws_iam_policy" "healthscribe_caller" {
  name        = "${var.project_name}-healthscribe-caller"
  description = "Lets the application run Amazon HealthScribe jobs and access their encrypted input and output"
  policy      = data.aws_iam_policy_document.healthscribe_caller.json
}

output "healthscribe_output_bucket" {
  description = "Provide this bucket name in the HealthScribe output configuration."
  value       = aws_s3_bucket.healthscribe_output.bucket
}

output "healthscribe_input_bucket" {
  description = "Upload batch-job source recordings to this bucket."
  value       = aws_s3_bucket.healthscribe_input.bucket
}

output "healthscribe_kms_key_arn" {
  description = "Provide this key ARN in the HealthScribe output encryption configuration."
  value       = aws_kms_key.healthscribe.arn
}

output "healthscribe_resource_access_role_arn" {
  description = "Provide this role ARN as ResourceAccessRoleArn in the streaming configuration."
  value       = aws_iam_role.healthscribe_resource_access.arn
}

output "healthscribe_batch_data_access_role_arn" {
  description = "Provide this role ARN as DataAccessRoleArn in batch job requests."
  value       = aws_iam_role.healthscribe_batch_data_access.arn
}

output "healthscribe_caller_policy_arn" {
  description = "Attach this policy to the IAM principal that starts HealthScribe sessions and batch jobs."
  value       = aws_iam_policy.healthscribe_caller.arn
}
