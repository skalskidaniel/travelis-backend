output "api_endpoint" {
  value       = aws_apigatewayv2_api.api.api_endpoint
  description = "The HTTP API Gateway endpoint URL."
}

output "api_id" {
  value       = aws_apigatewayv2_api.api.id
  description = "The HTTP API Gateway API ID."
}
