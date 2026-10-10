output "public_ip" {
  description = "Point the temporary DuckDNS hostname at this Elastic IP."
  value       = aws_eip.application.public_ip
}

output "application_url" {
  description = "HTTPS URL for the synthetic hosted demo."
  value       = "https://${var.domain_name}"
}

output "instance_id" {
  description = "EC2 instance ID used with AWS Systems Manager Session Manager."
  value       = aws_instance.application.id
}

output "instance_role_arn" {
  description = "IAM role assumed by the hosted demo application."
  value       = aws_iam_role.application.arn
}

output "caddy_health_url" {
  description = "Caddy-only health endpoint; application routes may remain unavailable until runtime deployment."
  value       = "https://${var.domain_name}/infra-healthz"
}
