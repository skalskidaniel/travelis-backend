output "geo_catalog_bucket_name" {
  description = "S3 bucket for provider geo catalogs."
  value       = module.geo_catalog.bucket_name
}

output "geo_catalog_bucket_arn" {
  description = "ARN of the geo catalog bucket."
  value       = module.geo_catalog.bucket_arn
}

output "geo_catalog_object_keys" {
  description = "S3 object keys for provider geo catalogs."
  value       = module.geo_catalog.object_keys
}
