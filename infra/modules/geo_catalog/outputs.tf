output "bucket_name" {
  description = "S3 bucket storing provider geo catalogs."
  value       = aws_s3_bucket.geo_catalog.id
}

output "bucket_arn" {
  description = "ARN of the geo catalog bucket."
  value       = aws_s3_bucket.geo_catalog.arn
}

output "object_keys" {
  description = "Canonical S3 object keys for provider geo catalogs."
  value = {
    tui       = "providers/tui/tui_geo_catalog.json"
    wakacjepl = "providers/wakacjepl/wakacjepl_geo_catalog.json"
  }
}
