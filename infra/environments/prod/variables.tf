variable "project" {
  description = "Project name used in resource naming and tags."
  type        = string
  default     = "travelis"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-central-1"
}

variable "aws_profile" {
  description = "AWS shared config profile. Use travelis-terraform when authenticating via aws login."
  type        = string
  default     = "travelis-terraform"
}

variable "redis_url" {
  description = "Redis Cloud connection URL."
  type        = string
  sensitive   = true
}

variable "frontend_url" {
  description = "URL of the frontend PWA application."
  type        = string
  default     = "https://wakacje-travelis.pl"
}

variable "vapid_public_key" {
  description = "Web Push VAPID public key."
  type        = string
  default     = ""
}

variable "vapid_private_key" {
  description = "Web Push VAPID private key."
  type        = string
  default     = ""
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
