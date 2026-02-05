# services/auth/tests/test_auth_api_stack.py

import os
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from cdk.stacks.auth_api_stack import AuthApiStack

@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("CDK_DEFAULT_ACCOUNT", "123456789012")
    monkeypatch.setenv("CDK_DEFAULT_REGION", "us-west-1")
    yield

def test_auth_api_stack_authorizer():
    app = cdk.App()
    dummy_user_pool_arn = "arn:aws:cognito-idp:us-west-1:123456789012:userpool/test"
    dummy_api_id = "fake-api-id"

    stack = AuthApiStack(app, "TestAuthApiStack",
                         user_pool_arn=dummy_user_pool_arn,
                         rest_api_id=dummy_api_id,
                         env=cdk.Environment(
                             account=os.getenv("CDK_DEFAULT_ACCOUNT"),
                             region=os.getenv("CDK_DEFAULT_REGION"),
                         ))
    template = Template.from_stack(stack)

    # one Authorizer
    template.resource_count_is("AWS::ApiGateway::Authorizer", 1)

    # it must reference the correct pool ARN and API ID
    template.has_resource_properties("AWS::ApiGateway::Authorizer", {
        "Type": "COGNITO_USER_POOLS",
        "ProviderARNs": [dummy_user_pool_arn],
        "RestApiId": dummy_api_id,
        "IdentitySource": "method.request.header.Authorization",
    })
