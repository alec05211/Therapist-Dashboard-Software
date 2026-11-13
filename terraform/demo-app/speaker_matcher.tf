variable "speaker_matcher_image_digest" {
  description = "Published linux/amd64 speaker matcher ECR image digest. Null disables the worker."
  type        = string
  default     = null
  validation {
    condition     = var.speaker_matcher_image_digest == null ? true : can(regex("^sha256:[0-9a-f]{64}$", var.speaker_matcher_image_digest))
    error_message = "Use the SHA-256 digest of the published worker image."
  }
}

variable "speaker_match_threshold" {
  description = "Calibrated minimum cosine similarity for automatic assignments."
  type        = number
  default     = 0.80
}

variable "speaker_match_margin" {
  description = "Minimum cosine similarity separation between eligible voices."
  type        = number
  default     = 0.12
}

resource "aws_ecr_repository" "speaker_matcher" {
  name                 = "${var.project_name}-speaker-matcher"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
}

output "speaker_matcher_repository" {
  value = aws_ecr_repository.speaker_matcher.repository_url
}

resource "aws_iam_role" "speaker_matcher" {
  count = var.speaker_matcher_image_digest == null ? 0 : 1
  name  = "${var.project_name}-speaker-matcher"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_cloudwatch_log_group" "speaker_matcher" {
  count             = var.speaker_matcher_image_digest == null ? 0 : 1
  name              = "/aws/lambda/${var.project_name}-speaker-matcher"
  retention_in_days = 14
}

resource "aws_iam_role_policy" "speaker_matcher_logs" {
  count = var.speaker_matcher_image_digest == null ? 0 : 1
  role  = aws_iam_role.speaker_matcher[0].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "${aws_cloudwatch_log_group.speaker_matcher[0].arn}:*"
    }]
  })
}

resource "aws_lambda_function" "speaker_matcher" {
  count         = var.speaker_matcher_image_digest == null ? 0 : 1
  function_name = "${var.project_name}-speaker-matcher"
  role          = aws_iam_role.speaker_matcher[0].arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.speaker_matcher.repository_url}@${var.speaker_matcher_image_digest}"
  architectures = ["x86_64"]
  memory_size   = 2048
  timeout       = 180
  ephemeral_storage {
    size = 1024
  }
  environment {
    variables = {
      VOICE_MATCH_THRESHOLD = tostring(var.speaker_match_threshold)
      VOICE_MATCH_MARGIN    = tostring(var.speaker_match_margin)
    }
  }
  depends_on = [aws_iam_role_policy.speaker_matcher_logs]
}

resource "aws_iam_role_policy" "invoke_speaker_matcher" {
  count = var.speaker_matcher_image_digest == null ? 0 : 1
  role  = aws_iam_role.application.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.speaker_matcher[0].arn
    }]
  })
}
