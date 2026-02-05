import os, boto3, json
events = boto3.client("events")

def _emit_usage_event(item):
    if os.getenv("USAGE_EVENTS_ENABLED", "false").lower() != "true":
        return
    detail = {
        "ts": item.get("timestamp"),
        "tenant_id": item.get("user_id"),  # replace with real tenant when available
        "service": "usage",
        "action": "log",
        "quantity": item.get("token_count", 0),
        "meta": {"endpoint": item.get("endpoint")}
    }
    try:
        events.put_events(Entries=[{
            "Source": "baas.metering",
            "DetailType": "UsageEvent",
            "Detail": json.dumps(detail),
            "EventBusName": "default",
        }])
    except Exception:
        # best-effort only; never fail the request on metering
        pass
