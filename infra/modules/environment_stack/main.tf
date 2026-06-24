data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  api_lambda_name  = "${var.project}-${var.environment}-lambdalith-api"
  cron_lambda_name = "${var.project}-${var.environment}-lambdalith-cron"
  api_lambda_arn   = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.api_lambda_name}"
  cron_lambda_arn  = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.cron_lambda_name}"
}

module "geo_catalog" {
  source = "../geo_catalog"

  project     = var.project
  environment = var.environment
}

module "dynamodb" {
  source = "../dynamodb"

  project     = var.project
  environment = var.environment
}

module "cognito" {
  source = "../cognito"

  project     = var.project
  environment = var.environment
}

module "eventbridge" {
  source = "../eventbridge"

  project                      = var.project
  environment                  = var.environment
  lambda_arn                   = local.cron_lambda_arn
  lambda_name                  = local.cron_lambda_name
  scheduler_invoke_lambda_arns = [local.cron_lambda_arn]
}

module "lambda" {
  source = "../lambda"

  project                    = var.project
  environment                = var.environment
  redis_url                  = var.redis_url
  frontend_url               = var.frontend_url
  users_table_name           = module.dynamodb.users_table_name
  users_table_arn            = module.dynamodb.users_table_arn
  cells_table_name           = module.dynamodb.cells_table_name
  cells_table_arn            = module.dynamodb.cells_table_arn
  offers_table_name          = module.dynamodb.offers_table_name
  offers_table_arn           = module.dynamodb.offers_table_arn
  user_offers_table_name     = module.dynamodb.user_offers_table_name
  user_offers_table_arn      = module.dynamodb.user_offers_table_arn
  geo_catalog_bucket_name    = module.geo_catalog.bucket_name
  geo_catalog_bucket_arn     = module.geo_catalog.bucket_arn
  cognito_user_pool_id       = module.cognito.user_pool_id
  cognito_user_pool_arn      = module.cognito.user_pool_arn
  cognito_app_client_id      = module.cognito.app_client_id
  vapid_public_key           = var.vapid_public_key
  vapid_private_key          = var.vapid_private_key
  scheduler_role_arn         = module.eventbridge.scheduler_role_arn
  attractiveness_z_threshold = var.attractiveness_z_threshold
}

module "api_gateway" {
  source = "../api_gateway"

  project      = var.project
  environment  = var.environment
  frontend_url = var.frontend_url
  lambda_arn   = module.lambda.api_lambda_arn
  lambda_name  = module.lambda.api_lambda_name
}

resource "aws_lambda_permission" "allow_eventbridge_scrape" {
  statement_id  = "AllowExecutionFromEventBridgeScrape"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.cron_lambda_name
  principal     = "events.amazonaws.com"
  source_arn    = module.eventbridge.scrape_offers_rule_arn
}

resource "aws_lambda_permission" "allow_eventbridge_availability" {
  statement_id  = "AllowExecutionFromEventBridgeAvailability"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.cron_lambda_name
  principal     = "events.amazonaws.com"
  source_arn    = module.eventbridge.check_availability_rule_arn
}

resource "aws_lambda_permission" "allow_scheduler_match" {
  statement_id  = "AllowExecutionFromEventBridgeScheduler"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.cron_lambda_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = "arn:aws:scheduler:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:schedule/*"
}

module "monitoring" {
  source = "../monitoring"

  project                      = var.project
  environment                  = var.environment
  grafana_cloud_aws_account_id = var.grafana_cloud_aws_account_id
  grafana_cloud_external_id    = var.grafana_cloud_external_id
  api_lambda_name              = module.lambda.api_lambda_name
  cron_lambda_name             = module.lambda.cron_lambda_name
  api_gateway_id               = module.api_gateway.api_id
}

# -----------------------------------------------------------------------------
# Workaround for Cognito <-> Lambda circular dependency
# -----------------------------------------------------------------------------
# We attach the Lambda trigger out-of-band using AWS CLI via local-exec
# AFTER both Cognito and Lambda have been fully provisioned.
resource "null_resource" "cognito_trigger_attachment" {
  depends_on = [module.cognito, module.lambda]

  triggers = {
    user_pool_id = module.cognito.user_pool_id
    lambda_arn   = module.lambda.api_lambda_arn
  }

  provisioner "local-exec" {
    command = <<EOF
cat << 'PYTHON_SCRIPT' > update_cognito.py
import boto3
import sys

pool_id = '${module.cognito.user_pool_id}'
lambda_arn = '${module.lambda.api_lambda_arn}'
region = '${data.aws_region.current.name}'

client = boto3.client('cognito-idp', region_name=region)

try:
    response = client.describe_user_pool(UserPoolId=pool_id)
    pool = response['UserPool']
    
    ALLOWED_KEYS = {
        'UserPoolId', 'Policies', 'DeletionProtection', 'LambdaConfig',
        'AutoVerifiedAttributes', 'SmsVerificationMessage', 'EmailVerificationMessage',
        'EmailVerificationSubject', 'VerificationMessageTemplate', 'SmsAuthenticationMessage',
        'UserAttributeUpdateSettings', 'MfaConfiguration', 'DeviceConfiguration',
        'EmailConfiguration', 'SmsConfiguration', 'UserPoolTags', 'AdminCreateUserConfig',
        'UserPoolAddOns', 'AccountRecoverySetting', 'PoolName', 'UserPoolTier'
    }

    kwargs = {}
    for key in ALLOWED_KEYS:
        if key in pool:
            kwargs[key] = pool[key]
            
    # Clean up empty strings or values that fail validation if empty
    for k in list(kwargs.keys()):
        val = kwargs[k]
        if val is None:
            del kwargs[k]
        elif isinstance(val, str) and not val.strip():
            del kwargs[k]
        elif isinstance(val, dict) and not val:
            del kwargs[k]
        elif isinstance(val, list) and not val:
            del kwargs[k]

    kwargs['UserPoolId'] = pool_id

    if 'LambdaConfig' not in kwargs:
        kwargs['LambdaConfig'] = {}

    kwargs['LambdaConfig']['PostConfirmation'] = lambda_arn

    client.update_user_pool(**kwargs)
    print(f"Successfully attached {lambda_arn} to {pool_id}")
except Exception as e:
    print(f"Error updating User Pool: {e}")
    sys.exit(1)
PYTHON_SCRIPT
AWS_PROFILE="${var.aws_profile}" uv run python update_cognito.py
EXIT_CODE=$?
rm -f update_cognito.py
exit $EXIT_CODE
EOF
  }
}
