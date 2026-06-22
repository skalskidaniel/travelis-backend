output "grafana_cloud_role_arn" {
  description = "The ARN of the IAM Role created for Grafana Cloud read access."
  value       = aws_iam_role.grafana_cloud_read.arn
}
