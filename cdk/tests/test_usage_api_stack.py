import aws_cdk as cdk
import aws_cdk.assertions as assertions
import pytest

from aws_cdk import aws_cognito as cognito, aws_lambda as _lambda
from cdk.stacks.usage_api_stack import UsageApiStack


@pytest.fixture
def template():
    app = cdk.App()
    env = cdk.Environment(account="111111111111", region="us-west-1")

    # Minimal user pool + lambdas for stack instantiation
    auth_stack = cdk.Stack(app, "AuthStack", env=env)
    user_pool = cognito.UserPool(auth_stack, "TestUserPool")

    log_fn = _lambda.Function(
        auth_stack, "LogFn",
        code=_lambda.Code.from_inline("def handler(event, ctx): return {}"),
        handler="index.handler",
        runtime=_lambda.Runtime.PYTHON_3_9,
    )

    agg_fn = _lambda.Function(
        auth_stack, "AggFn",
        code=_lambda.Code.from_inline("def handler(event, ctx): return {}"),
        handler="index.handler",
        runtime=_lambda.Runtime.PYTHON_3_9,
    )

    stack = UsageApiStack(
        app, "UsageApiStackTest",
        user_pool=user_pool,
        log_usage_lambda=log_fn,
        aggregate_lambda=agg_fn,
        env=env,
    )

    return assertions.Template.from_stack(stack)


# --- Infra Tests ---

def test_rest_api_created(template):
    template.has_resource_properties("AWS::ApiGateway::RestApi", {
        "Name": "UsageApi",
    })


def test_cognito_authorizer_attached(template):
    resources = template.find_resources("AWS::ApiGateway::Authorizer")
    assert any(r["Properties"]["Type"] == "COGNITO_USER_POOLS" for r in resources.values())


def test_log_usage_endpoint(template):
    methods = template.find_resources("AWS::ApiGateway::Method")
    post_methods = [m for m in methods.values() if m["Properties"]["HttpMethod"] == "POST"]
    assert any("log" in str(m["Properties"]["ResourceId"]) for m in post_methods)


def test_aggregate_usage_endpoint(template):
    methods = template.find_resources("AWS::ApiGateway::Method")
    get_methods = [m for m in methods.values() if m["Properties"]["HttpMethod"] == "GET"]
    assert any("aggregate" in str(m["Properties"]["ResourceId"]) for m in get_methods)


def test_outputs_present(template):
    outputs = template.to_json().get("Outputs", {})
    keys = list(outputs.keys())
    assert any("UsageApiId" in k for k in keys)
    assert any("UsageApiRootId" in k for k in keys)
