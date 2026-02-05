# API Versioning

- All external endpoints live under `/v1`.
- Backward-compatible changes update `/v1`.
- Breaking changes create `/v2`, and `/v1` is maintained for a deprecation window.

## CDK pattern
```python
v1 = api.root.add_resource("v1")
usage = v1.add_resource("usage")
usage_log = usage.add_resource("log")
