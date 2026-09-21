terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

variable "aws_region" { default = "us-east-1" }
variable "environment" {
  type = string
  validation {
    condition     = contains(["demo", "staging", "production"], var.environment)
    error_message = "Use demo, staging, or production."
  }
}
variable "organization_ids" {
  type = set(string)
  validation {
    condition     = alltrue([for id in var.organization_ids : can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", id))])
    error_message = "Organization IDs must be canonical lowercase UUIDs."
  }
}
variable "application_role_name" {
  description = "Optional existing application role to receive object access; local administrators already have access."
  type        = string
  default     = ""
}
provider "aws" {
  region = var.aws_region
  default_tags {
    tags = { Project = "therapist-dashboard", Environment = var.environment, ManagedBy = "Terraform" }
  }
}
data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "organization" {
  for_each      = var.organization_ids
  bucket        = "td-${var.environment}-${data.aws_caller_identity.current.account_id}-${replace(each.key, "-", "")}"
  force_destroy = false
  tags          = { OrganizationId = each.key }
  lifecycle { prevent_destroy = true }
}
resource "aws_s3_bucket_public_access_block" "organization" {
  for_each                = aws_s3_bucket.organization
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_ownership_controls" "organization" {
  for_each = aws_s3_bucket.organization
  bucket   = each.value.id
  rule { object_ownership = "BucketOwnerEnforced" }
}
resource "aws_s3_bucket_versioning" "organization" {
  for_each = aws_s3_bucket.organization
  bucket   = each.value.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_kms_key" "organization" {
  for_each                = var.organization_ids
  description             = "Therapist Dashboard ${var.environment} organization ${each.key}"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = { OrganizationId = each.key }
  lifecycle { prevent_destroy = true }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "organization" {
  for_each = aws_s3_bucket.organization
  bucket   = each.value.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.organization[each.key].arn
    }
  }
}
resource "aws_s3_bucket_policy" "organization" {
  for_each = aws_s3_bucket.organization
  bucket   = each.value.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Sid       = "RequireTLS", Effect = "Deny", Principal = "*", Action = "s3:*",
    Resource  = [each.value.arn, "${each.value.arn}/*"],
    Condition = { Bool = { "aws:SecureTransport" = "false" } }
  }] })
}
resource "aws_iam_role" "healthscribe" {
  for_each = var.organization_ids
  name     = "td-${var.environment}-scribe-${each.key}"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "transcribe.amazonaws.com" }, Action = "sts:AssumeRole",
    Condition = {
      StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id },
      ArnLike      = { "aws:SourceArn" = "arn:aws:transcribe:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*" }
    }
  }] })
}
resource "aws_iam_role_policy" "healthscribe" {
  for_each = var.organization_ids
  role     = aws_iam_role.healthscribe[each.key].id
  name     = "organization-artifacts"
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:GetBucketLocation", "s3:ListBucket"], Resource = aws_s3_bucket.organization[each.key].arn },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:GetObjectVersion"], Resource = "${aws_s3_bucket.organization[each.key].arn}/clients/*/sessions/*/audio/*" },
    { Effect = "Allow", Action = ["s3:PutObject"], Resource = "${aws_s3_bucket.organization[each.key].arn}/*" },
    { Effect = "Allow", Action = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey*", "kms:DescribeKey"], Resource = aws_kms_key.organization[each.key].arn }
  ] })
}
resource "aws_iam_policy" "application" {
  for_each = var.organization_ids
  name     = "td-${var.environment}-storage-${each.key}"
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"], Resource = "${aws_s3_bucket.organization[each.key].arn}/*" },
    { Effect = "Allow", Action = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey", "kms:DescribeKey"], Resource = aws_kms_key.organization[each.key].arn },
    { Effect = "Allow", Action = ["iam:PassRole"], Resource = aws_iam_role.healthscribe[each.key].arn, Condition = { StringEquals = { "iam:PassedToService" = "transcribe.amazonaws.com" } } },
    { Effect = "Allow", Action = ["transcribe:StartMedicalScribeJob", "transcribe:GetMedicalScribeJob"], Resource = "*" }
  ] })
}
resource "aws_iam_role_policy_attachment" "application" {
  for_each   = var.application_role_name == "" ? toset([]) : var.organization_ids
  role       = var.application_role_name
  policy_arn = aws_iam_policy.application[each.key].arn
}
output "organization_storage" {
  value = { for id in var.organization_ids : id => {
    bucket                 = aws_s3_bucket.organization[id].id
    region                 = var.aws_region
    kms_key_arn            = aws_kms_key.organization[id].arn
    healthscribe_role_arn  = aws_iam_role.healthscribe[id].arn
    application_policy_arn = aws_iam_policy.application[id].arn
  } }
}
