variable "project" {
  description = "Project name used for resource naming."
  type        = string
}

variable "environment" {
  description = "Deployment environment."
  type        = string
}

variable "frontend_url" {
  description = "URL of the frontend PWA application."
  type        = string
}

variable "lambda_arn" {
  description = "ARN of the Lambdalith function."
  type        = string
}

variable "lambda_name" {
  description = "Name of the Lambdalith function."
  type        = string
}

variable "custom_domain" {
  description = "Custom API Gateway domain name (e.g., api.wakacje-travelis.pl). Leave empty to skip."
  type        = string
  default     = ""
}
