# This file tells Terraform which "provider" (cloud platform) we're using,
# and which version of AWS's Terraform plugin to use.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# The region where all resources below will be created.
# Matches the AWS_REGION we've used throughout this project.
provider "aws" {
  region = "us-east-1"
}
