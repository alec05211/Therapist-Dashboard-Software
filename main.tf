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

variable "database_name" {
  description = "Name of the initial PostgreSQL database."
  type        = string
  default     = "therapist_dashboard"
}

variable "database_instance_class" {
  description = "RDS instance size. Keep the development default deliberately small."
  type        = string
  default     = "db.t4g.micro"
}

variable "database_vpc_cidr" {
  description = "Dedicated private VPC range for database and future application workloads."
  type        = string
  default     = "10.46.0.0/16"
}

variable "migration_image_tag" {
  description = "Immutable container-image tag used by the one-off Fargate migration task."
  type        = string
  default     = "initial"
}

variable "enable_migration_task_network" {
  description = "Temporarily create the private endpoints and RDS rule required to run a migration task."
  type        = bool
  default     = false
}

variable "enable_migration_network_diagnostics" {
  description = "Temporarily publish VPC flow metadata while diagnosing the private migration task."
  type        = bool
  default     = false
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
data "aws_availability_zones" "available" {
  state = "available"
}


locals {
  # The account ID keeps this bucket name globally unique without storing a random
  # suffix in state. Keep project_name lowercase and DNS-compatible.
  healthscribe_bucket_name = "${var.project_name}-healthscribe-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  healthscribe_input_bucket_name = "${var.project_name}-healthscribe-input-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  database_identifier            = "${var.project_name}-postgres"
}


# Database network boundary. The database has no public address and the security
# group has no ingress rule until an application workload is intentionally added.
resource "aws_vpc" "database" {
  cidr_block           = var.database_vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
}

resource "aws_subnet" "database_private" {
  count = 2

  vpc_id            = aws_vpc.database.id
  cidr_block        = cidrsubnet(var.database_vpc_cidr, 4, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "${var.project_name}-database-private-${count.index + 1}"
  }
}

resource "aws_db_subnet_group" "database" {
  name       = "${var.project_name}-database-private"
  subnet_ids = aws_subnet.database_private[*].id
}

resource "aws_security_group" "database" {
  name        = "${var.project_name}-database"
  description = "No public ingress; future application security groups are added explicitly."
  vpc_id      = aws_vpc.database.id

  # RDS does not initiate outbound connections. Avoid a permissive default
  # egress rule; security-group ingress is introduced only for the app tier.
  egress = []
}

resource "aws_kms_key" "database" {
  description             = "Encrypts the therapist dashboard PostgreSQL database and RDS-managed master secret"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "database" {
  name          = "alias/${var.project_name}-database"
  target_key_id = aws_kms_key.database.key_id
}

resource "aws_db_parameter_group" "database" {
  name        = "${var.project_name}-postgres16"
  family      = "postgres16"
  description = "Security and operational defaults for therapist dashboard PostgreSQL"

  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "immediate"
  }

  # Metadata-only connection logs help incident investigation while avoiding SQL
  # statement logging, which could expose sensitive clinical text.
  parameter {
    name         = "log_connections"
    value        = "1"
    apply_method = "immediate"
  }

  parameter {
    name         = "log_disconnections"
    value        = "1"
    apply_method = "immediate"
  }

  parameter {
    name         = "log_min_duration_statement"
    value        = "1000"
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

  db_subnet_group_name   = aws_db_subnet_group.database.name
  vpc_security_group_ids = [aws_security_group.database.id]
  parameter_group_name   = aws_db_parameter_group.database.name
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period = 7
  backup_window           = "04:00-04:30"
  maintenance_window      = "sun:05:00-sun:05:30"
  copy_tags_to_snapshot   = true
  deletion_protection     = true
  skip_final_snapshot     = false
  final_snapshot_identifier = "${local.database_identifier}-final"

  auto_minor_version_upgrade  = true
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  performance_insights_enabled = true
  performance_insights_retention_period = 7

  tags = {
    DataClassification = "sensitive"
    Component          = "relational-database"
  }
}

# The migration task runs only when invoked explicitly. It is isolated from the
# public internet and has access only to its required AWS APIs and PostgreSQL.
resource "aws_ecr_repository" "database_migration" {
  name                 = "${var.project_name}-database-migration"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_cloudwatch_log_group" "database_migration" {
  name              = "/${var.project_name}/database-migration"
  retention_in_days = 30
}

# This is intentionally opt-in and short-retention. Flow logs contain network
# metadata only (not request bodies, database contents, or secrets) and let us
# diagnose private endpoint connectivity without weakening network controls.
resource "aws_cloudwatch_log_group" "database_migration_flow_logs" {
  count = var.enable_migration_network_diagnostics ? 1 : 0

  name              = "/${var.project_name}/database-migration-flow-logs"
  retention_in_days = 7
}

data "aws_iam_policy_document" "migration_flow_logs_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["vpc-flow-logs.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "migration_flow_logs" {
  count = var.enable_migration_network_diagnostics ? 1 : 0

  name               = "${var.project_name}-migration-flow-logs"
  assume_role_policy = data.aws_iam_policy_document.migration_flow_logs_assume_role.json
}

data "aws_iam_policy_document" "migration_flow_logs" {
  count = var.enable_migration_network_diagnostics ? 1 : 0

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.database_migration_flow_logs[0].arn}:*"]
  }
  statement {
    effect = "Allow"
    actions = [
      "logs:DescribeLogGroups",
      "logs:DescribeLogStreams",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "migration_flow_logs" {
  count = var.enable_migration_network_diagnostics ? 1 : 0

  name   = "migration-flow-logs"
  role   = aws_iam_role.migration_flow_logs[0].id
  policy = data.aws_iam_policy_document.migration_flow_logs[0].json
}

resource "aws_flow_log" "database_migration" {
  count = var.enable_migration_network_diagnostics ? 1 : 0

  iam_role_arn             = aws_iam_role.migration_flow_logs[0].arn
  log_destination          = aws_cloudwatch_log_group.database_migration_flow_logs[0].arn
  log_destination_type     = "cloud-watch-logs"
  traffic_type             = "ALL"
  vpc_id                   = aws_vpc.database.id
  max_aggregation_interval = 60
}

resource "aws_ecs_cluster" "database_migration" {
  name = "${var.project_name}-database-migration"
}

resource "aws_security_group" "database_migration_task" {
  name        = "${var.project_name}-database-migration-task"
  description = "No ingress; one-off Fargate database migration task."
  vpc_id      = aws_vpc.database.id
  egress      = []

  # Keep the default allow-all egress rule revoked, while the individual
  # aws_vpc_security_group_egress_rule resources below remain the sole
  # authority for the task's permitted outbound paths. Without this, the
  # inline empty list and standalone rules continually remove each other.
  lifecycle {
    ignore_changes = [egress]
  }
}

resource "aws_security_group" "database_migration_endpoints" {
  count = var.enable_migration_task_network ? 1 : 0

  name        = "${var.project_name}-database-migration-endpoints"
  description = "Private AWS API endpoints for the one-off migration task."
  vpc_id      = aws_vpc.database.id
  egress      = []
}

resource "aws_vpc_security_group_ingress_rule" "migration_endpoints_from_task" {
  count = var.enable_migration_task_network ? 1 : 0

  security_group_id            = aws_security_group.database_migration_endpoints[0].id
  referenced_security_group_id = aws_security_group.database_migration_task.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  description                  = "Private AWS API calls from migration task"
}

resource "aws_vpc_security_group_egress_rule" "migration_task_to_endpoints" {
  count = var.enable_migration_task_network ? 1 : 0

  security_group_id            = aws_security_group.database_migration_task.id
  referenced_security_group_id = aws_security_group.database_migration_endpoints[0].id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  description                  = "ECR, Secrets Manager, KMS, and CloudWatch Logs through PrivateLink"
}

# ECR stores container layers in S3. The gateway endpoint supplies the route,
# while this rule permits only HTTPS to AWS's managed S3 prefix list.
data "aws_prefix_list" "s3" {
  name = "com.amazonaws.${var.aws_region}.s3"
}

resource "aws_vpc_security_group_egress_rule" "migration_task_to_s3" {
  count = var.enable_migration_task_network ? 1 : 0

  security_group_id = aws_security_group.database_migration_task.id
  prefix_list_id    = data.aws_prefix_list.s3.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  description       = "ECR image layers through the private S3 gateway endpoint"
}

resource "aws_vpc_security_group_egress_rule" "migration_task_to_database" {
  count = var.enable_migration_task_network ? 1 : 0

  security_group_id            = aws_security_group.database_migration_task.id
  referenced_security_group_id = aws_security_group.database.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  description                  = "PostgreSQL migration connection"
}

resource "aws_vpc_security_group_ingress_rule" "database_from_migration_task" {
  count = var.enable_migration_task_network ? 1 : 0

  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.database_migration_task.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  description                  = "One-off private Fargate migration task only"
}

resource "aws_vpc_security_group_egress_rule" "migration_task_dns_udp" {
  count = var.enable_migration_task_network ? 1 : 0

  security_group_id = aws_security_group.database_migration_task.id
  cidr_ipv4         = var.database_vpc_cidr
  ip_protocol       = "udp"
  from_port         = 53
  to_port           = 53
  description       = "Private VPC DNS"
}

resource "aws_vpc_security_group_egress_rule" "migration_task_dns_tcp" {
  count = var.enable_migration_task_network ? 1 : 0

  security_group_id = aws_security_group.database_migration_task.id
  cidr_ipv4         = var.database_vpc_cidr
  ip_protocol       = "tcp"
  from_port         = 53
  to_port           = 53
  description       = "Private VPC DNS"
}

resource "aws_vpc_endpoint" "database_migration_apis" {
  for_each = var.enable_migration_task_network ? toset(["ecr.api", "ecr.dkr", "logs", "secretsmanager", "kms"]) : toset([])

  vpc_id              = aws_vpc.database.id
  service_name        = "com.amazonaws.${var.aws_region}.${each.value}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = [aws_subnet.database_private[0].id]
  security_group_ids  = [aws_security_group.database_migration_endpoints[0].id]
}

data "aws_route_tables" "database" {
  filter {
    name   = "vpc-id"
    values = [aws_vpc.database.id]
  }
}

resource "aws_vpc_endpoint" "database_migration_s3" {
  count = var.enable_migration_task_network ? 1 : 0

  vpc_id            = aws_vpc.database.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = data.aws_route_tables.database.ids
}

data "aws_iam_policy_document" "migration_task_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "migration_task_execution" {
  name               = "${var.project_name}-database-migration-execution"
  assume_role_policy = data.aws_iam_policy_document.migration_task_assume_role.json
}

data "aws_iam_policy_document" "migration_task_execution" {
  statement {
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    effect = "Allow"
    actions = ["ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"]
    resources = [aws_ecr_repository.database_migration.arn]
  }
  statement {
    effect = "Allow"
    actions = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.database_migration.arn}:*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_db_instance.database.master_user_secret[0].secret_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.database.arn]
  }
}

resource "aws_iam_role_policy" "migration_task_execution" {
  name   = "database-migration-execution"
  role   = aws_iam_role.migration_task_execution.id
  policy = data.aws_iam_policy_document.migration_task_execution.json
}

resource "aws_ecs_task_definition" "database_migration" {
  family                   = "${var.project_name}-database-migration"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.migration_task_execution.arn

  container_definitions = jsonencode([{
    name      = "migration"
    image     = "${aws_ecr_repository.database_migration.repository_url}:${var.migration_image_tag}"
    essential = true
    environment = [
      { name = "DATABASE_HOST", value = aws_db_instance.database.address },
      { name = "DATABASE_NAME", value = var.database_name },
    ]
    secrets = [
      { name = "DATABASE_USERNAME", valueFrom = "${aws_db_instance.database.master_user_secret[0].secret_arn}:username::" },
      { name = "DATABASE_PASSWORD", valueFrom = "${aws_db_instance.database.master_user_secret[0].secret_arn}:password::" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.database_migration.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "migration"
      }
    }
  }])
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

output "database_endpoint" {
  description = "Private RDS endpoint. It is reachable only from an explicitly authorized workload in the database VPC."
  value       = aws_db_instance.database.address
}

output "database_port" {
  description = "Private PostgreSQL port."
  value       = aws_db_instance.database.port
}

output "database_name" {
  description = "Initial PostgreSQL database name."
  value       = aws_db_instance.database.db_name
}

output "database_master_user_secret_arn" {
  description = "RDS-managed secret ARN for migration/admin use. Do not put its value in source control or browser code."
  value       = aws_db_instance.database.master_user_secret[0].secret_arn
  sensitive   = true
}

output "database_security_group_id" {
  description = "Attach future in-VPC application security groups through explicit database ingress rules."
  value       = aws_security_group.database.id
}

output "database_migration_repository_url" {
  description = "Private ECR repository for the database migration task image."
  value       = aws_ecr_repository.database_migration.repository_url
}

output "database_migration_cluster_name" {
  description = "ECS cluster used only for explicitly invoked migration tasks."
  value       = aws_ecs_cluster.database_migration.name
}

output "database_migration_task_definition_arn" {
  description = "Task definition to supply to aws ecs run-task after the migration image is pushed."
  value       = aws_ecs_task_definition.database_migration.arn
}

output "database_migration_task_security_group_id" {
  description = "Security group for the one-off Fargate migration task."
  value       = aws_security_group.database_migration_task.id
}

output "database_private_subnet_id" {
  description = "Private subnet used by the one-off Fargate migration task."
  value       = aws_subnet.database_private[0].id
}

output "database_migration_flow_log_group_name" {
  description = "Temporary VPC Flow Logs group; null unless diagnostics are enabled."
  value       = try(aws_cloudwatch_log_group.database_migration_flow_logs[0].name, null)
}
