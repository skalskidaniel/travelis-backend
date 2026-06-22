resource "aws_iam_role" "grafana_cloud_read" {
  name = "${var.project}-${var.environment}-grafana-cloud-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.grafana_cloud_aws_account_id}:root"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "sts:ExternalId" = var.grafana_cloud_external_id
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "grafana_cloud_logs_policy" {
  name        = "${var.project}-${var.environment}-grafana-logs-policy"
  description = "Allows Grafana Cloud to pull CloudWatch Logs and Metrics for ${var.project}-${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # 1. Allow listing/describing log groups (required by Grafana logs indexer, must be *)
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      },
      # 2. Allow reading actual log streams/events (restricted to this project's lambdas)
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogStreams",
          "logs:FilterLogEvents",
          "logs:GetLogEvents",
          "logs:DescribeMetricFilters",
          "logs:DescribeSubscriptionFilters"
        ]
        Resource = [
          "arn:aws:logs:*:*:log-group:/aws/lambda/${var.project}-${var.environment}-*:*",
          "arn:aws:logs:*:*:log-group:/aws/lambda/${var.project}-${var.environment}-*"
        ]
      },
      # 3. Allow querying basic CloudWatch metrics to pass Grafana's connection tests
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:DescribeAlarmsForMetric",
          "cloudwatch:DescribeAlarmHistory",
          "cloudwatch:DescribeAlarms",
          "cloudwatch:ListMetrics",
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics"
        ]
        Resource = "*"
      }
    ]
  })
}


resource "aws_iam_role_policy_attachment" "grafana_cloud_logs" {
  role       = aws_iam_role.grafana_cloud_read.name
  policy_arn = aws_iam_policy.grafana_cloud_logs_policy.arn
}
