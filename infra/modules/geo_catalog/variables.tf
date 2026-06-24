variable "project" {
  description = "Project name used in resource naming and tags."
  type        = string
}

variable "environment" {
  description = "Deployment environment (e.g. dev, prod)."
  type        = string
}

variable "enable_versioning" {
  description = "Enable S3 versioning for catalog rollback."
  type        = bool
  default     = true
}
