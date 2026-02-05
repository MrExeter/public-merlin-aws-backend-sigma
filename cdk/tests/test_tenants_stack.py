import aws_cdk as cdk
import aws_cdk.assertions as assertions
import pytest

from cdk.stacks.tenants_stack import TenantsStack


@pytest.fixture
def template():
    """Synth the TenantsStack into a CloudFormation template for assertions."""
    app = cdk.App()
    stack = TenantsStack(app, "TestTenantsStack")
    return assertions.Template.from_stack(stack)


# --- Infra Tests ---

def test_dynamodb_table_created(template):
    template.has_resource_properties("AWS::DynamoDB::Table", {
        "TableName": "Tenants",
        "BillingMode": "PAY_PER_REQUEST",
        "KeySchema": [
            {"AttributeName": "client_id", "KeyType": "HASH"}
        ],
        "AttributeDefinitions": [
            {"AttributeName": "client_id", "AttributeType": "S"}
        ]
    })


def test_table_has_retain_policy(template):
    resources = template.find_resources("AWS::DynamoDB::Table")
    table = next(iter(resources.values()))
    assert table["DeletionPolicy"] == "Retain"


def test_table_has_pitr_enabled(template):
    resources = template.find_resources("AWS::DynamoDB::Table")
    table = next(iter(resources.values()))
    pitr_spec = table["Properties"].get("PointInTimeRecoverySpecification", {})
    assert pitr_spec.get("PointInTimeRecoveryEnabled") is True


def test_outputs_present(template):
    outputs = template.to_json().get("Outputs", {})
    keys = list(outputs.keys())
    assert any("TenantsTableName" in k for k in keys)
    assert any("TenantsTableArn" in k for k in keys)



# --- Resilience / Schema Tests ---

def test_tenants_table_has_correct_partition_key(template):
    resources = template.find_resources("AWS::DynamoDB::Table")
    table = next(iter(resources.values()))
    key_schema = table["Properties"]["KeySchema"]
    assert key_schema[0]["AttributeName"] == "client_id"
    assert key_schema[0]["KeyType"] == "HASH"


def test_tenants_table_pitr_property(template):
    resources = template.find_resources("AWS::DynamoDB::Table")
    table = next(iter(resources.values()))
    pitr_spec = table["Properties"].get("PointInTimeRecoverySpecification", {})
    assert pitr_spec.get("PointInTimeRecoveryEnabled") is True
