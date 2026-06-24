output "geo_catalog_bucket_name" {
  value = module.geo_catalog.bucket_name
}

output "geo_catalog_bucket_arn" {
  value = module.geo_catalog.bucket_arn
}

output "geo_catalog_object_keys" {
  value = module.geo_catalog.object_keys
}

output "api_endpoint" {
  value = module.api_gateway.api_endpoint
}

output "cognito_user_pool_id" {
  value = module.cognito.user_pool_id
}

output "cognito_app_client_id" {
  value = module.cognito.app_client_id
}

output "dynamodb_users_table" {
  value = module.dynamodb.users_table_name
}

output "dynamodb_cells_table" {
  value = module.dynamodb.cells_table_name
}

output "dynamodb_offers_table" {
  value = module.dynamodb.offers_table_name
}

output "dynamodb_user_offers_table" {
  value = module.dynamodb.user_offers_table_name
}

output "grafana_cloud_role_arn" {
  value = module.monitoring.grafana_cloud_role_arn
}

output "api_lambda_arn" {
  value = module.lambda.api_lambda_arn
}

output "cron_lambda_arn" {
  value = module.lambda.cron_lambda_arn
}

output "scheduler_role_arn" {
  value = module.eventbridge.scheduler_role_arn
}
