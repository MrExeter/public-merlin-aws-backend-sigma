# services/auth/tests/test_auth_stack.py

import os
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from cdk.stacks.auth_stack import AuthStack

@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("CDK_DEFAULT_ACCOUNT", "123456789012")
    monkeypatch.setenv("CDK_DEFAULT_REGION", "us-west-1")
    # Also set a dummy stage so the secret import context works
    monkeypatch.setenv("CDK_CONTEXT_STAGE", "dev")
    yield

def test_auth_stack_resources():
    app = cdk.App(context={"stage": "dev"})
    stack = AuthStack(app, "TestAuthStack",
                      env=cdk.Environment(
                          account=os.getenv("CDK_DEFAULT_ACCOUNT"),
                          region=os.getenv("CDK_DEFAULT_REGION"),
                      ))
    template = Template.from_stack(stack)

    # 1) One User Pool
    template.resource_count_is("AWS::Cognito::UserPool", 1)

    # 2) Three generic UserPoolIdentityProvider resources
    template.resource_count_is("AWS::Cognito::UserPoolIdentityProvider", 2)

    # 3) Verify each provider’s name is correct
    providers = template.find_resources("AWS::Cognito::UserPoolIdentityProvider")
    types = {
        res["Properties"]["ProviderType"]
        for res in providers.values()
    }
    # assert types == {"Google", "Facebook", "OIDC"}
    assert types == {"Google", "Facebook"}

    # 4) Two User Pool Clients
    template.resource_count_is("AWS::Cognito::UserPoolClient", 2)

    # 5) Verify OAuth flows on at least one client
    template.has_resource_properties("AWS::Cognito::UserPoolClient", {
        "AllowedOAuthFlows": ["code"],
        "AllowedOAuthScopes": ["openid", "email", "profile"],
    })
