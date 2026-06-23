terraform {
  required_version = ">= 1.5"

  backend "s3" {
    bucket         = "travelis-prod-terraform-state"
    key            = "state/terraform.tfstate"
    region         = "eu-central-1"
    dynamodb_table = "travelis-prod-terraform-locks"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}
