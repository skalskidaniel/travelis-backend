variable "project" {
  description = "Project name used in resource naming and tags."
  type        = string
}

variable "environment" {
  description = "Deployment environment."
  type        = string
}

variable "redis_url" {
  description = "Redis Cloud connection URL."
  type        = string
  sensitive   = true
}

variable "frontend_url" {
  description = "URL of the frontend PWA application."
  type        = string
}

variable "vapid_public_key" {
  description = "Web Push VAPID public key."
  type        = string
}

variable "vapid_private_key" {
  description = "Web Push VAPID private key."
  type        = string
  sensitive   = true
}

variable "grafana_cloud_aws_account_id" {
  description = "The Grafana Labs AWS Account ID (provided in Grafana Cloud setup)"
  type        = string
  default     = ""
}

variable "grafana_cloud_external_id" {
  description = "The External ID provided by Grafana Cloud for security cross-account trust"
  type        = string
  default     = ""
}

variable "attractiveness_z_threshold" {
  description = "Z-score threshold for Stage 1 attractiveness filtering."
  type        = number
  default     = -1.2
}
