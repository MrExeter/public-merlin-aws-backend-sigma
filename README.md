# Merlin Sigma — Public Reference Implementation (production credentials removed)

## AWS BaaS (API Gateway + Lambda + DynamoDB + Cognito)


A modular, versioned AWS-native Backend-as-a-Service foundation:

- REST API under `/v1`
- Cognito authorizer (Web + backend clients)
- Usage logging to DynamoDB
- Metering framework (monthly aggregation → draft invoices)
- Multi-tenant foundation (maps Cognito `client_id` → `tenant_id`)
- CDK-managed infrastructure

This repository represents a **public reference build** of Merlin Sigma.  
All production credentials, account-specific configuration, and alert routing have been removed.

---

## Quick Start

### Prerequisites

- AWS credentials (`AWS_PROFILE`, `CDK_DEFAULT_ACCOUNT`, `CDK_DEFAULT_REGION`)
- AWS CDK bootstrapped in target account/region

---

## Running Tests
Tests run fully locally using mocked AWS and dummy credentials.

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt

pytest
```

---

### Deploy (core)

```bash
cdk synth
cdk deploy UsageStack UsageLambdaStack UsageApiStack AuthStack AuthApiStack

# Tenants (client_id → tenant_id mapping)
cdk deploy TenantsStack

# Metering (invoices table + aggregator; schedule OFF by default)
cdk deploy MeteringStack
