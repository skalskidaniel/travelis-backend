data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  frontend_origin = trimsuffix(var.frontend_url, "/")
  www_frontend_origin = startswith(local.frontend_origin, "https://www.") ? null : replace(
    local.frontend_origin,
    "https://",
    "https://www.",
  )
  oauth_redirect_urls = distinct(compact([
    "http://localhost:3000",
    local.frontend_origin,
    local.www_frontend_origin,
  ]))
  cognito_domain_prefix = "${var.project}-auth-${data.aws_caller_identity.current.account_id}"
  enable_google_oidc    = var.google_client_id != "" && var.google_client_secret != ""
}

resource "aws_cognito_user_pool" "pool" {
  name                     = "${var.project}-${var.environment}-user-pool"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # lambda_config is managed out-of-band by the null_resource in environment_stack
  lifecycle {
    ignore_changes = [
      lambda_config
    ]
  }

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }

  schema {
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    name                     = "email"
    required                 = true

    string_attribute_constraints {
      min_length = 7
      max_length = 256
    }
  }

  tags = {
    Name = "${var.project}-${var.environment}-user-pool"
  }
}

resource "aws_cognito_user_pool_domain" "domain" {
  domain       = local.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.pool.id
}

resource "aws_cognito_identity_provider" "google" {
  count = local.enable_google_oidc ? 1 : 0

  user_pool_id  = aws_cognito_user_pool.pool.id
  provider_name = "Google"
  provider_type = "Google"

  provider_details = {
    client_id        = var.google_client_id
    client_secret    = var.google_client_secret
    authorize_scopes = "openid email profile"
  }

  attribute_mapping = {
    email    = "email"
    name     = "name"
    username = "sub"
  }
}

resource "aws_cognito_user_pool_client" "client" {
  name            = "${var.project}-${var.environment}-app-client"
  user_pool_id    = aws_cognito_user_pool.pool.id
  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]

  supported_identity_providers = concat(
    ["COGNITO"],
    local.enable_google_oidc ? ["Google"] : []
  )

  callback_urls = local.oauth_redirect_urls
  logout_urls   = local.oauth_redirect_urls

  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["email", "openid", "profile"]
  allowed_oauth_flows_user_pool_client = true

  depends_on = [aws_cognito_identity_provider.google]
}
