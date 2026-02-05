# cdk/stacks/auth_stack.py

from aws_cdk import (
    Stack,
    aws_cognito as cognito,
    aws_secretsmanager as secrets,
    RemovalPolicy,
)
from constructs import Construct

class AuthStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, env=None, **kwargs):
        stage = kwargs.pop("stage", "dev")
        super().__init__(scope, construct_id, env=env, **kwargs)

        stage = self.node.try_get_context("stage") or "dev"

        # 1) User Pool
        user_pool = cognito.UserPool(
            self, "UserPool",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=False)
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # 2) Social IdPs
        providers = [
            ("Google", "google-client-id", "google-client-secret"),
            ("Facebook", "fb-client-id", "fb-client-secret"),
        ]
        for name, id_key, secret_key in providers:
            sec = secrets.Secret.from_secret_name_v2(
                self, f"{name}Secret", secret_name=f"/{stage}/auth/{name.lower()}"
            )
            if name == "Google":
                cognito.UserPoolIdentityProviderGoogle(
                    self, "GoogleIdp",
                    user_pool=user_pool,
                    client_id=sec.secret_value_from_json(id_key).to_string(),
                    client_secret_value=sec.secret_value_from_json(secret_key),
                    scopes=["email", "profile", "openid"],
                )
            elif name == "Facebook":
                cognito.UserPoolIdentityProviderFacebook(
                    self, "FacebookIdp",
                    user_pool=user_pool,
                    client_id=sec.secret_value_from_json(id_key).to_string(),
                    client_secret=sec.secret_value_from_json(secret_key).to_string(),
                    scopes=["email", "public_profile"],
                )

        # 3) Resource Server & Scopes
        usage_read_scope = cognito.ResourceServerScope(
            scope_name="usage.read",
            scope_description="Read usage data"
        )
        resource_server = user_pool.add_resource_server(
            "MyApiResourceServer",
            identifier=f"myapi-{stage}",
            scopes=[usage_read_scope]
        )

        # 4) App Clients

        # a) Web client (auth code grant)
        user_pool.add_client(
            "WebAppClient",
            auth_flows=cognito.AuthFlow(user_srp=True, user_password=True),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE,
                ],
                callback_urls=["https://your-app.com/callback"],
                logout_urls=["https://your-app.com/logout"],
            ),
        )

        # b) Backend client (client credentials grant)
        user_pool.add_client(
            "BackendClient",
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True),
                scopes=[
                    cognito.OAuthScope.resource_server(
                        resource_server,
                        usage_read_scope  # pass the ResourceServerScope object
                    )
                ],
            ),
        )

        # 5) Exports
        self.user_pool     = user_pool
        self.user_pool_id  = user_pool.user_pool_id
        self.user_pool_arn = user_pool.user_pool_arn
