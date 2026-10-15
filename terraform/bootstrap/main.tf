data "aws_caller_identity" "current" {}

locals {
  state_prefix   = "therapist-dashboard"
  data_state_key = "${local.state_prefix}/demo-data.tfstate"
  app_state_key  = "${local.state_prefix}/demo-app.tfstate"

  github_oidc_host = "token.actions.githubusercontent.com"
  github_oidc_url  = "https://${local.github_oidc_host}"

  app_role_name  = "therapist-dashboard-demo-app-github"
  data_role_name = "therapist-dashboard-demo-data-github"
}

resource "aws_s3_bucket" "terraform_state" {
  bucket = var.state_bucket_name

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "terraform_state" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    actions = [
      "s3:*",
    ]
    resources = [
      aws_s3_bucket.terraform_state.arn,
      "${aws_s3_bucket.terraform_state.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  policy = data.aws_iam_policy_document.terraform_state.json
}

resource "aws_iam_openid_connect_provider" "github" {
  url = local.github_oidc_url

  client_id_list = [
    "sts.amazonaws.com",
  ]
}

data "aws_iam_policy_document" "github_app_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_host}:sub"
      values   = ["repo:${var.github_repository}:environment:demo-app"]
    }
  }
}

data "aws_iam_policy_document" "github_data_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_host}:sub"
      values = [
        "repo:${var.github_repository}:environment:demo-data",
        "repo:${var.github_repository}:environment:demo-data-destroy",
      ]
    }
  }
}

resource "aws_iam_role" "github_app" {
  name                 = local.app_role_name
  assume_role_policy   = data.aws_iam_policy_document.github_app_assume_role.json
  max_session_duration = 3600
}

resource "aws_iam_role" "github_data" {
  name                 = local.data_role_name
  assume_role_policy   = data.aws_iam_policy_document.github_data_assume_role.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "app_backend" {
  statement {
    sid       = "ListAppAndDataState"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.terraform_state.arn]

    condition {
      test     = "StringEquals"
      variable = "s3:prefix"
      values   = [local.app_state_key, local.data_state_key]
    }
  }

  statement {
    sid       = "ReadWriteAppState"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.terraform_state.arn}/${local.app_state_key}"]
  }

  statement {
    sid       = "ReadDataStateOutputs"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.terraform_state.arn}/${local.data_state_key}"]
  }

  statement {
    sid       = "ManageAppStateLock"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.terraform_state.arn}/${local.app_state_key}.tflock"]
  }
}

data "aws_iam_policy_document" "data_backend" {
  statement {
    sid       = "ListDataState"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.terraform_state.arn]

    condition {
      test     = "StringEquals"
      variable = "s3:prefix"
      values   = [local.data_state_key]
    }
  }

  statement {
    sid       = "ReadWriteDataState"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.terraform_state.arn}/${local.data_state_key}"]
  }

  statement {
    sid       = "ManageDataStateLock"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.terraform_state.arn}/${local.data_state_key}.tflock"]
  }
}

resource "aws_iam_role_policy" "github_app_backend" {
  name   = "terraform-app-state"
  role   = aws_iam_role.github_app.id
  policy = data.aws_iam_policy_document.app_backend.json
}

resource "aws_iam_role_policy" "github_data_backend" {
  name   = "terraform-data-state"
  role   = aws_iam_role.github_data.id
  policy = data.aws_iam_policy_document.data_backend.json
}

# IAM Policy Autopilot was run against the saved hosted-app Terraform plan.
# The generated action set is narrowed here to the demo's EC2 resources and
# exact IAM names, while read-only discovery calls remain account scoped.
data "aws_iam_policy_document" "github_app_deployment" {
  statement {
    sid = "ReadEc2Inventory"
    actions = [
      "ec2:DescribeAddresses",
      "ec2:DescribeAvailabilityZones",
      "ec2:DescribeImages",
      "ec2:DescribeInstanceAttribute",
      "ec2:DescribeInstanceCreditSpecifications",
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceStatus",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DescribeSecurityGroupRules",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSubnets",
      "ec2:DescribeTags",
      "ec2:DescribeVolumes",
      "ec2:DescribeVpcAttribute",
      "ec2:DescribeVpcs",
    ]
    resources = ["*"]
  }

  statement {
    sid = "ManageHostedDemoEc2"
    actions = [
      "ec2:AllocateAddress",
      "ec2:AssociateAddress",
      "ec2:AttachNetworkInterface",
      "ec2:AuthorizeSecurityGroupEgress",
      "ec2:AuthorizeSecurityGroupIngress",
      "ec2:CreateSecurityGroup",
      "ec2:CreateTags",
      "ec2:CreateVolume",
      "ec2:DeleteSecurityGroup",
      "ec2:DeleteTags",
      "ec2:DeleteVolume",
      "ec2:DisassociateAddress",
      "ec2:ModifyInstanceAttribute",
      "ec2:ModifyInstanceCreditSpecification",
      "ec2:ModifyNetworkInterfaceAttribute",
      "ec2:ModifyVolume",
      "ec2:ReleaseAddress",
      "ec2:RevokeSecurityGroupEgress",
      "ec2:RevokeSecurityGroupIngress",
      "ec2:RunInstances",
      "ec2:StartInstances",
      "ec2:StopInstances",
      "ec2:TerminateInstances",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [var.aws_region]
    }
  }

  statement {
    sid = "ManageExactApplicationIdentity"
    actions = [
      "iam:AddRoleToInstanceProfile",
      "iam:AttachRolePolicy",
      "iam:CreateInstanceProfile",
      "iam:CreateRole",
      "iam:DeleteInstanceProfile",
      "iam:DeleteRole",
      "iam:DeleteRolePolicy",
      "iam:DetachRolePolicy",
      "iam:GetInstanceProfile",
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:ListRolePolicies",
      "iam:PutRolePolicy",
      "iam:RemoveRoleFromInstanceProfile",
      "iam:TagInstanceProfile",
      "iam:TagRole",
      "iam:UntagInstanceProfile",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/therapist-dashboard-demo-app-instance",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:instance-profile/therapist-dashboard-demo-app-instance",
    ]
  }

  statement {
    sid       = "PassExactApplicationRoleToEc2"
    actions   = ["iam:PassRole"]
    resources = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/therapist-dashboard-demo-app-instance"]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ec2.amazonaws.com"]
    }
  }

  statement {
    sid = "ReadAttachedManagedPolicies"
    actions = [
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:ListPolicyVersions",
    ]
    resources = [
      "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/therapist-dashboard-demo-healthscribe-caller",
    ]
  }

  statement {
    sid     = "RunHostedDemoDeploymentCommand"
    actions = ["ssm:SendCommand"]
    resources = [
      "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/*",
    ]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Project"
      values   = ["therapist-dashboard-demo-app"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Environment"
      values   = ["demo"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Stack"
      values   = ["hosted-application"]
    }
  }

  statement {
    sid     = "UseAwsRunShellScriptDocument"
    actions = ["ssm:SendCommand"]
    resources = [
      "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript",
    ]
  }

  # GetCommandInvocation does not support resource-level permissions. The
  # workflow uses it only to wait for and report the command ID it just sent.
  statement {
    sid       = "ReadDeploymentCommandResult"
    actions   = ["ssm:GetCommandInvocation"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_app_deployment" {
  name   = "terraform-app-deployment"
  role   = aws_iam_role.github_app.id
  policy = data.aws_iam_policy_document.github_app_deployment.json
}

# The data root owns the synthetic-demo VPC, RDS, artifact buckets, KMS keys,
# and HealthScribe IAM resources. The role is still isolated to this repository
# and the two protected data environments in its trust policy.
data "aws_iam_policy_document" "github_data_deployment" {
  statement {
    sid = "ManageDemoDataServices"
    actions = [
      "ec2:AssociateRouteTable",
      "ec2:AttachInternetGateway",
      "ec2:AuthorizeSecurityGroupEgress",
      "ec2:AuthorizeSecurityGroupIngress",
      "ec2:CreateInternetGateway",
      "ec2:CreateRoute",
      "ec2:CreateRouteTable",
      "ec2:CreateSecurityGroup",
      "ec2:CreateSubnet",
      "ec2:CreateTags",
      "ec2:CreateVpc",
      "ec2:DeleteInternetGateway",
      "ec2:DeleteRoute",
      "ec2:DeleteRouteTable",
      "ec2:DeleteSecurityGroup",
      "ec2:DeleteSubnet",
      "ec2:DeleteTags",
      "ec2:DeleteVpc",
      "ec2:Describe*",
      "ec2:DetachInternetGateway",
      "ec2:DisassociateRouteTable",
      "ec2:ModifySubnetAttribute",
      "ec2:ModifyVpcAttribute",
      "ec2:RevokeSecurityGroupEgress",
      "ec2:RevokeSecurityGroupIngress",
      "kms:CancelKeyDeletion",
      "kms:CreateAlias",
      "kms:CreateKey",
      "kms:DescribeKey",
      "kms:DisableKey",
      "kms:EnableKey",
      "kms:EnableKeyRotation",
      "kms:GetKeyPolicy",
      "kms:GetKeyRotationStatus",
      "kms:ListAliases",
      "kms:ListResourceTags",
      "kms:PutKeyPolicy",
      "kms:ScheduleKeyDeletion",
      "kms:TagResource",
      "kms:UntagResource",
      "kms:UpdateAlias",
      "kms:UpdateKeyDescription",
      "rds:AddTagsToResource",
      "rds:CreateDBInstance",
      "rds:CreateDBParameterGroup",
      "rds:CreateDBSubnetGroup",
      "rds:DeleteDBInstance",
      "rds:DeleteDBParameterGroup",
      "rds:DeleteDBSubnetGroup",
      "rds:Describe*",
      "rds:ListTagsForResource",
      "rds:ModifyDBInstance",
      "rds:ModifyDBParameterGroup",
      "rds:ModifyDBSubnetGroup",
      "rds:RemoveTagsFromResource",
      "rds:ResetDBParameterGroup",
      "s3:CreateBucket",
      "s3:DeleteBucket",
      "s3:DeleteBucketPolicy",
      "s3:DeleteObject",
      "s3:Get*",
      "s3:List*",
      "s3:PutBucketLifecycleConfiguration",
      "s3:PutBucketOwnershipControls",
      "s3:PutBucketPolicy",
      "s3:PutBucketPublicAccessBlock",
      "s3:PutBucketTagging",
      "s3:PutEncryptionConfiguration",
      "s3:PutLifecycleConfiguration",
    ]
    resources = ["*"]
  }

  statement {
    sid = "ManageHostedRuntimeSecretMetadata"
    actions = [
      "secretsmanager:CreateSecret",
      "secretsmanager:DeleteSecret",
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetResourcePolicy",
      "secretsmanager:PutResourcePolicy",
      "secretsmanager:RemoveRegionsFromReplication",
      "secretsmanager:ReplicateSecretToRegions",
      "secretsmanager:RestoreSecret",
      "secretsmanager:TagResource",
      "secretsmanager:UntagResource",
      "secretsmanager:UpdateSecret",
    ]
    resources = [
      "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:therapist-dashboard-demo/hosted-app-runtime-*",
    ]
  }

  statement {
    sid = "ManageDemoHealthScribeIam"
    actions = [
      "iam:CreatePolicy",
      "iam:CreatePolicyVersion",
      "iam:CreateRole",
      "iam:DeletePolicy",
      "iam:DeletePolicyVersion",
      "iam:DeleteRole",
      "iam:DeleteRolePolicy",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListPolicyVersions",
      "iam:ListRolePolicies",
      "iam:PutRolePolicy",
      "iam:SetDefaultPolicyVersion",
      "iam:TagPolicy",
      "iam:TagRole",
      "iam:UntagPolicy",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/therapist-dashboard-demo-healthscribe-batch",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/therapist-dashboard-demo-healthscribe-caller",
    ]
  }
}

resource "aws_iam_role_policy" "github_data_deployment" {
  name   = "terraform-data-deployment"
  role   = aws_iam_role.github_data.id
  policy = data.aws_iam_policy_document.github_data_deployment.json
}
