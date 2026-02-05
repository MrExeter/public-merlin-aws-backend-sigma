# NON-FUNCTIONING PUBLIC COPY

# AWS BaaS (API Gateway + Lambda + DynamoDB + Cognito)

A modular, versioned BaaS skeleton:
- REST API under `/v1`
- Cognito authorizer (Web & Backend clients)
- Usage logging to DynamoDB
- Metering skeleton (monthly aggregator → draft invoices)
- Tenants foundation (map Cognito `client_id` → `tenant_id`)

## NOTE: ALL Credentials, env variables etc have been removed

## Quick Start

### Prereqs
- AWS credentials (`AWS_PROFILE`, `CDK_DEFAULT_ACCOUNT`, `CDK_DEFAULT_REGION`)
- CDK bootstrapped in target account/region

### Deploy (core)
```bash
cdk synth
cdk deploy UsageStack UsageLambdaStack UsageApiStack AuthStack AuthApiStack


# Tenants (client_id → tenant_id mapping)
cdk deploy TenantsStack

# Metering (invoices table + aggregator; schedule OFF by default)
cdk deploy MeteringStack