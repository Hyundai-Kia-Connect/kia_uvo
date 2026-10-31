"""Tests for safe authentication failure diagnostics."""

import ast
from pathlib import Path

from hyundai_kia_connect_api.exceptions import (
    AuthenticationBlockedError,
    AuthenticationCciTokenExchangeError,
    AuthenticationError,
    AuthenticationInvalidCredentialsError,
    AuthenticationRedirectError,
    AuthenticationSigninError,
    AuthenticationTokenExpiredError,
)
import pytest


@pytest.mark.parametrize(
    ("exception_type", "expected"),
    [
        (AuthenticationRedirectError, "redirected_to_login"),
        (AuthenticationCciTokenExchangeError, "cci_token_exchange"),
        (AuthenticationSigninError, "signin"),
        (AuthenticationInvalidCredentialsError, "signin"),
        (AuthenticationTokenExpiredError, "other_authentication_error"),
        (AuthenticationBlockedError, "authorize_blocked"),
        (None, "login_returned_false"),
        (AuthenticationError, "other_authentication_error"),
    ],
)
def test_authentication_diagnostics(exception_type, expected):
    path = (
        Path(__file__).resolve().parents[1] / "custom_components/kia_uvo/config_flow.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))

    flow = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ConfigFlow"
    )
    method = next(
        n
        for n in flow.body
        if isinstance(n, ast.AsyncFunctionDef)
        and n.name == "async_step_credentials_password"
    )
    handler = next(
        h
        for n in ast.walk(method)
        if isinstance(n, ast.Try)
        for h in n.handlers
        if isinstance(h.type, ast.Name) and h.type.id == "InvalidAuth"
    )

    code = compile(
        ast.Module(body=handler.body, type_ignores=[]),
        str(path),
        "exec",
    )

    class Logger:
        def __init__(self):
            self.messages = []

        def warning(self, fmt, *args):
            self.messages.append(fmt % args)

    err = Exception("Invalid authentication")
    if exception_type is not None:
        err.__cause__ = exception_type("SECRET_TEST")

    logger = Logger()
    context = {
        "err": err,
        "AuthenticationRedirectError": AuthenticationRedirectError,
        "AuthenticationCciTokenExchangeError": AuthenticationCciTokenExchangeError,
        "AuthenticationSigninError": AuthenticationSigninError,
        "AuthenticationBlockedError": AuthenticationBlockedError,
        "_LOGGER": logger,
        "errors": {},
    }

    exec(code, context)  # noqa: S102

    assert logger.messages == [f"Hyundai/Kia authentication failed: {expected}"]
    assert context["errors"]["base"] == "invalid_auth"
    assert "SECRET_TEST" not in str(logger.messages)
