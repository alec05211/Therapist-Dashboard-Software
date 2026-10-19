data "aws_ami" "amazon_linux_2023_arm64" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-arm64"]
  }

  filter {
    name   = "architecture"
    values = ["arm64"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "application" {
  name               = "${var.project_name}-instance"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

resource "aws_iam_instance_profile" "application" {
  name = "${var.project_name}-instance"
  role = aws_iam_role.application.name
}

resource "aws_iam_role_policy_attachment" "systems_manager" {
  role       = aws_iam_role.application.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "healthscribe" {
  role       = aws_iam_role.application.name
  policy_arn = var.healthscribe_caller_policy_arn
}

# The per-organization policies remain owned by the persistent organization
# storage stack. This replaceable compute stack owns their attachment so a
# destroy/recreate cycle cannot leave the new EC2 role unable to read sessions.
resource "aws_iam_role_policy_attachment" "organization_storage" {
  for_each = var.organization_storage_policy_arns

  role       = aws_iam_role.application.name
  policy_arn = each.value
}

# IAM Policy Autopilot identified these two additional runtime operations from
# database/connection.py. Resource scope is narrowed to this one RDS-managed
# secret and its customer-managed KMS key.
data "aws_iam_policy_document" "database_credentials" {
  statement {
    sid    = "ReadDemoDatabaseCredential"
    effect = "Allow"
    actions = [
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetSecretValue",
    ]
    resources = [var.database_secret_arn]
  }

  statement {
    sid       = "DecryptDemoDatabaseCredential"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.database_kms_key_arn]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["secretsmanager.${var.aws_region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "database_credentials" {
  name   = "database-credentials"
  role   = aws_iam_role.application.id
  policy = data.aws_iam_policy_document.database_credentials.json
}

data "aws_iam_policy_document" "hosted_app_runtime" {
  statement {
    sid    = "ReadHostedApplicationRuntime"
    effect = "Allow"
    actions = [
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetSecretValue",
    ]
    resources = [var.hosted_app_runtime_secret_arn]
  }
}

resource "aws_iam_role_policy" "hosted_app_runtime" {
  name   = "hosted-app-runtime"
  role   = aws_iam_role.application.id
  policy = data.aws_iam_policy_document.hosted_app_runtime.json
}

data "aws_iam_policy_document" "clinical_synthesis_runtime" {
  statement {
    sid    = "ReadClinicalSynthesisCredential"
    effect = "Allow"
    actions = [
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetSecretValue",
    ]
    resources = [var.clinical_synthesis_secret_arn]
  }
}

resource "aws_iam_role_policy" "clinical_synthesis_runtime" {
  name   = "clinical-synthesis-runtime"
  role   = aws_iam_role.application.id
  policy = data.aws_iam_policy_document.clinical_synthesis_runtime.json
}

resource "aws_security_group" "web" {
  name        = "${var.project_name}-web"
  description = "Public HTTPS entry point for the synthetic hosted demo."
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP for certificate validation and HTTPS redirect"
    protocol    = "tcp"
    from_port   = 80
    to_port     = 80
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS synthetic demo"
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Application dependencies, AWS APIs, package registries, and RDS"
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "application" {
  ami           = data.aws_ami.amazon_linux_2023_arm64.id
  instance_type = var.instance_type
  subnet_id     = var.public_subnet_ids[0]
  vpc_security_group_ids = [
    aws_security_group.web.id,
    var.database_client_security_group_id,
  ]
  iam_instance_profile        = aws_iam_instance_profile.application.name
  associate_public_ip_address = true
  monitoring                  = true

  user_data = templatefile("${path.module}/user-data.sh.tftpl", {
    aws_region                              = var.aws_region
    database_endpoint                       = var.database_endpoint
    database_name                           = var.database_name
    database_secret_arn                     = var.database_secret_arn
    domain_name                             = var.domain_name
    hosted_app_runtime_secret_arn           = var.hosted_app_runtime_secret_arn
    clinical_synthesis_secret_arn           = var.clinical_synthesis_secret_arn
    healthscribe_batch_data_access_role_arn = var.healthscribe_batch_data_access_role_arn
    healthscribe_input_bucket               = var.healthscribe_input_bucket
    healthscribe_output_bucket              = var.healthscribe_output_bucket
  })

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    encrypted             = true
    volume_type           = "gp3"
    volume_size           = var.root_volume_size_gib
    delete_on_termination = true
  }

  lifecycle {
    precondition {
      condition     = startswith(data.aws_ami.amazon_linux_2023_arm64.architecture, "arm64")
      error_message = "The selected AMI must be ARM64 for the initial t4g host."
    }
  }

  tags = {
    Name               = var.project_name
    DataClassification = "synthetic-demo-only"
  }
}

resource "aws_eip" "application" {
  domain   = "vpc"
  instance = aws_instance.application.id

  tags = {
    Name = "${var.project_name}-public"
  }
}
