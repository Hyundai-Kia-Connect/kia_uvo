"""Tests for safe authentication failure diagnostics."""

import ast
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Authentication failed — returned to login page", "redirected_to_login"),
        ("CCI token exchange failed: HTTP 400", "cci_token_exchange"),
        ("Signin failed: HTTP 400", "signin"),
        ("IDPConnect authorize was blocked", "authorize_blocked"),
        (None, "login_returned_false"),
        ("Unknown error SECRET_TEST", "other_authentication_error"),
    ],
)
def test_authentication_diagnostics(message, expected):
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

    class AuthenticationError(Exception):
        pass

    class Logger:
        def __init__(self):
            self.messages = []

        def warning(self, fmt, *args):
            self.messages.append(fmt % args)

    err = Exception("Invalid authentication")
    if message is not None:
        err.__cause__ = AuthenticationError(message)

    logger = Logger()
    context = {
        "err": err,
        "AuthenticationError": AuthenticationError,
        "_LOGGER": logger,
        "errors": {},
    }

    exec(code, context)

    assert logger.messages == [f"Hyundai/Kia authentication failed: {expected}"]
    assert context["errors"]["base"] == "invalid_auth"
    assert "SECRET_TEST" not in str(logger.messages)
