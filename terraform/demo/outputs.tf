output "database_endpoint" {
  description = "Public RDS DNS name. It accepts TLS PostgreSQL only from demo_allowed_cidr."
  value       = aws_db_instance.database.address
}

output "database_name" {
  value = aws_db_instance.database.db_name
}

output "database_master_user_secret_arn" {
  description = "RDS-managed credential secret; retrieve it locally when constructing DATABASE_URL."
  value       = aws_db_instance.database.master_user_secret[0].secret_arn
  sensitive   = true
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
