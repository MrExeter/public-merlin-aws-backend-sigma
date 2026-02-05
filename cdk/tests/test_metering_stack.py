import aws_cdk as cdk
import aws_cdk.assertions as assertions
from aws_cdk import aws_dynamodb as dynamodb
import pytest

from cdk.stacks.metering_stack import MeteringStack


@pytest.fixture
def template():
    """Synth the MeteringStack into a CloudFormation template for assertions."""
    app = cdk.App()
    env = cdk.Environment(account="111111111111", region="us-west-1")

    # Create a dummy usage table to satisfy dependency
    usage_stack = cdk.Stack(app, "UsageStack", env=env)
    usage_table = dynamodb.Table(
        usage_stack, "UsageTable",
        partition_key=dynamodb.Attribute(name="id", type=dynamodb.AttributeType.STRING),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
    )

    # Now pass usage_table into MeteringStack
    stack = MeteringStack(app, "TestMeteringStack", usage_table=usage_table, env=env)
    return assertions.Template.from_stack(stack)


# --- Infra Tests ---

def test_invoices_table_created(template):
    """Ensure the invoices (metering) table exists with correct schema."""
    resources = template.find_resources("AWS::DynamoDB::Table")
    assert len(resources) == 1

    table = next(iter(resources.values()))
    props = table["Properties"]

    assert props.get("BillingMode") == "PAY_PER_REQUEST"
    keys = [k["AttributeName"] for k in props["KeySchema"]]
    assert "invoice_id" in keys   # ✅ match actual stack schema


def test_table_has_retain_policy(template):
    """Ensure the invoices table retains data when stack is deleted."""
    resources = template.find_resources("AWS::DynamoDB::Table")
    table = next(iter(resources.values()))
    assert table["DeletionPolicy"] == "Retain"


def test_table_schema_matches_design(template):
    """Check explicitly for invoice_id key schema."""
    resources = template.find_resources("AWS::DynamoDB::Table")
    table = next(iter(resources.values()))
    props = table["Properties"]
    key_schema = props["KeySchema"]
    assert key_schema[0]["AttributeName"] == "invoice_id"
    assert key_schema[0]["KeyType"] == "HASH"


def test_outputs_present(template):
    """Check that stack exports aggregator + table outputs."""
    outputs = template.to_json().get("Outputs", {})
    keys = list(outputs.keys())
    assert any("MonthlyUsageAggregatorName" in k for k in keys)
    assert any("MeteringTableName" in k for k in keys)
    assert any("MeteringTableArn" in k for k in keys)
