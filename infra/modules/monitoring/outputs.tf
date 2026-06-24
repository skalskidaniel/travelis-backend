output "grafana_cloud_role_arn" {
  description = "The ARN of the IAM Role created for Grafana Cloud read access."
  value       = var.grafana_cloud_aws_account_id != "" ? aws_iam_role.grafana_cloud_read[0].arn : ""
}
