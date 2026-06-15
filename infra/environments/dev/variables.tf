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
