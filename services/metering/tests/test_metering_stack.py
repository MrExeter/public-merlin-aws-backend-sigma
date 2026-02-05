import aws_cdk as cdk
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk.assertions import Template
from cdk.stacks.metering_stack import MeteringStack

def _make_usage_table(scope: cdk.Stack):
    return dynamodb.Table(
        scope, "UsageLogs",
        partition_key=dynamodb.Attribute(name="usage_id", type=dynamodb.AttributeType.STRING),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
    )

def test_metering_stack_resources_without_schedule():
    app = cdk.App()
    infra = cdk.Stack(app, "Infra")
    usage_table = _make_usage_table(infra)

    meter = MeteringStack(app, "MeteringStackTestNoSched", usage_table=usage_table)
    template = Template.from_stack(meter)

    # Has a DynamoDB table for invoices
    template.resource_count_is("AWS::DynamoDB::Table", 1)
    # Has the Lambda function
    template.resource_count_is("AWS::Lambda::Function", 1)
    # No EventBridge Rule by default
    template.resource_count_is("AWS::Events::Rule", 0)

def test_metering_stack_with_schedule_flag():
    app = cdk.App(context={"enable_metering_aggregation": "true"})
    infra = cdk.Stack(app, "Infra2")
    usage_table = _make_usage_table(infra)

    meter = MeteringStack(app, "MeteringStackTestSched", usage_table=usage_table)
    template = Template.from_stack(meter)

    # EventBridge Rule present when flag enabled
    template.resource_count_is("AWS::Events::Rule", 1)
