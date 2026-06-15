data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "geo_catalog" {
  bucket = "${var.project}-${var.environment}-geo-catalog-${data.aws_caller_identity.current.account_id}"

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Purpose     = "provider-geo-catalogs"
  }
}

resource "aws_s3_bucket_versioning" "geo_catalog" {
  bucket = aws_s3_bucket.geo_catalog.id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "geo_catalog" {
  bucket = aws_s3_bucket.geo_catalog.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "geo_catalog" {
  bucket = aws_s3_bucket.geo_catalog.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
