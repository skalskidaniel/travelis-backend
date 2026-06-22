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
