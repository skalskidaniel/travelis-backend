output "user_pool_id" {
  value       = aws_cognito_user_pool.pool.id
  description = "The ID of the Cognito User Pool."
}

output "user_pool_arn" {
  value       = aws_cognito_user_pool.pool.arn
  description = "The ARN of the Cognito User Pool."
}

output "app_client_id" {
  value       = aws_cognito_user_pool_client.client.id
  description = "The ID of the Cognito User Pool Client."
}