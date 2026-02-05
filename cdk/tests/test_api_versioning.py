import aws_cdk as cdk
from aws_cdk.assertions import Template
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as ddb

from cdk.stacks.usage_stack import UsageStack
from cdk.stacks.usage_lambda_stack import UsageLambdaStack
from cdk.stacks.usage_api_stack import UsageApiStack

def test_only_v1_at_api_root():
    app = cdk.App()
    env = cdk.Environment(account="111111111111", region="us-west-1")

    # owner stack + table (single source of truth for tests)
    owner = cdk.Stack(app, "OwnerStack", env=env)
    usage_table = ddb.Table(
        owner, "UsageLogs",
        table_name="UsageLogs",  # or omit if you don’t care about the name in tests
        partition_key=ddb.Attribute(name="usage_id", type=ddb.AttributeType.STRING),
        billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
    )

    # Create a stack to host the user pool (must be under a Stack, not App)
    auth_stack = cdk.Stack(app, "AuthTestStack", env=env)
    user_pool = cognito.UserPool(
        auth_stack, "TestUserPool",
        self_sign_up_enabled=False,
        sign_in_aliases=cognito.SignInAliases(email=True),
        auto_verify=cognito.AutoVerifiedAttrs(email=True),
    )

    usage = UsageStack(app, "UsageStack", env=env)

    lambdas = UsageLambdaStack(
        app, "UsageLambdaStack",
        usage_logs_table=usage_table,
        env=env,
    )

    api = UsageApiStack(
        app, "UsageApiStack",
        user_pool=user_pool,  # <-- required now
        log_usage_lambda=lambdas.log_usage_lambda,
        aggregate_lambda=lambdas.aggregate_lambda,
        env=env,
    )

    t = Template.from_stack(api)

    # Assert only /v1 is directly under the API root
    rest_apis = t.find_resources("AWS::ApiGateway::RestApi")
    assert len(rest_apis) == 1
    rest_api_id = next(iter(rest_apis.keys()))

    resources = t.find_resources("AWS::ApiGateway::Resource")
    top_level = []
    for _, res in resources.items():
        if res["Properties"].get("ParentId") == {"Fn::GetAtt": [rest_api_id, "RootResourceId"]}:
            top_level.append(res["Properties"]["PathPart"])

    assert top_level == ["v1"], f"Top-level paths must be only ['v1'], got {top_level}"


def test_usage_lambda_stack_synthesizes_handlers_and_alarms():
    app = cdk.App()
    env = cdk.Environment(account="111111111111", region="us-west-1")

    # Owner/table for the test
    owner = cdk.Stack(app, "OwnerStack", env=env)
    usage_table = ddb.Table(
        owner, "UsageLogs",
        partition_key=ddb.Attribute(name="usage_id", type=ddb.AttributeType.STRING),
        billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
    )

    # System under test
    sut = UsageLambdaStack(app, "UsageLambdaStackTest", usage_logs_table=usage_table, env=env)
    sut.add_dependency(owner)

    t = Template.from_stack(sut)

    # Assert both functions exist with correct handlers (dot notation)
    funcs = t.find_resources("AWS::Lambda::Function")
    handlers = {res["Properties"]["Handler"] for res in funcs.values()}
    assert handlers == {
        "usage.lambdas.log_usage.handler.handler",
        "usage.lambdas.aggregate.handler.handler",  # ✅ Fixed here
    }

    # Alarms + SNS topic present
    t.resource_count_is("AWS::CloudWatch::Alarm", 2)  # usage + aggregator
    t.resource_count_is("AWS::SNS::Topic", 1)

