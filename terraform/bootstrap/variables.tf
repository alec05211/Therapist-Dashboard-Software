variable "aws_region" {
  description = "AWS Region containing the Terraform state bucket and demo resources."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "Local AWS CLI profile used only while bootstrapping. GitHub Actions uses OIDC."
  type        = string
  default     = "terraform"
}

variable "github_repository" {
  description = "GitHub repository allowed to assume the deployment roles."
  type        = string
  default     = "alec05211/Therapist-Dashboard-Software"
}

variable "github_owner_id" {
  description = "Immutable GitHub owner ID included in the repository's customized OIDC subject."
  type        = string
  default     = "143427173"

  validation {
    condition     = can(regex("^[0-9]+$", var.github_owner_id))
    error_message = "github_owner_id must contain only digits."
  }
}

variable "github_repository_id" {
  description = "Immutable GitHub repository ID included in the repository's customized OIDC subject."
  type        = string
  default     = "1345148625"

  validation {
    condition     = can(regex("^[0-9]+$", var.github_repository_id))
    error_message = "github_repository_id must contain only digits."
  }
}

variable "state_bucket_name" {
  description = "Globally unique private S3 bucket for Terraform state."
  type        = string
  default     = "therapist-dashboard-terraform-state-408009925213-us-east-1"
}
