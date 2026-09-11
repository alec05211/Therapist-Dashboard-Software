# Database migrations

`migrations/` contains ordered, immutable PostgreSQL migrations. `migrate.py`
applies each migration once and records its SHA-256 checksum in
`app.schema_migrations`.

The approved migration path is an explicitly invoked AWS Fargate task inside
the database VPC. It reads the RDS-managed administrator secret directly from
Secrets Manager, verifies the RDS TLS certificate, applies migrations, exits,
and writes only operational output to CloudWatch Logs. No laptop database
tunnel or public RDS access is used.

## Run the initial migration

1. Build and push the migration image. Docker is required only to package the
   image; it never receives the database password.

   ```powershell
   $env:AWS_PROFILE = "terraform"
   $env:AWS_REGION = "us-east-1"
   $repository = terraform output -raw database_migration_repository_url
   aws ecr get-login-password | docker login --username AWS --password-stdin $repository.Split('/')[0]
   docker build -f database/migration-container/Dockerfile -t therapist-dashboard-migration:initial .
   docker tag therapist-dashboard-migration:initial "${repository}:initial"
   docker push "${repository}:initial"
   ```

2. Create the short-lived private API endpoints and RDS rule needed by the
   task. Review the plan first.

   ```powershell
   terraform apply -var="enable_migration_task_network=true"
   ```

3. Start exactly one migration task:

   ```powershell
   $cluster = terraform output -raw database_migration_cluster_name
   $taskDefinition = terraform output -raw database_migration_task_definition_arn
   $subnet = terraform output -raw database_private_subnet_id
   $securityGroup = terraform output -raw database_migration_task_security_group_id
   $taskArn = aws ecs run-task --cluster $cluster --launch-type FARGATE --task-definition $taskDefinition --count 1 --network-configuration "awsvpcConfiguration={subnets=[$subnet],securityGroups=[$securityGroup],assignPublicIp=DISABLED}" --query "tasks[0].taskArn" --output text
   aws ecs wait tasks-stopped --cluster $cluster --tasks $taskArn
   aws ecs describe-tasks --cluster $cluster --tasks $taskArn --query "tasks[0].containers[0].{ExitCode:exitCode,Reason:reason}" --output table
   aws logs tail "/therapist-dashboard/database-migration" --since 10m
   ```

4. Wait for the task to stop with exit code `0`, then check the CloudWatch log
   stream for `Migrations complete.`. Do not retry after an unknown failure
   without checking the recorded migration state.

5. Remove the temporary endpoints and RDS ingress rule after validation:

   ```powershell
   terraform apply -var="enable_migration_task_network=false"
   ```

This does not destroy RDS, its schema, or the ECR image repository.

## Temporary network diagnostics

If the task fails before its container starts, enable short-retention VPC Flow
Logs only while diagnosing it:

```powershell
terraform apply -var="enable_migration_task_network=true" -var="enable_migration_network_diagnostics=true"
```

Run one task, wait two minutes for log delivery, then inspect the network
metadata:

```powershell
$flowLogGroup = terraform output -raw database_migration_flow_log_group_name
aws logs tail $flowLogGroup --since 10m
```

Disable diagnostics after the cause is resolved:

```powershell
terraform apply -var="enable_migration_task_network=true" -var="enable_migration_network_diagnostics=false"
```

## Local validation only

You may run `python database/migrate.py` against a local non-sensitive
PostgreSQL database. For the private RDS instance, use the Fargate task above.
