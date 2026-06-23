# Production Infrastructure Deployment

This directory contains the Terraform configuration to deploy the production infrastructure for the TraveLis backend.

## Prerequisites

Before deploying the production environment, make sure you have:
1. An AWS Account with credentials configured locally (e.g., using the AWS profile `travelis-terraform`).
2. A production Redis Cloud database (TLS enabled) and its connection URL.
3. Production Web Push VAPID keys (public and private).
4. (Optional) Grafana Cloud AWS Account ID and External ID if integrating with Grafana Cloud for monitoring.

## 1. Remote State Management (Highly Recommended)

To ensure the Terraform state file is backed up and supports concurrent deployment safety:
1. Create a private S3 bucket in your production AWS account (e.g., `travelis-prod-terraform-state`).
2. Create a DynamoDB table for state locking (e.g., `travelis-prod-terraform-locks`) with a Partition Key named `LockID` of type String.
3. Open [versions.tf](versions.tf) and uncomment the `backend "s3"` block:
   ```terraform
   backend "s3" {
     bucket         = "YOUR_S3_BUCKET_NAME"
     key            = "state/terraform.tfstate"
     region         = "YOUR_AWS_REGION"
     dynamodb_table = "YOUR_DYNAMODB_LOCK_TABLE_NAME"
     encrypt        = true
   }
   ```
4. Run `terraform init` to migrate your state to AWS.

If you choose to skip this step, Terraform will keep the state file locally on your computer (`terraform.tfstate`). Be careful not to lose or delete this file!

## 2. Configuration Setup

1. Copy the boilerplate variables file or edit the existing [terraform.tfvars](terraform.tfvars):
   * Populate `redis_url` with your production Redis database URL.
   * Populate `vapid_public_key` and `vapid_private_key` with your production keys.
   * Populate `grafana_cloud_aws_account_id` and `grafana_cloud_external_id` (or leave empty if not using Grafana monitoring).
   * Verify the `aws_profile` and `aws_region` are correct.

## 3. Initial Deploy

Run the following commands to initialize Terraform, check the plan, and deploy the stack:

```bash
# Initialize Terraform
terraform init

# Plan changes to verify what will be created
terraform plan

# Apply changes to deploy to AWS
terraform apply
```

## 4. Seeding the Geo Catalog

Once the deployment completes successfully, the Geo Catalog S3 bucket will be created. You must copy the initial provider geo catalogs into this bucket so that the scraping coordinator knows where to scrape:

```bash
# Get the name of the bucket from the outputs:
# terraform output geo_catalog_bucket_name

# Copy the TUI and Wakacjepl geo catalogs to S3:
aws s3 cp ../../../docs/providers/tui/tui_geo_catalog.json \
  s3://<geo_catalog_bucket_name>/providers/tui/tui_geo_catalog.json

aws s3 cp ../../../docs/providers/wakacjepl/wakacjepl_geo_catalog.json \
  s3://<geo_catalog_bucket_name>/providers/wakacjepl/wakacjepl_geo_catalog.json
```
