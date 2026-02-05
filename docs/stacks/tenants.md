# Tenants Stack

## TenantsStack
- DynamoDB `Tenants`
  - PK `client_id` (S)
  - Attrs: `tenant_id` (S), `app_id` (S), `plan` (S, optional), `created_at` (ISO8601 optional)

### Purpose
- Map Cognito **App Client** (`client_id` from access token) → your **tenant_id** (and optional `app_id`).

### Seeding example
```bash
aws dynamodb put-item --table-name Tenants \
  --item '{
    "client_id":{"S":"<BACKEND_CLIENT_ID>"},
    "tenant_id":{"S":"tenant-dev"},
    "app_id":{"S":"app-1"},
    "plan":{"S":"dev"}
  }'
