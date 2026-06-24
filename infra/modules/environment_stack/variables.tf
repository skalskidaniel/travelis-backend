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

variable "google_client_id" {
  description = "Google OAuth client ID for Cognito social sign-in. Leave empty to skip Google IdP."
  type        = string
  default     = ""
  sensitive   = true
}

variable "google_client_secret" {
  description = "Google OAuth client secret for Cognito social sign-in. Leave empty to skip Google IdP."
  type        = string
  default     = ""
  sensitive   = true
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

variable "aws_profile" {
  description = "AWS shared config profile to pass to local-exec scripts."
  type        = string
  default     = ""
}

variable "custom_domain" {
  description = "Custom API Gateway domain name (e.g., api.wakacje-travelis.pl). Leave empty to skip."
  type        = string
  default     = ""
}
