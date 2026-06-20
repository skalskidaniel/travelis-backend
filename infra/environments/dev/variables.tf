variable "project" {
  description = "Project name used in resource naming and tags."
  type        = string
  default     = "travelis"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"
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

