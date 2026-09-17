variable "aws_region" {
  description = "AWS Region for the disposable demonstration environment."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Lowercase DNS-compatible prefix for demo resources."
  type        = string
  default     = "therapist-dashboard-demo"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,40}$", var.project_name))
    error_message = "project_name must be 3-40 lowercase letters, numbers, or hyphens."
  }
}

variable "database_name" {
  description = "Initial PostgreSQL database name."
  type        = string
  default     = "therapist_dashboard"
}

variable "database_instance_class" {
  description = "Use a small single-AZ instance for mock-data demonstrations."
  type        = string
  default     = "db.t4g.micro"
}

variable "demo_allowed_cidr" {
  description = "Required public IPv4 CIDR allowed to connect to PostgreSQL, normally your current public IP with /32. Never use 0.0.0.0/0."
  type        = string

  validation {
    condition     = can(cidrhost(var.demo_allowed_cidr, 0)) && var.demo_allowed_cidr != "0.0.0.0/0"
    error_message = "demo_allowed_cidr must be a valid CIDR and must not be 0.0.0.0/0."
  }
}

variable "artifact_retention_days" {
  description = "Days to retain mock recording and HealthScribe artifacts in S3 before automatic expiration."
  type        = number
  default     = 30

  validation {
    condition     = var.artifact_retention_days >= 1 && var.artifact_retention_days <= 365
    error_message = "artifact_retention_days must be between 1 and 365."
  }
}

variable "take_final_snapshot" {
  description = "Set true only when preserving a final RDS snapshot before destroying this demo."
  type        = bool
  default     = false
}

variable "final_snapshot_identifier" {
  description = "Unique snapshot identifier required when take_final_snapshot is true."
  type        = string
  default     = ""
}

variable "force_destroy_artifact_buckets" {
  description = "Explicitly permit Terraform to delete all mock objects when destroying the demo stack."
  type        = bool
  default     = false
}
