import json


def handler(event, context):
    """
    GET /admin/me

    Uses JWT claims from API Gateway (Cognito authorizer).
    """
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims")
    )

    if not claims:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "missing auth claims"}),
        }

    username = claims.get("cognito:username") or claims.get("username")
    email = claims.get("email")

    raw_groups = claims.get("cognito:groups", [])
    if isinstance(raw_groups, str):
        # Handle comma-separated or single string
        groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
    elif isinstance(raw_groups, list):
        groups = raw_groups
    else:
        groups = []

    body = {
        "username": username,
        "email": email,
        "groups": groups,
        "claims": claims,
    }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
