# services/usage/tests/test_handler_integration.py
import os
import json
from datetime import datetime
import boto3
import importlib
from moto import mock_aws

import services.usage.lambdas.log_usage.handler as log_usage_handler


def test_log_usage_writes_item_and_respects_quota(lambda_ctx):
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["USAGE_TABLE_NAME"] = "UsageTable"
    os.environ["TENANTS_TABLE_NAME"] = "TenantsTable"
    os.environ["QUOTA_TABLE_NAME"] = "QuotaTable"

    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")

        ddb.create_table(
            TableName="UsageTable",
            KeySchema=[
                {"AttributeName": "tenant_month", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "tenant_month", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        ddb.create_table(
            TableName="TenantsTable",
            KeySchema=[{"AttributeName": "tenant_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "tenant_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        ddb.create_table(
            TableName="QuotaTable",
            KeySchema=[{"AttributeName": "plan_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "plan_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # 🔑 Import after Moto is live and env is set
        import services.usage.lambdas.log_usage.handler as log_usage_handler
        importlib.reload(log_usage_handler)

        tenants = ddb.Table("TenantsTable")
        quota = ddb.Table("QuotaTable")

        tenants.put_item(Item={"tenant_id": "t-123", "plan_id": "basic-plan", "subscription_status": "active"})
        quota.put_item(Item={"plan_id": "basic-plan", "quota_limit": 1000})

        event = {"body": json.dumps({"tenant_id": "t-123", "token_count": 5, "endpoint": "/e"})}

        resp = log_usage_handler.handler(event, lambda_ctx)

        assert resp["statusCode"] == 200
        assert "Usage recorded" in resp["body"]

