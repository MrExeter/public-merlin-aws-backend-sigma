# services/usage/crud.py

import os
from typing import Optional

from boto3.resources.base import ServiceResource
from services.usage.models import UsageRecord
from services.common.ddb_utils import ddb_safe  # <- ensure this file exists

DEFAULT_USAGE_TABLE_NAME = "UsageLogs"  # fallback for local/dev; prefer env var in tests/CDK


def get_usage_table_name() -> str:
    return os.getenv("USAGE_TABLE_NAME", DEFAULT_USAGE_TABLE_NAME)

def log_usage(record: UsageRecord, dynamodb: Optional[ServiceResource] = None) -> dict:
    if dynamodb is None:
        import boto3
        dynamodb = boto3.resource("dynamodb")

    table = dynamodb.Table(get_usage_table_name())
    item = record.for_dynamodb()
    table.put_item(Item=ddb_safe(item))
    return item