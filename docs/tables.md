# DynamoDB Tables

## UsageLogs
- **PK**: `usage_id` (S)
- **Attrs**: `tenant_id` (S), `app_id` (S), `user_id` (S), `token_count` (N serialized via Decimal), `endpoint` (S), `timestamp` (ISO8601)
- **GSI**: `user_id-index` → PK `user_id`, SK `timestamp`

## Tenants
- **PK**: `client_id` (S)
- **Attrs**: `tenant_id` (S), `app_id` (S), `plan` (S), `created_at` (S, ISO8601 optional)

## UsageInvoices
- **PK**: `invoice_id` (S) — e.g. `<tenant_id>-<YYYY-MM>`
- **Attrs**: `tenant_id` (S), `period_label` (S, `YYYY-MM`), `tokens` (S), `status` (S), `estimated_aws_cost_usd` (S), `created_at` (S)
- **GSI (optional/if configured)**: `TenantPeriodIndex` → PK `tenant_id`, SK `period_label`
