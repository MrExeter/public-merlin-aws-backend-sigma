import json
import pytest
import uuid
from types import SimpleNamespace


class FakeTable:
    """
    Simple fake DynamoDB Table for unit tests.

    Supports:
      - scan()
      - query()
      - get_item()
      - put_item()
      - update_item()
    """

    def __init__(
        self,
        scan_items=None,
        query_items=None,
        get_item=None,
        should_fail=False
    ):
        self.scan_items = scan_items or []
        self.query_items = query_items or []
        self.get_item_value = get_item
        self.should_fail = should_fail

    def scan(self, **kwargs):
        if self.should_fail:
            raise Exception("FakeTable scan failed")
        return {"Items": self.scan_items}

    def query(self, **kwargs):
        if self.should_fail:
            raise Exception("FakeTable query failed")
        return {"Items": self.query_items}

    def get_item(self, Key=None, **kwargs):
        if self.should_fail:
            raise Exception("FakeTable get_item failed")
        if self.get_item_value:
            return {"Item": self.get_item_value}
        return {}

    def put_item(self, Item=None, **kwargs):
        if self.should_fail:
            raise Exception("FakeTable put_item failed")
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def update_item(self, **kwargs):
        if self.should_fail:
            raise Exception("FakeTable update_item failed")
        return {"Attributes": {}}


class FakeDynamoResource:
    """
    Mimics boto3.resource("dynamodb") for testing.
    """

    def __init__(self, tables):
        self.tables = tables

    def Table(self, table_name):
        if table_name not in self.tables:
            raise Exception(f"FakeDynamoResource: Unknown table {table_name}")
        return self.tables[table_name]


@pytest.fixture
def tenants_table_name():
    return "FakeTenantsTable"

@pytest.fixture
def plans_table_name():
    return "FakePlansTable"

@pytest.fixture
def usage_table_name():
    return "FakeUsageTable"

@pytest.fixture
def lambda_context():
    class Ctx:
        function_name = "test_fn"
    return Ctx()

