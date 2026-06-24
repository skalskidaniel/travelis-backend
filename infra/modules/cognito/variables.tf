variable "project" {
  description = "Project name used for resource naming."
  type        = string
}

variable "environment" {
  description = "Deployment environment."
  type        = string
}

variable "frontend_url" {
  description = "Canonical frontend origin used for OAuth callback and logout URLs."
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
