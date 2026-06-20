variable "project" {
  description = "Project name used for resource naming."
  type        = string
}

variable "environment" {
  description = "Deployment environment."
  type        = string
}

variable "redis_url" {
  description = "Connection string for Redis cache."
  type        = string
}

variable "frontend_url" {
  description = "URL of the frontend PWA application."
  type        = string
}

variable "users_table_name" {
  type = string
}

variable "users_table_arn" {
  type = string
}

variable "cells_table_name" {
  type = string
}

variable "cells_table_arn" {
  type = string
}

variable "offers_table_name" {
  type = string
}

variable "offers_table_arn" {
  type = string
}

variable "user_offers_table_name" {
  type = string
}

variable "user_offers_table_arn" {
  type = string
}

variable "geo_catalog_bucket_name" {
  type = string
}

variable "geo_catalog_bucket_arn" {
  type = string
}

variable "cognito_user_pool_id" {
  type = string
}

variable "cognito_user_pool_arn" {
  type = string
}

variable "vapid_public_key" {
  type    = string
  default = ""
}

variable "vapid_private_key" {
  type    = string
  default = ""
}

variable "scheduler_role_arn" {
  description = "ARN of the role EventBridge Scheduler uses to invoke Lambda (required for PassRole)."
  type        = string
}
