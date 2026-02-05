# Ops & Troubleshooting

## Common API errors
- **403 Forbidden**: wrong URL; missing **/<stage>** segment
- **401 Unauthorized**: missing/expired token; wrong authorizer
- **400 Missing required field**: body lacks `user_id`, `token_count`, or `endpoint`

## Cognito
- **invalid_scope**: scope must be `myapi-<stage>/usage.read` (resource server identifier + scope name)
- Hosted UI code flow: ensure `redirect_uri` EXACTLY matches a registered callback

## Tenants
- `tenant_id` = "unknown": Tenants table has no row for this `client_id`
  - Seed: `client_id → tenant_id, app_id`

## Testing locally
- Use **moto**; set `AWS_DEFAULT_REGION`
- Lazy env/table init prevents import-time KeyErrors
