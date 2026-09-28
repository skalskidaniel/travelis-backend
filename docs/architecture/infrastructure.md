# Infrastructure

Terraform-managed AWS resources with modular layout. The VAPID private key is stored in Secrets Manager. Other runtime settings are Lambda environment variables populated from Terraform variables.

## Directory layout

```
infra/
├── modules/
│   ├── geo_catalog/      # S3 bucket for provider geo catalogs
│   ├── lambda/           # Dual lambdalith functions + IAM role
│   ├── api_gateway/      # HTTP API → Lambda
│   ├── dynamodb/         # 4 tables (on-demand)
│   ├── cognito/          # User pool + app client + post-confirmation trigger
│   ├── eventbridge/      # Cron rules + Scheduler (debounced match) role
│   └── monitoring/       # CloudWatch, Grafana integration
└── environments/
    ├── dev/
    │   ├── main.tf       # Composes modules
    │   ├── variables.tf
    │   ├── outputs.tf
    │   └── terraform.tfvars
    └── prod/
        ├── main.tf       # Composes modules (production settings)
        ├── variables.tf
        ├── outputs.tf
        ├── terraform.tfvars # Production parameters template
        ├── versions.tf   # Remote S3 state backend config option
        └── README.md     # Production deployment instructions
```

## AWS resources

### Lambda (dual lambdalith functions)

| Function            | Target                                                     | Timeout | Memory  |
| ------------------- | ---------------------------------------------------------- | ------- | ------- |
| `*-lambdalith-api`  | API Gateway and Cognito post-confirmation trigger          | 30s     | 1024 MB |
| `*-lambdalith-cron` | EventBridge cron jobs and EventBridge Scheduler match jobs | 15 min  | 1024 MB |

Both functions use:

| Setting | Value                                                  |
| ------- | ------------------------------------------------------ |
| Runtime | Python 3.13 (latest Lambda runtime)                    |
| Handler | `app.main.handler` (dual entry: Mangum + jobs)         |
| Package | Contents of `src/` (`app/` + `core/`) at artifact root |

The deployment artifact zips the **contents** of `src/`, so `app` and `core` are top-level importable packages and the handler resolves as `app.main.handler`. The same artifact is deployed to both Lambda functions; the split exists to keep HTTP requests on a short timeout while letting background jobs use the full Lambda timeout.

**IAM permissions:**

- DynamoDB read/write on all 4 tables (`GetItem`, `PutItem`, `UpdateItem`, `DeleteItem`, `Query`, `Scan`, `BatchGetItem`, `BatchWriteItem`, `DescribeTable`)
- Cognito `AdminDeleteUser`
- S3 `GetObject` and `ListBucket` on the geo catalog bucket
- EventBridge Scheduler `CreateSchedule` / `UpdateSchedule` / `DeleteSchedule` / `GetSchedule` (+ `iam:PassRole` for the schedule's target role)
- `lambda:InvokeFunction` on `*-lambdalith-*` (scrape continuation targets the cron function)
- `secretsmanager:GetSecretValue` on the VAPID private key secret
- CloudWatch Logs via `AWSLambdaBasicExecutionRole`

No VPC attachment required (Redis Cloud is external, providers are public HTTPS).

### S3 (provider geo catalogs)

Private bucket for refreshed destination/departure catalogs used at scrape time:

| Setting  | Value                                                                                         |
| -------- | --------------------------------------------------------------------------------------------- |
| Module   | `modules/geo_catalog`                                                                         |
| Objects  | `providers/tui/tui_geo_catalog.json`, `providers/wakacjepl/wakacjepl_geo_catalog.json`        |
| Access   | Lambda read (IAM added with `lambda` module); writes via `scripts/fetch_geo_catalog.py` or CI |
| Security | SSE-S3, public access blocked, versioning enabled                                             |

Populate after `terraform apply`:

```bash
aws s3 cp docs/providers/tui/tui_geo_catalog.json \
  s3://<bucket>/providers/tui/tui_geo_catalog.json
aws s3 cp docs/providers/wakacjepl/wakacjepl_geo_catalog.json \
  s3://<bucket>/providers/wakacjepl/wakacjepl_geo_catalog.json
```

### API Gateway

HTTP API (v2) proxying all routes to the Lambda. Routes:

- `ANY /v2/{proxy+}` → Lambda (`$default` stage, so the public path is `/v2/...` with no `/api` prefix)

**CORS** is this HTTP API's `cors_configuration`, not FastAPI middleware. `allow_origins` is the single Terraform `frontend_url`. `allow_headers` is `Content-Type` and `Authorization`. `allow_methods` is `GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS` (`max_age` 300). `PUT` is absent, so browser preflight for `PUT /v2/offers/{offer_id}/favorite` does not allow that method. Cognito callback URLs add a `www` variant; this CORS list does not. Stage throttling is 100 requests/second with a burst of 50, separate from the Redis rate limiter.

**Custom domain.** `custom_domain` empty skips these resources. When set (for example `api.wakacje-travelis.pl`):

- Terraform looks up an **already issued** ACM certificate for that exact domain in the API region. It does not create the certificate or the DNS record.
- The domain is a regional HTTP API custom domain with TLS 1.2, mapped to the `$default` stage.
- Apply outputs `custom_domain_target` and `custom_domain_hosted_zone_id` for an alias record. A missing or pending certificate fails the plan.

### DynamoDB

Four tables with **on-demand capacity** (`PAY_PER_REQUEST`) for low operational overhead during early traffic:

| Table         | PK        | SK         | GSI | TTL                                                       |
| ------------- | --------- | ---------- | --- | --------------------------------------------------------- |
| `Users`       | `user_id` | —          | —   |                                                           |
| `MarketCells` | `cell_id` | —          | —   |                                                           |
| `Offers`      | `cell_id` | `offer_id` | —   | `ttl` (departure_date while available; now+14d when sold) |
| `UserOffers`  | `user_id` | `offer_id` | —   | Pruned cascadingly by eventual consistency in match job   |

No capacity units are configured. Revisit provisioned capacity only if traffic becomes predictable enough that it is clearly cheaper than on-demand billing.

### Cognito

| Resource   | Purpose                          |
| ---------- | -------------------------------- |
| User Pool  | Email sign-up (`username_attributes = email`) |
| App Client | Public client (no secret). Flows: user-password, SRP, refresh token |
| Hosted UI  | Cognito domain `{project}-auth-{account_id}`. Authorization code, scopes `email` `openid` `profile` |
| JWT        | Validated by `get_current_user` → `CognitoJwtVerifier` (JWKS) |

**Google sign-in** is optional. Both `google_client_id` and `google_client_secret` must be non-empty or the Google identity provider is not created and the app client stays on `COGNITO` only. Callback and logout URLs are `http://localhost:3000`, `FRONTEND_URL`, and the `www.` variant of that origin when the configured URL is not already `www`. Attribute mapping is `email`, `name`, and `username = sub`.

### EventBridge rules

Only the periodic jobs use fixed schedules. There is **no `match-users` poll** — matching is event-driven (see below).

| Rule                 | Schedule                     | Target               | Job                 |
| -------------------- | ---------------------------- | -------------------- | ------------------- |
| `scrape-offers`        | `cron(0 6,10,14,18 * * ? *)` | Cron Lambda (direct) | `jobs.coordinator`           |
| `check-availability`   | `cron(0 8,12,16,20 * * ? *)` | Cron Lambda (direct) | `jobs.availability`          |
| `sweep-inactive-users` | `cron(0 3 ? * MON *)`        | Cron Lambda (direct) | `jobs.user_inactivity_sweep` |

Cron times are UTC; adjust for desired local schedule.

`jobs.coordinator` triggers a **bulk re-match** of users on the affected cells when scraping completes (in-process), so no separate rule wires scrape → match.

### EventBridge Scheduler (debounced per-user match)

Preference changes and new-account provisioning create **one-time** schedules instead of polling:

| Setting                 | Value                                                                      |
| ----------------------- | -------------------------------------------------------------------------- |
| Name                    | `match-{user_id}` (deterministic → upsert debounces)                       |
| Expression              | `at(now + 15s)`                                                            |
| `ActionAfterCompletion` | `DELETE` (self-cleaning)                                                   |
| Target                  | Cron Lambda (direct), payload `{ "type": "match_user", "user_id": "..." }` |

See [pipeline.md](pipeline.md#preference-debouncing-eventbridge-scheduler).

### Cognito triggers

| Trigger           | Target              | Action                                                                         |
| ----------------- | ------------------- | ------------------------------------------------------------------------------ |
| Post-confirmation | API Lambda (direct) | Create `Users` row with defaults, activate default cells, schedule first match |

Folded into the lambdalith via the dual-entry handler (`event.triggerSource`). A lazy get-or-create on the first authenticated request is the fallback if the trigger ever fails.

### Redis Cloud

| Setting    | Value                                                                |
| ---------- | -------------------------------------------------------------------- |
| Provider   | [Redis Cloud](https://redis.com/redis-enterprise-cloud/) (free tier) |
| Purpose    | User offer feed ZSETs, rate limiting, optional offer payload cache   |
| Connection | `REDIS_URL` env var on Lambda                                        |
| TLS        | Required (Redis Cloud default)                                       |

**Not used:** AWS ElastiCache (avoids VPC cold starts and cost).

## Environment variables (Lambda)

Terraform sets these on **both** Lambda functions (`infra/modules/lambda/main.tf`). `LAMBDA_FUNCTION_ARN` is the cron function ARN on the API function and on the cron function (Scheduler targets and scrape continuation both invoke cron).

| Variable                     | Set by Terraform | Description                                                                 |
| ---------------------------- | ---------------- | --------------------------------------------------------------------------- |
| `REDIS_URL`                  | yes              | Redis Cloud connection string                                               |
| `COGNITO_USER_POOL_ID`       | yes              |                                                                             |
| `COGNITO_APP_CLIENT_ID`      | yes              |                                                                             |
| `DYNAMODB_USERS_TABLE`       | yes              |                                                                             |
| `DYNAMODB_CELLS_TABLE`       | yes              |                                                                             |
| `DYNAMODB_OFFERS_TABLE`      | yes              |                                                                             |
| `DYNAMODB_USER_OFFERS_TABLE` | yes              |                                                                             |
| `VAPID_PUBLIC_KEY`           | yes              | Web Push public key                                                         |
| `VAPID_PRIVATE_KEY_SECRET_ARN` | yes            | Secrets Manager ARN. At init the container loads `SecretString` and uses it as the private key. |
| `FRONTEND_URL`               | yes              | e.g. `https://wakacje-travelis.pl` (used for `share_url` and API Gateway CORS) |
| `ATTRACTIVENESS_Z_THRESHOLD` | yes              | Terraform variable, code default `-1.2` if unset                            |
| `SCHEDULER_ROLE_ARN`         | yes              | Role EventBridge Scheduler assumes to invoke the cron Lambda                |
| `LAMBDA_FUNCTION_ARN`        | yes              | Cron Lambda ARN                                                             |
| `ENVIRONMENT`                | yes              | `dev` or `prod`. `prod` turns off `/docs`, `/redoc`, and `/openapi.json`.   |
| `POWERTOOLS_SERVICE_NAME`    | yes              | `{project}-backend`                                                         |
| `POWERTOOLS_LOG_LEVEL`       | yes              | `INFO` in prod, `DEBUG` otherwise                                           |

Not set by Terraform. Code defaults apply unless you add the env var yourself:

| Variable                    | Default | Description                                                                 |
| --------------------------- | ------- | --------------------------------------------------------------------------- |
| `RATE_LIMITING_ENABLED`     | `true`  | `false` bypasses the Redis rate limiter                                     |
| `INACTIVITY_THRESHOLD_DAYS` | `7`     | Days without a new session before the weekly sweep releases a user's cells  |
| `SESSION_GAP_MINUTES`       | `30`    | Idle gap that starts a new session and moves `Users.new_since`              |
| `VAPID_PRIVATE_KEY`         | unset   | Local signing key. On Lambda, a non-empty `VAPID_PRIVATE_KEY_SECRET_ARN` replaces this value. |
| `AWS_PROFILE`               | unset   | Named profile for local `aioboto3`. Lambda uses the execution role.         |

`AWS_REGION` is provided by the Lambda runtime. Locally it defaults to `eu-central-1`.

Never commit secrets. Use `.env.example` with placeholders for local dev.

## Local development

```bash
uv sync

# REDIS_URL is required (Settings has no default). Table names default to
# Users, MarketCells, Offers, UserOffers. AWS_REGION defaults to eu-central-1.
uvicorn app.main:app --reload --port 8000 --app-dir src

uv run pytest
```

`Settings` loads `.env` from the working directory. The FastAPI lifespan calls `container.initialize()`, which opens DynamoDB, Scheduler, Cognito, Lambda, and Redis clients before the app serves traffic. A missing `REDIS_URL` fails at import. Missing AWS credentials fail during startup, so `/v2/health` never runs.

`GET /v2/health` pings Redis and `DescribeTable` on the users table. Both `ok` is HTTP 200. Either failure is HTTP 503 with `status: unhealthy`. See [api.md](api.md#get-v2health).

`/docs`, `/redoc`, and `/openapi.json` are mounted only when `ENVIRONMENT` is not `prod`.

Local uvicorn does not add CORS headers. Deployed CORS is API Gateway only, and its allow-list omits `PUT`.

For local Web Push, set `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` and leave `VAPID_PRIVATE_KEY_SECRET_ARN` unset. A set ARN makes startup call Secrets Manager and replace the env private key. If either key is missing, match still succeeds and the push send is skipped.

Integration tests stay off unless `RUN_INTEGRATION_TESTS=1` or `RUN_PROVIDER_INTEGRATION=1`. Unit tests use `respx`, `moto`, and `fakeredis`.

## Monitoring

| Tool                  | Scope                       |
| --------------------- | --------------------------- |
| AWS Lambda Powertools | Structured logging, tracing |
| Grafana               | Backend dashboards          |
| Sentry                | Frontend PWA only           |

## Deployment flow

### AWS credentials (`aws login`)

The AWS CLI `aws login` flow stores credentials in a format Terraform does not read yet. Add a bridge profile to `~/.aws/config` (once):

```ini
[profile travelis-terraform]
credential_process = aws configure export-credentials --profile default --format process
region = eu-central-1
```

Then authenticate as usual:

```bash
aws login
```

`infra/environments/dev/terraform.tfvars` sets `aws_profile = "travelis-terraform"`. Quick alternative without the bridge profile:

```bash
eval "$(aws configure export-credentials --format env)"
```

### Apply

```bash
cd infra/environments/dev
terraform init
terraform plan
terraform apply
```

Lambda deployment artifact: zip built from the contents of `src/` (`app/` + `core/`) plus dependencies (see `pyproject.toml`), then deployed to both the API and cron Lambda functions.

## Cost notes

- **On-demand DynamoDB** — no capacity planning while traffic is low or spiky.
- **Dual Lambda functions, one artifact** — timeout isolation for HTTP and jobs without duplicating code.
- **Redis Cloud free tier** — sufficient for early user count.
- **EventBridge** — negligible cost for 3–4 rules.

## Future scaling triggers

| Signal                   | Action                                                  |
| ------------------------ | ------------------------------------------------------- |
| Lambda timeout on scrape | Fan out from the cron Lambda to per-cell worker Lambdas |
| DynamoDB throttling      | Revisit hot partitions or provisioned capacity          |
| Redis memory limit       | Upgrade Redis Cloud plan or trim payload cache          |
