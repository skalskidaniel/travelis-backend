terraform {
  required_version = ">= 1.5"

  # Uncomment the following block to configure remote state storage on AWS S3 
  # once you have created the S3 bucket and DynamoDB lock table.
  #
  # backend "s3" {
  #   bucket         = "travelis-prod-terraform-state"
  #   key            = "state/terraform.tfstate"
  #   region         = "eu-central-1"
  #   dynamodb_table = "travelis-prod-terraform-locks"
  #   encrypt        = true
  # }

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
