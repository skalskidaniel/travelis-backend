output "api_endpoint" {
  value       = aws_apigatewayv2_api.api.api_endpoint
  description = "The HTTP API Gateway endpoint URL."
}

output "api_id" {
  value       = aws_apigatewayv2_api.api.id
  description = "The HTTP API Gateway API ID."
}

output "custom_domain_target" {
  value       = var.custom_domain != "" ? aws_apigatewayv2_domain_name.api[0].domain_name_configuration[0].target_domain_name : ""
  description = "The target domain name to point DNS CNAME/Alias to."
}

output "custom_domain_hosted_zone_id" {
  value       = var.custom_domain != "" ? aws_apigatewayv2_domain_name.api[0].domain_name_configuration[0].hosted_zone_id : ""
  description = "The hosted zone ID of the custom domain target."
}
