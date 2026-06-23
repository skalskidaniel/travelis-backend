output "users_table_name" {
  value = aws_dynamodb_table.users.name
}

output "users_table_arn" {
  value = aws_dynamodb_table.users.arn
}

output "cells_table_name" {
  value = aws_dynamodb_table.cells.name
}

output "cells_table_arn" {
  value = aws_dynamodb_table.cells.arn
}

output "offers_table_name" {
  value = aws_dynamodb_table.offers.name
}

output "offers_table_arn" {
  value = aws_dynamodb_table.offers.arn
}

output "user_offers_table_name" {
  value = aws_dynamodb_table.user_offers.name
}

output "user_offers_table_arn" {
  value = aws_dynamodb_table.user_offers.arn
}