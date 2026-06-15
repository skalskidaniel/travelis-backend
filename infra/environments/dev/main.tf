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

module "geo_catalog" {
  source = "../../modules/geo_catalog"

  project     = var.project
  environment = var.environment
}
