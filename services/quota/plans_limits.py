# services/quota/plans_limits.py

PLAN_LIMITS = {
    "plan_free": {
        "max_tokens_per_day": 1000,
        "max_requests_per_day": 100
    },
    "plan_pro": {
        "max_tokens_per_day": 100_000,
        "max_requests_per_day": 5_000
    },
    "plan_enterprise": {
        "max_tokens_per_day": float("inf"),
        "max_requests_per_day": float("inf")
    }
}


def get_plan_limits(plan_id: str) -> dict:
    return PLAN_LIMITS.get(plan_id, PLAN_LIMITS["plan_free"])
