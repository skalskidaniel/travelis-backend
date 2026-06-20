output "scheduler_role_arn" {
  value       = aws_iam_role.scheduler_role.arn
  description = "The ARN of the IAM role for EventBridge Scheduler."
}
