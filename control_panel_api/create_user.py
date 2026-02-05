import json
import os

import boto3


def handler(event, context):
    """
    POST /admin/users

    Body:
      {
        "username": "charlie",
        "email": "charlie@example.com",
        "groups": ["Admins", "Developers"]
      }
    """
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
    if not user_pool_id:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "COGNITO_USER_POOL_ID not set"}),
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

        username = body.get("username")
        email = body.get("email")
        groups = body.get("groups") or []

        if not username or not email:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "username and email are required"}),
            }

        cognito = boto3.client("cognito-idp")

        attrs = [{"Name": "email", "Value": email}]
        cognito.admin_create_user(
            UserPoolId=user_pool_id,
            Username=username,
            UserAttributes=attrs,
            MessageAction="SUPPRESS",  # no email send in this pattern
        )

        for group in groups:
            cognito.admin_add_user_to_group(
                UserPoolId=user_pool_id,
                Username=username,
                GroupName=group,
            )

        resp_body = {
            "username": username,
            "email": email,
            "groups": groups,
        }

        return {
            "statusCode": 201,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(resp_body),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
