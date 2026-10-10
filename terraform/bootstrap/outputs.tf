output "state_bucket_name" {
  description = "Private versioned S3 bucket used by all demo Terraform roots."
  value       = aws_s3_bucket.terraform_state.id
}

output "github_app_role_arn" {
  description = "Set as the AWS_TERRAFORM_APP_ROLE_ARN GitHub repository variable."
  value       = aws_iam_role.github_app.arn
}

output "github_data_role_arn" {
  description = "Set as the AWS_TERRAFORM_DATA_ROLE_ARN GitHub repository variable."
  value       = aws_iam_role.github_data.arn
}

output "github_oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.github.arn
}
