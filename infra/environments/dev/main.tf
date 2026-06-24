provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

module "environment_stack" {
  source = "../../modules/environment_stack"

  project                      = var.project
  environment                  = var.environment
  redis_url                    = var.redis_url
  frontend_url                 = var.frontend_url
  vapid_public_key             = var.vapid_public_key
  vapid_private_key            = var.vapid_private_key
  grafana_cloud_aws_account_id = var.grafana_cloud_aws_account_id
  grafana_cloud_external_id    = var.grafana_cloud_external_id
  aws_profile                  = var.aws_profile
}
