resource "aws_dynamodb_table" "users" {
  name           = "${var.project}-${var.environment}-users"
  billing_mode   = "PROVISIONED"
  read_capacity  = 5
  write_capacity = 5
  hash_key       = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  tags = {
    Name = "${var.project}-${var.environment}-users"
  }
}

resource "aws_dynamodb_table" "cells" {
  name           = "${var.project}-${var.environment}-cells"
  billing_mode   = "PROVISIONED"
  read_capacity  = 5
  write_capacity = 5
  hash_key       = "cell_id"

  attribute {
    name = "cell_id"
    type = "S"
  }

  tags = {
    Name = "${var.project}-${var.environment}-cells"
  }
}

resource "aws_dynamodb_table" "offers" {
  name           = "${var.project}-${var.environment}-offers"
  billing_mode   = "PROVISIONED"
  read_capacity  = 5
  write_capacity = 5
  hash_key       = "cell_id"
  range_key      = "offer_id"

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
  name           = "${var.project}-${var.environment}-user-offers"
  billing_mode   = "PROVISIONED"
  read_capacity  = 5
  write_capacity = 5
  hash_key       = "user_id"
  range_key      = "offer_id"

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
