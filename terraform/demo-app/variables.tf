variable "aws_region" {
  description = "AWS Region containing the existing synthetic demo data stack."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name prefix for replaceable hosted-demo resources."
  type        = string
  default     = "therapist-dashboard-demo-app"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,40}$", var.project_name))
    error_message = "project_name must be 3-40 lowercase letters, numbers, or hyphens."
  }
}

variable "domain_name" {
  description = "Temporary DuckDNS hostname, for example therapist-dashboard-demo.duckdns.org."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.duckdns\\.org$", var.domain_name))
    error_message = "domain_name must be one DuckDNS hostname such as therapist-dashboard-demo.duckdns.org."
  }
}

variable "instance_type" {
  description = "ARM64 EC2 instance type for the compact synthetic demo host."
  type        = string
  default     = "t4g.small"

  validation {
    condition     = startswith(var.instance_type, "t4g.")
    error_message = "The initial demo host uses an ARM64 t4g instance type."
  }
}

variable "root_volume_size_gib" {
  description = "Encrypted gp3 root volume size for code, images, and temporary synthetic-demo files."
  type        = number
  default     = 24

  validation {
    condition     = var.root_volume_size_gib >= 16 && var.root_volume_size_gib <= 100
    error_message = "root_volume_size_gib must be between 16 and 100 GiB."
  }
}

variable "vpc_id" {
  description = "VPC ID output by terraform/demo."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs output by terraform/demo."
  type        = list(string)

  validation {
    condition     = length(var.public_subnet_ids) >= 1
    error_message = "At least one public subnet ID is required."
  }
}

variable "database_client_security_group_id" {
  description = "Persistent database-client security group output by terraform/demo."
  type        = string
}

variable "database_endpoint" {
  description = "Synthetic demo RDS endpoint output by terraform/demo."
  type        = string
}

variable "database_name" {
  description = "Synthetic demo PostgreSQL database name output by terraform/demo."
  type        = string
}

variable "database_secret_arn" {
  description = "ARN, not value, of the RDS-managed credential secret."
  type        = string
  sensitive   = true
}

variable "database_kms_key_arn" {
  description = "KMS key ARN used to encrypt the RDS-managed credential secret."
  type        = string
}

variable "hosted_app_runtime_secret_arn" {
  description = "Persistent Secrets Manager ARN containing hosted Auth0 runtime configuration."
  type        = string
}

variable "clinical_synthesis_secret_arn" {
  description = "Persistent Secrets Manager ARN containing the hosted clinical-synthesis API credential."
  type        = string
}

variable "healthscribe_input_bucket" {
  description = "Synthetic HealthScribe input bucket output by terraform/demo."
  type        = string
}

variable "healthscribe_output_bucket" {
  description = "Synthetic HealthScribe output bucket output by terraform/demo."
  type        = string
}

variable "healthscribe_batch_data_access_role_arn" {
  description = "Batch data-access role passed to HealthScribe jobs."
  type        = string
}

variable "healthscribe_caller_policy_arn" {
  description = "Existing least-privilege demo policy for HealthScribe, S3, KMS, and PassRole access."
  type        = string
}

variable "organization_storage_policy_arns" {
  description = "Organization-scoped storage policies that let the hosted API restore and publish authorized session artifacts."
  type        = set(string)
  default     = []

  validation {
    condition = alltrue([
      for arn in var.organization_storage_policy_arns :
      can(regex("^arn:aws:iam::[0-9]{12}:policy/td-[a-z0-9-]+-storage-[0-9a-f-]{36}$", arn))
    ])
    error_message = "Each organization storage policy must be a td-<environment>-storage-<organization UUID> IAM policy ARN."
  }
}
