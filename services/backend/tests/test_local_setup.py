import json
from pathlib import Path

import pytest

from vouch_backend import local_setup
from vouch_backend.local_setup import (
    LocalSetupError,
    _atomic_write,
    _credentials,
    _merge_env,
    _validate_targets,
)


@pytest.mark.parametrize(
    "api,database",
    [
        ("https://example.supabase.co", "postgresql://postgres:unused@127.0.0.1:54322/postgres"),
        ("http://127.0.0.1:54321", "postgresql://postgres:unused@remote.example:54322/postgres"),
        ("http://127.0.0.1:54321", "postgresql://postgres:unused@127.0.0.1:5432/postgres"),
    ],
)
def test_bootstrap_refuses_nonlocal_or_unexpected_targets(api: str, database: str) -> None:
    with pytest.raises(LocalSetupError, match="Refusing setup"):
        _validate_targets(api, database)


def test_environment_merge_preserves_unrelated_configuration(tmp_path: Path) -> None:
    path = tmp_path / ".env.api"
    _merge_env(path, {"UNRELATED_SETTING": "preserve", "VOUCH_AUTH_MODE": "fixture"})
    _merge_env(path, {"VOUCH_AUTH_MODE": "supabase"})
    assert path.read_text().splitlines() == [
        'UNRELATED_SETTING="preserve"',
        'VOUCH_AUTH_MODE="supabase"',
    ]


def test_guest_and_retention_credential_upgrade_preserves_existing_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_setup, "PROJECT_ROOT", tmp_path)
    _atomic_write(tmp_path / ".gitignore", ".local/\n")
    original = {
        "password": "synthetic-user-password-for-local-test-only",
        "users": [{"email": "marketer@vouch.test", "role": "marketer"}],
        "database_passwords": {"api": "a" * 40, "worker": "w" * 40},
        "unrelated": "preserved",
    }
    path = tmp_path / ".local/credentials.json"
    _atomic_write(path, json.dumps(original))
    upgraded = _credentials()
    assert upgraded["password"] == original["password"]
    assert upgraded["users"] == original["users"]
    assert upgraded["unrelated"] == "preserved"
    assert upgraded["database_passwords"]["api"] == original["database_passwords"]["api"]
    assert upgraded["database_passwords"]["worker"] == original["database_passwords"]["worker"]
    assert len(upgraded["database_passwords"]["retention"]) >= 32
    assert len(upgraded["database_passwords"]["guest"]) >= 32
    assert len(set(upgraded["database_passwords"].values())) == 4
    assert len(upgraded["guest_rate_limit_key"]) >= 32
    first_write = path.read_bytes()
    assert _credentials() == upgraded
    assert path.read_bytes() == first_write


def test_new_credentials_generate_distinct_guest_runtime_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_setup, "PROJECT_ROOT", tmp_path)
    _atomic_write(tmp_path / ".gitignore", ".local/\n")

    generated = _credentials()
    passwords = generated["database_passwords"]

    assert set(passwords) == {"api", "worker", "retention", "guest"}
    assert all(isinstance(value, str) and len(value) >= 32 for value in passwords.values())
    assert len(set(passwords.values())) == 4
    assert isinstance(generated["guest_rate_limit_key"], str)
    assert len(generated["guest_rate_limit_key"]) >= 32
    assert generated["guest_rate_limit_key"] not in set(passwords.values())


@pytest.mark.parametrize("kind", ["retention", "guest"])
def test_existing_invalid_additive_credential_is_not_rotated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    monkeypatch.setattr(local_setup, "PROJECT_ROOT", tmp_path)
    _atomic_write(tmp_path / ".gitignore", ".local/\n")
    path = tmp_path / ".local/credentials.json"
    passwords = {
        "api": "a" * 40,
        "worker": "w" * 40,
        "retention": "r" * 40,
        "guest": "g" * 40,
        kind: "bad",
    }
    if kind == "guest":
        # Exercise the interrupted-upgrade boundary too: a newly generated
        # retention secret must not be persisted before the bad guest value is rejected.
        passwords.pop("retention")
    _atomic_write(
        path,
        json.dumps(
            {
                "password": "p" * 40,
                "database_passwords": passwords,
            }
        ),
    )
    before = path.read_bytes()
    with pytest.raises(LocalSetupError, match=rf"{kind} credentials are invalid"):
        _credentials()
    assert path.read_bytes() == before


def test_invalid_guest_rate_limit_key_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_setup, "PROJECT_ROOT", tmp_path)
    _atomic_write(tmp_path / ".gitignore", ".local/\n")
    path = tmp_path / ".local/credentials.json"
    _atomic_write(
        path,
        json.dumps(
            {
                "password": "p" * 40,
                "database_passwords": {
                    "api": "a" * 40,
                    "worker": "w" * 40,
                    "retention": "r" * 40,
                    "guest": "g" * 40,
                },
                "guest_rate_limit_key": "bad",
            }
        ),
    )
    before = path.read_bytes()
    with pytest.raises(LocalSetupError, match="rate-limit credentials are invalid"):
        _credentials()
    assert path.read_bytes() == before


def test_explicit_guest_rotation_preserves_every_unrelated_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_setup, "PROJECT_ROOT", tmp_path)
    _atomic_write(tmp_path / ".gitignore", ".local/\n")
    original = _credentials()

    rotated = _credentials(rotate_guest=True)

    assert rotated["password"] == original["password"]
    for kind in ("api", "worker", "retention"):
        assert rotated["database_passwords"][kind] == original["database_passwords"][kind]
    assert rotated["database_passwords"]["guest"] != original["database_passwords"]["guest"]
    assert rotated["guest_rate_limit_key"] != original["guest_rate_limit_key"]
