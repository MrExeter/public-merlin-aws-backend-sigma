# services/plans/crud.py

from services.plans.models import Plan
from boto3.resources.base import ServiceResource
from typing import Optional

TABLE_NAME = "PlansTable"


def create_plan(plan: Plan, dynamodb: Optional[ServiceResource] = None) -> dict:
    if not dynamodb:
        import boto3
        dynamodb = boto3.resource("dynamodb")

    table = dynamodb.Table(TABLE_NAME)
    item = plan.model_dump()
    table.put_item(Item=item)
    return item
