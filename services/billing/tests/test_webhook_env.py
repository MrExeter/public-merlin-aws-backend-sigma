# services/billing/tests/test_webhook_env.py
import importlib
import os
import pytest

MODULE = "services.billing.stripe_webhook_lambda"

def reload_mod(monkeypatch, env=None):
    # reset env for each test
    keys = [
        "STRIPE_WEBHOOK_SECRET", "STRIPE_WEBHOOK_SECRET_ARN",
        "STRIPE_SECRET_KEY", "STRIPE_SECRET_ARN",
    ]
    for k in keys:
        monkeypatch.delenv(k, raising=False)
    if env:
        for k, v in env.items():
            monkeypatch.setenv(k, v)
    return importlib.import_module(MODULE)

def test_module_imports_without_secret(monkeypatch):
    mod = reload_mod(monkeypatch)
    assert hasattr(mod, "handler")

def test_get_secret_raises_when_both_env_and_arn_missing(monkeypatch):
    mod = reload_mod(monkeypatch)
    with pytest.raises(RuntimeError):
        mod._get_secret("STRIPE_WEBHOOK_SECRET", "STRIPE_WEBHOOK_SECRET_ARN")

def test_get_secret_prefers_env_value(monkeypatch):
    mod = reload_mod(monkeypatch, {
        "STRIPE_WEBHOOK_SECRET": "whsec_from_env",
        "STRIPE_WEBHOOK_SECRET_ARN": "arn:aws:secretsmanager:dummy:secret:wh",
    })
    # Should return the env value without calling SM
    assert mod._get_secret("STRIPE_WEBHOOK_SECRET", "STRIPE_WEBHOOK_SECRET_ARN") == "whsec_from_env"
