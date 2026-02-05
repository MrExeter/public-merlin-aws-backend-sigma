from services.usage.lambdas.log_usage import handler

class MockLambdaContext:
    function_name = "test_handler"
    aws_request_id = "unit-test-id"
    memory_limit_in_mb = 128
    invoked_function_arn = "arn:aws:lambda:us-east-1:000000000000:function:test_handler"

def test_handler_returns_400_on_malformed_payload(monkeypatch):
    event = {"body": "not-json"}
    context = MockLambdaContext()
    result = handler.handler(event, context)
    assert result["statusCode"] == 400
    assert "Bad payload" in result["body"]

