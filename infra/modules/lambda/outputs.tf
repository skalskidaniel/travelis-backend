output "api_lambda_arn" {
  value       = aws_lambda_function.api_lambda.arn
  description = "The ARN of the API Lambda function."
}

output "api_lambda_name" {
  value       = aws_lambda_function.api_lambda.function_name
  description = "The name of the API Lambda function."
}

output "cron_lambda_arn" {
  value       = aws_lambda_function.cron_lambda.arn
  description = "The ARN of the Cron Lambda function."
}

output "cron_lambda_name" {
  value       = aws_lambda_function.cron_lambda.function_name
  description = "The name of the Cron Lambda function."
}

output "lambda_role_arn" {
  value       = aws_iam_role.lambda_role.arn
  description = "The ARN of the Lambda execution role."
}
