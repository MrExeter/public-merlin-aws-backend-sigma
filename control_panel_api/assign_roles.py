import json
import os

import boto3


def handler(event, context):
    """
    POST /admin/users/{username}/roles

    Body:
      { "groups": ["Admins", "Support"] }
    """
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
    if not user_pool_id:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "COGNITO_USER_POOL_ID not set"}),
        }

    path_params = event.get("pathParameters") or {}
    username = path_params.get("username")

    if not username:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "username is required"}),
        }

    try:
        try:
            body = json.loads(event.get("body") or "")
        except Exception:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "invalid json payload"}),
            }

        groups = body.get("groups")
        if not isinstance(groups, list) or not groups:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "groups (non-empty list) is required"}),
            }

        cognito = boto3.client("cognito-idp")

        for g in groups:
            try:
                cognito.admin_add_user_to_group(
                    UserPoolId=user_pool_id,
                    Username=username,
                    GroupName=g,
                )
            except KeyError:
                # Our FakeCognito raises KeyError for missing user.
                return {
                    "statusCode": 404,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({"error": "user not found"}),
                }

        resp_body = {
            "username": username,
            "groups": groups,
        }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(resp_body),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
