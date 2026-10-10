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

variable "state_bucket_name" {
  description = "Globally unique private S3 bucket for Terraform state."
  type        = string
  default     = "therapist-dashboard-terraform-state-408009925213-us-east-1"
}
