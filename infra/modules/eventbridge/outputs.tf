output "scheduler_role_arn" {
  value       = aws_iam_role.scheduler_role.arn
  description = "The ARN of the IAM role for EventBridge Scheduler."
}

output "scrape_offers_rule_arn" {
  value       = aws_cloudwatch_event_rule.scrape_offers.arn
  description = "The ARN of the EventBridge scrape offers rule."
}

output "check_availability_rule_arn" {
  value       = aws_cloudwatch_event_rule.check_availability.arn
}

output "sweep_inactive_users_rule_arn" {
  value       = aws_cloudwatch_event_rule.sweep_inactive_users.arn
}
