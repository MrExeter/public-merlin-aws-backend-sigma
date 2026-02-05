from constructs import Construct
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_cognito as cognito,
    Environment,
)
import os


# --------------------------------------------
# CORRECT PROJECT ROOT RESOLUTION
# --------------------------------------------
from pathlib import Path

# Locate this file (.../merlin-sigma/cdk/stacks/control_panel_api_stack.py)
stack_file = Path(__file__).resolve()

# Project root (.../merlin-sigma)
project_root = stack_file.parents[2]

# Lambda directory (.../merlin-sigma/control_panel_api)
lambda_dir = project_root / "control_panel_api"
lambda_dir = str(lambda_dir)



class ControlPanelApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, env_name="dev", **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --------------------------------------------
        # Locate lambda directory (sibling to /cdk)
        # --------------------------------------------
        # base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # lambda_dir = os.path.join(base_dir, "control_panel_api")

        print("DEBUG LAMBDA_DIR:", lambda_dir)

        # --------------------------------------------
        # IMPORT EXISTING TABLES (DO NOT RECREATE)
        # --------------------------------------------
        tenants_table = dynamodb.Table.from_table_name(
            self,
            "MerlinSigmaTenantsRef",
            "MerlinSigmaTenants"
        )

        plans_table = dynamodb.Table.from_table_name(
            self,
            "PlansTableRef",
            "PlansStack-dev-PlansTableD3E3A972-16PBXWJILMXMA"
        )

        usage_table = dynamodb.Table.from_table_name(
            self, "UsageLogsRef",
            "UsageLogs"
        )

        # --------------------------------------------
        # COGNITO USER POOL + AUTHORIZER
        # --------------------------------------------
        user_pool = cognito.UserPool.from_user_pool_id(
            self, "ControlPanelUserPool", "us-west-1_deJVBhpC3"
        )

        user_pool_client = cognito.UserPoolClient(
            self,
            "ControlPanelUserPoolClient",
            user_pool=user_pool,
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True
            )
        )

        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self,
            "ControlPanelAuthorizer",
            cognito_user_pools=[user_pool]
        )

        # --------------------------------------------
        # API GATEWAY
        # --------------------------------------------
        api = apigw.RestApi(
            self,
            "MerlinSigmaControlPanelApi",
            rest_api_name=f"MerlinSigma-ControlPanel-{env_name}",
            deploy_options=apigw.StageOptions(stage_name=env_name),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS
            )
        )

        tenants = api.root.add_resource("tenants")
        tenant_id_resource = tenants.add_resource("{tenantId}")
        tenant_plan_resource = tenant_id_resource.add_resource("plan")

        # --------------------------------------------
        # GET /tenants Lambda
        # --------------------------------------------
        list_tenants_fn = _lambda.Function(
            self,
            "ListTenantsFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="list_tenants.handler",
            code=_lambda.Code.from_asset(lambda_dir),
            timeout=Duration.seconds(15),
            environment={
                "TENANTS_TABLE": tenants_table.table_name,
                "ENV_NAME": env_name,
            }
        )

        tenants_table.grant_read_data(list_tenants_fn)

        tenants.add_method(
            "GET",
            apigw.LambdaIntegration(list_tenants_fn, proxy=True),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"]
        )

        # --------------------------------------------
        # GET /tenants/{tenantId}/plan Lambda
        # --------------------------------------------
        get_plan_fn = _lambda.Function(
            self,
            "GetTenantPlanFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="get_plan.handler",
            code=_lambda.Code.from_asset(lambda_dir),
            timeout=Duration.seconds(15),
            environment={
                "TENANTS_TABLE": tenants_table.table_name,
                "PLANS_TABLE": plans_table.table_name,
                "ENV_NAME": env_name,
            }
        )

        tenants_table.grant_read_data(get_plan_fn)
        plans_table.grant_read_data(get_plan_fn)

        tenant_plan_resource.add_method(
            "GET",
            apigw.LambdaIntegration(get_plan_fn, proxy=True),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"]
        )

        # --------------------------------------------
        # PUT /tenants/{tenantId}/plan Lambda
        # --------------------------------------------
        put_plan_fn = _lambda.Function(
            self,
            "PutTenantPlanFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="put_plan.handler",
            code=_lambda.Code.from_asset(lambda_dir),
            timeout=Duration.seconds(15),
            environment={
                "TENANTS_TABLE": tenants_table.table_name,
                "PLANS_TABLE": plans_table.table_name,
                "ENV_NAME": env_name,
            }
        )

        # --------------------------------------------
        # GET /tenants/{tenantId}/usage Lambda
        # --------------------------------------------
        get_usage_fn = _lambda.Function(
            self,
            "GetTenantUsageFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="get_usage.handler",
            code=_lambda.Code.from_asset(lambda_dir),
            timeout=Duration.seconds(15),
            environment={
                "USAGE_TABLE_NAME": usage_table.table_name,
            },
        )

        # --------------------------------------------
        # GET /tenants/{tenantId}/quota Lambda
        # --------------------------------------------
        get_quota_fn = _lambda.Function(
            self,
            "GetTenantQuotaFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="get_quota.handler",
            code=_lambda.Code.from_asset(lambda_dir),
            timeout=Duration.seconds(15),
            environment={
                "USAGE_TABLE_NAME": usage_table.table_name,
                "TENANTS_TABLE_NAME": tenants_table.table_name,
            },
        )

        # --------------------------------------------
        # ADMIN ROUTES
        # --------------------------------------------
        admin = api.root.add_resource("admin")

        # /admin/me
        admin_me_resource = admin.add_resource("me")

        admin_me_fn = _lambda.Function(
            self,
            "AdminMeFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="admin_me.handler",
            code=_lambda.Code.from_asset(lambda_dir),
            timeout=Duration.seconds(15),
            environment={
                "ENV_NAME": env_name,
            },
        )

        admin_me_resource.add_method(
            "GET",
            apigw.LambdaIntegration(admin_me_fn, proxy=True),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"]
        )

        # /admin/users
        admin_users_resource = admin.add_resource("users")

        list_users_fn = _lambda.Function(
            self,
            "AdminListUsersFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="list_users.handler",
            code=_lambda.Code.from_asset(lambda_dir),
            timeout=Duration.seconds(15),
            environment={
                "ENV_NAME": env_name,
            },
        )

        admin_users_resource.add_method(
            "GET",
            apigw.LambdaIntegration(list_users_fn, proxy=True),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"]
        )

        # POST /admin/users  → create user
        create_user_fn = _lambda.Function(
            self,
            "AdminCreateUserFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="create_user.handler",
            code=_lambda.Code.from_asset(lambda_dir),
            timeout=Duration.seconds(15),
            environment={
                "ENV_NAME": env_name,
                "USER_POOL_ID": user_pool.user_pool_id,
            },
        )

        admin_users_resource.add_method(
            "POST",
            apigw.LambdaIntegration(create_user_fn, proxy=True),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"]
        )

        # POST /admin/users/{username}/roles
        admin_user_roles = admin_users_resource.add_resource("{username}").add_resource("roles")

        assign_roles_fn = _lambda.Function(
            self,
            "AdminAssignRolesFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="assign_roles.handler",
            code=_lambda.Code.from_asset(lambda_dir),
            timeout=Duration.seconds(15),
            environment={
                "ENV_NAME": env_name,
                "USER_POOL_ID": user_pool.user_pool_id,
            },
        )

        admin_user_roles.add_method(
            "POST",
            apigw.LambdaIntegration(assign_roles_fn, proxy=True),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"]
        )



        usage_table.grant_read_data(get_usage_fn)
        usage_table.grant_read_data(get_quota_fn)
        tenants_table.grant_read_data(get_quota_fn)

        tenant_usage_resource = tenant_id_resource.add_resource("usage")
        tenant_quota_resource = tenant_id_resource.add_resource("quota")

        tenant_usage_resource.add_method(
            "GET",
            apigw.LambdaIntegration(get_usage_fn, proxy=True),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )

        tenant_quota_resource.add_method(
            "GET",
            apigw.LambdaIntegration(get_quota_fn, proxy=True),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"],
        )

        tenants_table.grant_read_write_data(put_plan_fn)
        plans_table.grant_read_data(put_plan_fn)

        tenant_plan_resource.add_method(
            "PUT",
            apigw.LambdaIntegration(put_plan_fn, proxy=True),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=["aws.cognito.signin.user.admin"]
        )

        # --------------------------------------------
        # DEBUG / META endpoint (optional)
        # --------------------------------------------
        debug = api.root.add_resource("debug")
        debug.add_method(
            "GET",
            apigw.MockIntegration(
                integration_responses=[{
                    "statusCode": "200",
                    "responseTemplates": {"application/json": '{"status": "ok"}'}
                }],
                request_templates={"application/json": '{"status": "ok"}'}
            ),
            method_responses=[{"statusCode": "200"}]
        )
