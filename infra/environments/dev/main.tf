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

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  lambda_name = "${var.project}-${var.environment}-lambdalith"
  lambda_arn  = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.lambda_name}"
}

module "geo_catalog" {
  source = "../../modules/geo_catalog"

  project     = var.project
  environment = var.environment
}

module "dynamodb" {
  source = "../../modules/dynamodb"

  project     = var.project
  environment = var.environment
}

module "cognito" {
  source = "../../modules/cognito"

  project     = var.project
  environment = var.environment
}

module "eventbridge" {
  source = "../../modules/eventbridge"

  project     = var.project
  environment = var.environment
  lambda_arn  = local.lambda_arn
  lambda_name = local.lambda_name
}

module "lambda" {
  source = "../../modules/lambda"

  project                 = var.project
  environment             = var.environment
  redis_url               = var.redis_url
  frontend_url            = var.frontend_url
  users_table_name        = module.dynamodb.users_table_name
  users_table_arn         = module.dynamodb.users_table_arn
  cells_table_name        = module.dynamodb.cells_table_name
  cells_table_arn         = module.dynamodb.cells_table_arn
  offers_table_name       = module.dynamodb.offers_table_name
  offers_table_arn        = module.dynamodb.offers_table_arn
  user_offers_table_name  = module.dynamodb.user_offers_table_name
  user_offers_table_arn   = module.dynamodb.user_offers_table_arn
  geo_catalog_bucket_name = module.geo_catalog.bucket_name
  geo_catalog_bucket_arn  = module.geo_catalog.bucket_arn
  cognito_user_pool_id    = module.cognito.user_pool_id
  cognito_user_pool_arn   = module.cognito.user_pool_arn
  vapid_public_key        = var.vapid_public_key
  vapid_private_key       = var.vapid_private_key
  scheduler_role_arn      = module.eventbridge.scheduler_role_arn
}

module "api_gateway" {
  source = "../../modules/api_gateway"

  project     = var.project
  environment = var.environment
  lambda_arn  = module.lambda.lambda_arn
  lambda_name = module.lambda.lambda_name
}
