# Infrastructure

Terraform-managed AWS resources with modular layout. Secrets via Terraform Vault provider and/or AWS SSM Parameter Store.

## Directory layout

```
infra/
├── modules/
│   ├── lambda/           # Lambdalith function + IAM role
│   ├── api_gateway/      # HTTP API → Lambda
│   ├── dynamodb/         # 4 tables (provisioned)
│   ├── cognito/          # User pool + app client + post-confirmation trigger
│   ├── eventbridge/      # Cron rules + Scheduler (debounced match) role
│   └── monitoring/       # CloudWatch, Grafana integration
└── environments/
    └── dev/
        ├── main.tf       # Composes modules
        ├── variables.tf
        ├── outputs.tf
        └── terraform.tfvars
```

Add `environments/prod/` when deploying to production.

## AWS resources

### Lambda (lambdalith)

| Setting | Value                                                  |
| ------- | ------------------------------------------------------ |
| Runtime | Python 3.13 (latest Lambda runtime)                    |
| Handler | `app.main.handler` (dual entry: Mangum + jobs)         |
| Timeout | 15 min (max)                                           |
| Memory  | 1024 MB (tune based on scrape concurrency)             |
| Package | Contents of `src/` (`app/` + `core/`) at artifact root |

The deployment artifact zips the **contents** of `src/`, so `app` and `core` are top-level importable packages and the handler resolves as `app.main.handler`.

**IAM permissions:**

- DynamoDB read/write on all 4 tables
- Cognito admin delete user
- EventBridge Scheduler `CreateSchedule` / `UpdateSchedule` / `DeleteSchedule` (+ `iam:PassRole` for the schedule's target role)
- CloudWatch Logs
- (Optional) SSM Parameter Store read

No VPC attachment required (Redis Cloud is external, providers are public HTTPS).

### API Gateway

HTTP API (v2) proxying all routes to the Lambda. Routes:

- `ANY /api/v2/{proxy+}` → Lambda

### DynamoDB

Four tables with **provisioned capacity** (cost control):

| Table         | PK        | SK         | GSI            | TTL                                                     |
| ------------- | --------- | ---------- | -------------- | ------------------------------------------------------- |
| `Users`       | `user_id` | —          | —              |                                                         |
| `MarketCells` | `cell_id` | —          | —              |                                                         |
| `Offers`      | `cell_id` | `offer_id` | —              | `ttl` (epoch of `departure_date`)                       |
| `UserOffers`  | `user_id` | `offer_id` | —              | Pruned cascadingly by eventual consistency in match job |

Start with low provisioned RCU/WCU; auto-scaling or manual tuning as load grows.

### Cognito

| Resource   | Purpose                          |
| ---------- | -------------------------------- |
| User Pool  | Email/password or social sign-up |
| App Client | PWA public client (no secret)    |
| JWT        | Validated by FastAPI middleware  |

### EventBridge rules

Only the periodic jobs use fixed schedules. There is **no `match-users` poll** — matching is event-driven (see below).

| Rule                 | Schedule                  | Target          | Job                 |
| -------------------- | ------------------------- | --------------- | ------------------- |
| `scrape-offers`      | `cron(0 6,14,22 * * ? *)` | Lambda (direct) | `jobs.coordinator`  |
| `check-availability` | `cron(0 4 * * ? *)`       | Lambda (direct) | `jobs.availability` |

Cron times are UTC; adjust for desired local schedule.

`jobs.coordinator` triggers a **bulk re-match** of users on the affected cells when scraping completes (in-process), so no separate rule wires scrape → match.

### EventBridge Scheduler (debounced per-user match)

Preference changes and new-account provisioning create **one-time** schedules instead of polling:

| Setting                 | Value                                                                 |
| ----------------------- | --------------------------------------------------------------------- |
| Name                    | `match-{user_id}` (deterministic → upsert debounces)                  |
| Expression              | `at(now + 30s)`                                                       |
| `ActionAfterCompletion` | `DELETE` (self-cleaning)                                              |
| Target                  | Lambda (direct), payload `{ "type": "match_user", "user_id": "..." }` |

See [pipeline.md](pipeline.md#preference-debouncing-eventbridge-scheduler).

### Cognito triggers

| Trigger           | Target          | Action                                                                         |
| ----------------- | --------------- | ------------------------------------------------------------------------------ |
| Post-confirmation | Lambda (direct) | Create `Users` row with defaults, activate default cells, schedule first match |

Folded into the lambdalith via the dual-entry handler (`event.triggerSource`). A lazy get-or-create on the first authenticated request is the fallback if the trigger ever fails.

### Redis Cloud

| Setting    | Value                                                                |
| ---------- | -------------------------------------------------------------------- |
| Provider   | [Redis Cloud](https://redis.com/redis-enterprise-cloud/) (free tier) |
| Purpose    | User offer feed ZSETs, optional offer payload cache                  |
| Connection | `REDIS_URL` env var on Lambda                                        |
| TLS        | Required (Redis Cloud default)                                       |

**Not used:** AWS ElastiCache (avoids VPC cold starts and cost).

## Environment variables (Lambda)

| Variable                     | Source           | Description                   |
| ---------------------------- | ---------------- | ----------------------------- |
| `REDIS_URL`                  | SSM / Vault      | Redis Cloud connection string |
| `COGNITO_USER_POOL_ID`       | Terraform output |                               |
| `COGNITO_APP_CLIENT_ID`      | Terraform output |                               |
| `DYNAMODB_USERS_TABLE`       | Terraform output |                               |
| `DYNAMODB_CELLS_TABLE`       | Terraform output |                               |
| `DYNAMODB_OFFERS_TABLE`      | Terraform output |                               |
| `DYNAMODB_USER_OFFERS_TABLE` | Terraform output |                               |
| `ATTRACTIVENESS_Z_THRESHOLD` | SSM              | Default `-1.0`                |
| `VAPID_PRIVATE_KEY`          | Vault            | Web Push signing              |
| `VAPID_PUBLIC_KEY`           | SSM              | Web Push public key           |
| `FRONTEND_URL`               | SSM / env        | e.g. `https://wakacje-travelis.pl` (used for `share_url`) |

Never commit secrets. Use `.env.example` with placeholders for local dev.

## Local development

```bash
# Run API locally (no Lambda); src/ is the source root
uvicorn app.main:app --reload --port 8000 --app-dir src

# Env vars from .env (DynamoDB Local + Redis Cloud dev instance)
```

DynamoDB Local or dev AWS account for integration testing. Redis Cloud free database for dev.

## Monitoring

| Tool                  | Scope                       |
| --------------------- | --------------------------- |
| AWS Lambda Powertools | Structured logging, tracing |
| Grafana               | Backend dashboards          |
| Sentry                | Frontend PWA only           |

## Deployment flow

```bash
cd infra/environments/dev
terraform init
terraform plan
terraform apply
```

Lambda deployment artifact: zip or container image built from the contents of `src/` (`app/` + `core/`) plus dependencies (see `pyproject.toml`).

## Cost notes

- **Provisioned DynamoDB** — predictable cost; tune capacity down when idle.
- **Single Lambda** — one function bill; no per-cell Lambda charges.
- **Redis Cloud free tier** — sufficient for early user count.
- **EventBridge** — negligible cost for 3–4 rules.

## Future scaling triggers

| Signal                   | Action                                                |
| ------------------------ | ----------------------------------------------------- |
| Lambda timeout on scrape | Split `jobs/` into separate Lambdas                   |
| DynamoDB throttling      | Enable auto-scaling or switch hot tables to on-demand |
| Redis memory limit       | Upgrade Redis Cloud plan or trim payload cache        |
