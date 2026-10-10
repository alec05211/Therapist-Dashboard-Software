terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project            = "therapist-dashboard"
      Environment        = "demo"
      ManagedBy          = "terraform"
      DataClassification = "synthetic-demo-only"
    }
  }
}
