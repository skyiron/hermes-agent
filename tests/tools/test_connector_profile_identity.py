"""A named profile without its own Nous provider still reaches connectors through the root's shared guest."""

import json

import pytest


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def profile_without_nous(tmp_path, monkeypatch):
    profile = tmp_path / "root" / "profiles" / "hermes-setup"
    _write(profile / "auth.json", {"version": 1, "providers": {}, "credential_pool": {}})
    monkeypatch.setenv("HERMES_HOME", str(profile))
    # Beside the root, not under it: the store's pytest seat belt refuses <root>/shared.
    monkeypatch.setenv("HERMES_SHARED_AUTH_DIR", str(tmp_path / "shared-store"))
    monkeypatch.setenv("HERMES_GUEST_ONBOARDING", "1")
    return tmp_path / "shared-store" / "nous_auth.json"


def test_shared_guest_opens_connectors_for_a_profile_without_its_own_identity(profile_without_nous, monkeypatch):
    from tools import managed_tool_gateway, tool_backend_helpers
    from tools.tool_gateway import config

    # No account anywhere: the signed-in leg must not decide this test.
    monkeypatch.setattr(tool_backend_helpers, "managed_nous_tools_enabled", lambda: False)
    assert managed_tool_gateway._read_nous_provider_state() is None
    assert config.connectors_available() is False

    _write(profile_without_nous, {
        "_schema": 1, "auth_method": "anonymous", "account_tier": "anonymous",
        "anon_token": "anon-token", "access_token": "shared-access", "expires_at": "2099-01-01T00:00:00Z",
    })

    state = managed_tool_gateway._read_nous_provider_state()
    assert state is not None and state["auth_method"] == "anonymous"
    assert managed_tool_gateway.peek_nous_access_token() == "shared-access"
    assert config.connectors_available() is True


def test_profile_identity_wins_over_the_shared_store(profile_without_nous, tmp_path):
    from tools import managed_tool_gateway

    _write(profile_without_nous, {"_schema": 1, "auth_method": "anonymous", "anon_token": "anon-token",
                                  "access_token": "shared-access"})
    _write(tmp_path / "root" / "profiles" / "hermes-setup" / "auth.json", {
        "version": 1, "providers": {"nous": {"auth_method": "oauth", "access_token": "own-access",
                                             "refresh_token": "own-refresh"}}})

    assert managed_tool_gateway._read_nous_provider_state()["access_token"] == "own-access"
