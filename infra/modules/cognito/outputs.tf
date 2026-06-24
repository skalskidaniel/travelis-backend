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

output "hosted_ui_domain" {
  value       = "${aws_cognito_user_pool_domain.domain.domain}.auth.${data.aws_region.current.name}.amazoncognito.com"
  description = "Cognito hosted UI domain hostname (no scheme) for Amplify OAuth."
}
