output "database_endpoint" {
  description = "Public RDS DNS name. It accepts TLS PostgreSQL only from demo_allowed_cidr."
  value       = aws_db_instance.database.address
}

output "demo_vpc_id" {
  description = "VPC shared with the replaceable hosted demo application."
  value       = aws_vpc.demo.id
}

output "demo_public_subnet_ids" {
  description = "Public demo subnets in which the hosted EC2 instance may run."
  value       = aws_subnet.public[*].id
}

output "database_client_security_group_id" {
  description = "Attach this security group to hosted workloads that may connect to demo PostgreSQL."
  value       = aws_security_group.database_client.id
}

output "database_name" {
  value = aws_db_instance.database.db_name
}

output "database_master_user_secret_arn" {
  description = "RDS-managed credential secret; retrieve it locally when constructing DATABASE_URL."
  value       = aws_db_instance.database.master_user_secret[0].secret_arn
  sensitive   = true
}

output "database_kms_key_arn" {
  description = "KMS key used by the demo database and its RDS-managed credential secret."
  value       = aws_kms_key.database.arn
}

output "hosted_app_runtime_secret_arn" {
  description = "Secret metadata ARN for hosted Auth0 runtime configuration; the value is managed outside Terraform."
  value       = aws_secretsmanager_secret.hosted_app_runtime.arn
}

output "clinical_synthesis_secret_arn" {
  description = "Secret metadata ARN for the hosted clinical-synthesis API credential; the value is managed outside Terraform."
  value       = aws_secretsmanager_secret.clinical_synthesis.arn
}

output "healthscribe_input_bucket" {
  value = aws_s3_bucket.input.bucket
}

output "healthscribe_output_bucket" {
  value = aws_s3_bucket.output.bucket
}

output "healthscribe_batch_data_access_role_arn" {
  value = aws_iam_role.healthscribe_batch.arn
}

output "healthscribe_caller_policy_arn" {
  description = "Attach to the IAM principal used by the local FastAPI server when it lacks equivalent permissions."
  value       = aws_iam_policy.healthscribe_caller.arn
}
