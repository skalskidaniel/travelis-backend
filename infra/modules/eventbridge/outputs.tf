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
  description = "The ARN of the EventBridge check availability rule."
}
