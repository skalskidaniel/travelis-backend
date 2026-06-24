variable "project" {
  description = "Project name used in resource naming and tags."
  type        = string
}

variable "environment" {
  description = "Deployment environment."
  type        = string
}

variable "grafana_cloud_aws_account_id" {
  description = "The Grafana Labs AWS Account ID (provided in Grafana Cloud setup)"
  type        = string
}

variable "grafana_cloud_external_id" {
  description = "The External ID provided by Grafana Cloud for security cross-account trust"
  type        = string
}

variable "api_lambda_name" {
  description = "Name of the API Lambda function for CloudWatch alarms."
  type        = string
}

variable "cron_lambda_name" {
  description = "Name of the cron Lambda function for CloudWatch alarms."
  type        = string
}

variable "api_gateway_id" {
  description = "HTTP API Gateway ID for CloudWatch alarms."
  type        = string
}
