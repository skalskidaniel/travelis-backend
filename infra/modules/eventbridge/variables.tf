variable "project" {
  description = "Project name used for resource naming."
  type        = string
}

variable "environment" {
  description = "Deployment environment."
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

variable "scheduler_invoke_lambda_arns" {
  description = "Lambda ARNs the EventBridge Scheduler execution role may invoke (cron Lambda for debounced match jobs)."
  type        = list(string)
}
