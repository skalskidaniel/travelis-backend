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

resource "aws_cloudwatch_metric_alarm" "api_lambda_errors" {
  alarm_name          = "${var.project}-${var.environment}-api-lambda-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "API Lambda reported one or more errors in a 5-minute window."
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.api_lambda_name
  }
}

resource "aws_cloudwatch_metric_alarm" "cron_lambda_errors" {
  alarm_name          = "${var.project}-${var.environment}-cron-lambda-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Cron Lambda reported one or more errors in a 5-minute window."
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.cron_lambda_name
  }
}

resource "aws_cloudwatch_metric_alarm" "api_lambda_duration_p99" {
  alarm_name          = "${var.project}-${var.environment}-api-lambda-duration-p99"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p99"
  threshold           = 25000
  alarm_description   = "API Lambda p99 duration exceeded 25s (30s timeout)."
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.api_lambda_name
  }
}

resource "aws_cloudwatch_metric_alarm" "api_gateway_5xx" {
  alarm_name          = "${var.project}-${var.environment}-api-gateway-5xx"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "5xx"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "API Gateway returned 5 or more 5xx responses in a 5-minute window."
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiId = var.api_gateway_id
  }
}
