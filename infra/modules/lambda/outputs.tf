output "lambda_arn" {
  value       = aws_lambda_function.lambdalith.arn
  description = "The ARN of the Lambdalith function."
}

output "lambda_name" {
  value       = aws_lambda_function.lambdalith.function_name
  description = "The name of the Lambdalith function."
}

output "lambda_role_arn" {
  value       = aws_iam_role.lambda_role.arn
  description = "The ARN of the Lambda execution role."
}
