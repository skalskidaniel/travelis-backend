output "geo_catalog_bucket_name" {
  description = "S3 bucket for provider geo catalogs."
  value       = module.geo_catalog.bucket_name
}

output "geo_catalog_bucket_arn" {
  description = "ARN of the geo catalog bucket."
  value       = module.geo_catalog.bucket_arn
}

output "geo_catalog_object_keys" {
  description = "S3 object keys for provider geo catalogs."
  value       = module.geo_catalog.object_keys
}

output "api_endpoint" {
  description = "The HTTP API Gateway endpoint URL."
  value       = module.api_gateway.api_endpoint
}

output "cognito_user_pool_id" {
  description = "The Cognito User Pool ID."
  value       = module.cognito.user_pool_id
}

output "cognito_app_client_id" {
  description = "The Cognito App Client ID."
  value       = module.cognito.app_client_id
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

