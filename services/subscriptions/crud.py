# services/subscriptions/crud.py

from typing import Optional
from boto3.resources.base import ServiceResource
from services.subscriptions.models import Subscription

TABLE_NAME = "SubscriptionsTable"


def create_subscription(subscription: Subscription, dynamodb: Optional[ServiceResource] = None) -> dict:
    if not dynamodb:
        import boto3
        dynamodb = boto3.resource("dynamodb")

    table = dynamodb.Table(TABLE_NAME)
    item = subscription.model_dump()
    table.put_item(Item=item)
    return item
