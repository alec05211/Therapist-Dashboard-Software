data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  database_identifier = "${var.project_name}-postgres"
  input_bucket_name   = "${var.project_name}-input-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  output_bucket_name  = "${var.project_name}-output-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
}

# This VPC is deliberately public only to make a local, mock-data demo practical.
# It is not the replacement for the private VPC in the repository root stack.
resource "aws_vpc" "demo" {
  cidr_block           = "10.56.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
}

resource "aws_internet_gateway" "demo" {
  vpc_id = aws_vpc.demo.id
}

resource "aws_subnet" "public" {
  count = 2

  vpc_id                  = aws_vpc.demo.id
  cidr_block              = cidrsubnet(aws_vpc.demo.cidr_block, 4, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-${count.index + 1}"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.demo.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.demo.id
  }
}

resource "aws_route_table_association" "public" {
  count = length(aws_subnet.public)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_db_subnet_group" "demo" {
  name       = "${var.project_name}-public"
  subnet_ids = aws_subnet.public[*].id
}

resource "aws_security_group" "database" {
  name        = "${var.project_name}-database"
  description = "Demo PostgreSQL: only the explicitly approved operator CIDR may connect."
  vpc_id      = aws_vpc.demo.id

  ingress {
    description = "TLS PostgreSQL from the current demo operator"
    protocol    = "tcp"
    from_port   = 5432
    to_port     = 5432
    cidr_blocks = [var.demo_allowed_cidr]
  }

  # RDS does not initiate network connections.
  egress = []
}

resource "aws_kms_key" "database" {
  description             = "Demo RDS encryption key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

resource "aws_kms_alias" "database" {
  name          = "alias/${var.project_name}-database"
  target_key_id = aws_kms_key.database.key_id
}

resource "aws_db_parameter_group" "database" {
  name   = "${var.project_name}-postgres16"
  family = "postgres16"

  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "immediate"
  }

  parameter {
    name         = "log_statement"
    value        = "none"
    apply_method = "immediate"
  }
}

resource "aws_db_instance" "database" {
  identifier     = local.database_identifier
  engine         = "postgres"
  engine_version = "16.15"
  instance_class = var.database_instance_class

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.database.arn

  db_name                     = var.database_name
  username                    = "database_admin"
  manage_master_user_password = true
  master_user_secret_kms_key_id = aws_kms_key.database.arn

  db_subnet_group_name   = aws_db_subnet_group.demo.name
  vpc_security_group_ids = [aws_security_group.database.id]
  parameter_group_name   = aws_db_parameter_group.database.name
  publicly_accessible    = true
  multi_az               = false

  backup_retention_period = 1
  deletion_protection     = false
  skip_final_snapshot     = !var.take_final_snapshot
  final_snapshot_identifier = var.take_final_snapshot ? var.final_snapshot_identifier : null

  lifecycle {
    precondition {
      condition     = !var.take_final_snapshot || length(trimspace(var.final_snapshot_identifier)) > 0
      error_message = "Set a unique final_snapshot_identifier when take_final_snapshot is true."
    }
  }

  tags = {
    DataClassification = "synthetic-demo-only"
    AutoDestroy        = "review-before-destroy"
  }
}

resource "aws_kms_key" "artifacts" {
  description             = "Demo HealthScribe artifact encryption key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

resource "aws_kms_alias" "artifacts" {
  name          = "alias/${var.project_name}-artifacts"
  target_key_id = aws_kms_key.artifacts.key_id
}

resource "aws_s3_bucket" "input" {
  bucket        = local.input_bucket_name
  force_destroy = var.force_destroy_artifact_buckets
}

resource "aws_s3_bucket" "output" {
  bucket        = local.output_bucket_name
  force_destroy = var.force_destroy_artifact_buckets
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each = {
    input  = aws_s3_bucket.input.id
    output = aws_s3_bucket.output.id
  }

  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "all" {
  for_each = {
    input  = aws_s3_bucket.input.id
    output = aws_s3_bucket.output.id
  }

  bucket = each.value
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "all" {
  for_each = {
    input  = aws_s3_bucket.input.id
    output = aws_s3_bucket.output.id
  }

  bucket = each.value
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.artifacts.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "all" {
  for_each = {
    input  = aws_s3_bucket.input.id
    output = aws_s3_bucket.output.id
  }

  bucket = each.value
  rule {
    id     = "expire-mock-artifacts"
    status = "Enabled"

    filter {}

    expiration {
      days = var.artifact_retention_days
    }
  }
}

data "aws_iam_policy_document" "healthscribe_batch_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["transcribe.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "healthscribe_batch" {
  name               = "${var.project_name}-healthscribe-batch"
  assume_role_policy = data.aws_iam_policy_document.healthscribe_batch_assume_role.json
}

data "aws_iam_policy_document" "healthscribe_batch" {
  statement {
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = [aws_s3_bucket.input.arn]
  }

  statement {
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${aws_s3_bucket.input.arn}/*"]
  }

  statement {
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.output.arn}/*"]
  }

  statement {
    actions = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey*", "kms:DescribeKey"]
    resources = [aws_kms_key.artifacts.arn]
  }
}

resource "aws_iam_role_policy" "healthscribe_batch" {
  name   = "healthscribe-batch-artifacts"
  role   = aws_iam_role.healthscribe_batch.id
  policy = data.aws_iam_policy_document.healthscribe_batch.json
}

# Attach this managed policy to the IAM principal that runs the local FastAPI
# server, unless that principal already has these narrowly scoped permissions.
data "aws_iam_policy_document" "healthscribe_caller" {
  statement {
    actions   = ["transcribe:StartMedicalScribeJob", "transcribe:GetMedicalScribeJob"]
    resources = ["*"]
  }

  statement {
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.input.arn}/*"]
  }

  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.output.arn}/*"]
  }

  statement {
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = [aws_kms_key.artifacts.arn]
  }

  statement {
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.healthscribe_batch.arn]
  }
}

resource "aws_iam_policy" "healthscribe_caller" {
  name        = "${var.project_name}-healthscribe-caller"
  description = "Lets the local demo application run HealthScribe jobs and access demo artifacts"
  policy      = data.aws_iam_policy_document.healthscribe_caller.json
}
