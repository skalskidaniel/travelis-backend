# 1. Scrape Offers Cron Rule (3x daily: 06:00, 14:00, 22:00 UTC)
resource "aws_cloudwatch_event_rule" "scrape_offers" {
  name                = "${var.project}-${var.environment}-scrape-offers-rule"
  description         = "Triggers scrape_offers job 3x daily"
  schedule_expression = "cron(0 6,14,22 * * ? *)"
}

resource "aws_cloudwatch_event_target" "scrape_offers_target" {
  rule      = aws_cloudwatch_event_rule.scrape_offers.name
  target_id = "ScrapeOffersTarget"
  arn       = var.lambda_arn
  input     = jsonencode({ "type" : "scrape_offers" })
}

# 2. Availability Check Cron Rule (1x daily: 04:00 UTC)
resource "aws_cloudwatch_event_rule" "check_availability" {
  name                = "${var.project}-${var.environment}-check-availability-rule"
  description         = "Triggers check_availability job 1x daily"
  schedule_expression = "cron(0 4 * * ? *)"
}

resource "aws_cloudwatch_event_target" "check_availability_target" {
  rule      = aws_cloudwatch_event_rule.check_availability.name
  target_id = "CheckAvailabilityTarget"
  arn       = var.lambda_arn
  input     = jsonencode({ "type" : "check_availability" })
}


# 3. EventBridge Scheduler IAM Role
# This is the role assumed by the one-time matching schedules created dynamically by the application.
resource "aws_iam_role" "scheduler_role" {
  name = "${var.project}-${var.environment}-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "scheduler_lambda_invoke" {
  name        = "${var.project}-${var.environment}-scheduler-lambda-invoke-policy"
  description = "Allows EventBridge Scheduler to invoke the Lambdalith function."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          var.lambda_arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "scheduler_policy_attachment" {
  role       = aws_iam_role.scheduler_role.name
  policy_arn = aws_iam_policy.scheduler_lambda_invoke.arn
}
