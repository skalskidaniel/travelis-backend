resource "aws_dynamodb_table" "users" {
  name                        = "${var.project}-${var.environment}-users"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "user_id"
  deletion_protection_enabled = var.environment == "dev" ? false : true

  point_in_time_recovery {
    enabled = var.environment == "dev" ? false : true
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  tags = {
    Name = "${var.project}-${var.environment}-users"
  }
}

resource "aws_dynamodb_table" "cells" {
  name                        = "${var.project}-${var.environment}-cells"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "cell_id"
  deletion_protection_enabled = var.environment == "dev" ? false : true

  point_in_time_recovery {
    enabled = var.environment == "dev" ? false : true
  }

  attribute {
    name = "cell_id"
    type = "S"
  }

  tags = {
    Name = "${var.project}-${var.environment}-cells"
  }
}

resource "aws_dynamodb_table" "offers" {
  name                        = "${var.project}-${var.environment}-offers"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "cell_id"
  range_key                   = "offer_id"
  deletion_protection_enabled = var.environment == "dev" ? false : true

  point_in_time_recovery {
    enabled = var.environment == "dev" ? false : true
  }

  attribute {
    name = "cell_id"
    type = "S"
  }

  attribute {
    name = "offer_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name = "${var.project}-${var.environment}-offers"
  }
}

resource "aws_dynamodb_table" "user_offers" {
  name                        = "${var.project}-${var.environment}-user-offers"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "user_id"
  range_key                   = "offer_id"
  deletion_protection_enabled = var.environment == "dev" ? false : true

  point_in_time_recovery {
    enabled = var.environment == "dev" ? false : true
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "offer_id"
    type = "S"
  }

  tags = {
    Name = "${var.project}-${var.environment}-user-offers"
  }
}