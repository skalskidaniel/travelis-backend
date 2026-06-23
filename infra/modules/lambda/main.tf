terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

resource "null_resource" "lambda_build" {
  triggers = {
    pyproject_hash = filemd5("${path.module}/../../../pyproject.toml")
    uv_lock_hash   = filemd5("${path.module}/../../../uv.lock")
    build_script   = filemd5("${path.module}/../../../scripts/build_lambda_package.sh")
    src_hash       = sha256(join("", [for f in fileset("${path.module}/../../../src", "**") : filesha256("${path.module}/../../../src/${f}")]))
  }

  provisioner "local-exec" {
    command     = "bash ${abspath("${path.module}/../../../scripts/build_lambda_package.sh")}"
    working_dir = abspath("${path.module}/../../..")
  }
}

data "archive_file" "lambda_zip" {
  depends_on = [null_resource.lambda_build]

  type        = "zip"
  source_dir  = "${path.module}/../../../dist/lambda-build"
  output_path = "${path.module}/../../../dist/lambda_function.zip"
}

resource "aws_iam_role" "lambda_role" {
  name = "${var.project}-${var.environment}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "basic_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "lambda_custom_policy" {
  name        = "${var.project}-${var.environment}-lambda-custom-policy"
  description = "Custom permissions for the TraveLis Lambdalith function."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # DynamoDB Access
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchWriteItem",
          "dynamodb:BatchGetItem"
        ]
        Resource = [
          var.users_table_arn,
          var.cells_table_arn,
          var.offers_table_arn,
          var.user_offers_table_arn
        ]
      },
      # Cognito Access
      {
        Effect = "Allow"
        Action = [
          "cognito-idp:AdminDeleteUser"
        ]
        Resource = [
          var.cognito_user_pool_arn
        ]
      },
      # S3 Access (Geo Catalog)
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = [
          "${var.geo_catalog_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          var.geo_catalog_bucket_arn
        ]
      },
      # EventBridge Scheduler Access (Create/Update/Delete user matching schedules)
      {
        Effect = "Allow"
        Action = [
          "scheduler:CreateSchedule",
          "scheduler:UpdateSchedule",
          "scheduler:DeleteSchedule",
          "scheduler:GetSchedule"
        ]
        Resource = [
          "arn:aws:scheduler:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:schedule/*"
        ]
      },
      # IAM PassRole (Required when assigning the execution role to EventBridge Scheduler triggers)
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          var.scheduler_role_arn
        ]
      },
      # Direct Self-Invocation permission for Scraper continuation
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${var.project}-${var.environment}-lambdalith-*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "custom_policy_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_custom_policy.arn
}

resource "aws_cloudwatch_log_group" "api_lambda_logs" {
  name              = "/aws/lambda/${var.project}-${var.environment}-lambdalith-api"
  retention_in_days = var.environment == "prod" ? 30 : 14
}

resource "aws_cloudwatch_log_group" "cron_lambda_logs" {
  name              = "/aws/lambda/${var.project}-${var.environment}-lambdalith-cron"
  retention_in_days = var.environment == "prod" ? 30 : 14
}

locals {
  common_environment_variables = {
    REDIS_URL                  = var.redis_url
    COGNITO_USER_POOL_ID       = var.cognito_user_pool_id
    COGNITO_APP_CLIENT_ID      = var.cognito_app_client_id
    DYNAMODB_USERS_TABLE       = var.users_table_name
    DYNAMODB_CELLS_TABLE       = var.cells_table_name
    DYNAMODB_OFFERS_TABLE      = var.offers_table_name
    DYNAMODB_USER_OFFERS_TABLE = var.user_offers_table_name
    VAPID_PUBLIC_KEY           = var.vapid_public_key
    VAPID_PRIVATE_KEY          = var.vapid_private_key
    FRONTEND_URL               = var.frontend_url
    SCHEDULER_ROLE_ARN         = var.scheduler_role_arn
    ATTRACTIVENESS_Z_THRESHOLD = tostring(var.attractiveness_z_threshold)
    POWERTOOLS_SERVICE_NAME    = "${var.project}-backend"
    POWERTOOLS_LOG_LEVEL       = var.environment == "prod" ? "INFO" : "DEBUG"
    ENVIRONMENT                = var.environment
  }
}

resource "aws_lambda_function" "api_lambda" {
  function_name    = "${var.project}-${var.environment}-lambdalith-api"
  role             = aws_iam_role.lambda_role.arn
  handler          = "app.main.handler"
  runtime          = "python3.13"
  timeout          = 30 # 30 seconds for API GW
  memory_size      = 1024
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = merge(local.common_environment_variables, {
      LAMBDA_FUNCTION_ARN = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${var.project}-${var.environment}-lambdalith-api"
    })
  }

  tags = {
    Name = "${var.project}-${var.environment}-lambdalith-api"
  }

  depends_on = [aws_cloudwatch_log_group.api_lambda_logs]
}

resource "aws_lambda_function" "cron_lambda" {
  function_name    = "${var.project}-${var.environment}-lambdalith-cron"
  role             = aws_iam_role.lambda_role.arn
  handler          = "app.main.handler"
  runtime          = "python3.13"
  timeout          = 900 # 15 minutes for cron jobs
  memory_size      = 1024
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = merge(local.common_environment_variables, {
      LAMBDA_FUNCTION_ARN = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${var.project}-${var.environment}-lambdalith-cron"
    })
  }

  tags = {
    Name = "${var.project}-${var.environment}-lambdalith-cron"
  }

  depends_on = [aws_cloudwatch_log_group.cron_lambda_logs]
}

resource "aws_lambda_permission" "cognito_trigger" {
  statement_id  = "AllowExecutionFromCognito"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api_lambda.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = var.cognito_user_pool_arn
}
