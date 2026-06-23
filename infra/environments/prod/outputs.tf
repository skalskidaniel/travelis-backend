output "geo_catalog_bucket_name" {
  description = "S3 bucket for provider geo catalogs."
  value       = module.environment_stack.geo_catalog_bucket_name
}

output "geo_catalog_bucket_arn" {
  description = "ARN of the geo catalog bucket."
  value       = module.environment_stack.geo_catalog_bucket_arn
}

output "geo_catalog_object_keys" {
  description = "S3 object keys for provider geo catalogs."
  value       = module.environment_stack.geo_catalog_object_keys
}

output "api_endpoint" {
  description = "The HTTP API Gateway endpoint URL."
  value       = module.environment_stack.api_endpoint
}

output "cognito_user_pool_id" {
  description = "The Cognito User Pool ID."
  value       = module.environment_stack.cognito_user_pool_id
}

output "cognito_app_client_id" {
  description = "The Cognito App Client ID."
  value       = module.environment_stack.cognito_app_client_id
}

output "dynamodb_users_table" {
  value = module.environment_stack.dynamodb_users_table
}

output "dynamodb_cells_table" {
  value = module.environment_stack.dynamodb_cells_table
}

output "dynamodb_offers_table" {
  value = module.environment_stack.dynamodb_offers_table
}

output "dynamodb_user_offers_table" {
  value = module.environment_stack.dynamodb_user_offers_table
}

output "grafana_cloud_role_arn" {
  description = "The ARN of the IAM Role created for Grafana Cloud read access."
  value       = module.environment_stack.grafana_cloud_role_arn
}

output "lambda_function_arn" {
  description = "The ARN of the Lambdalith function."
  value       = module.environment_stack.api_lambda_arn
}

output "cron_lambda_function_arn" {
  description = "The ARN of the Cron Lambdalith function."
  value       = module.environment_stack.cron_lambda_arn
}

output "scheduler_role_arn" {
  description = "The ARN of the IAM role for EventBridge Scheduler."
  value       = module.environment_stack.scheduler_role_arn
}
