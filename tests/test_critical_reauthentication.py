from unittest.mock import Mock, patch

import pytest

from services.critical_reauthentication import (
    CRITICAL_REAUTH_ACTION,
    CriticalReauthenticationBlocked,
    CriticalReauthenticationFailed,
    verify_critical_password,
)


USER = {"id": 1, "email": "Master@Example.com", "senha_hash": "hash"}


def _atomic_attempt(outcome: str):
    def execute(*args, verify, **kwargs):
        if outcome != "blocked":
            verified = verify()
            assert verified is (outcome == "success")
        return outcome

    return Mock(side_effect=execute)


def test_invalid_password_is_recorded_in_shared_bucket_without_secret():
    atomic = _atomic_attempt("failed")
    with patch("db.repo_users.get_user_by_id", return_value=USER), \
         patch("db.repo_users.check_password", return_value=False) as check, \
         patch("db.repo_auth_attempts.perform_rate_limited_attempt", atomic), \
         patch("services.critical_reauthentication._audit"):
        with pytest.raises(CriticalReauthenticationFailed):
            verify_critical_password(1, "segredo-sentinela", ip_address="203.0.113.9")

    check.assert_called_once_with("segredo-sentinela", "hash")
    assert atomic.call_args.args == ("Master@Example.com", "203.0.113.9")
    assert atomic.call_args.kwargs["action"] == CRITICAL_REAUTH_ACTION
    assert "segredo-sentinela" not in repr(atomic.call_args)


def test_blocked_reauthentication_never_reaches_bcrypt():
    atomic = _atomic_attempt("blocked")
    with patch("db.repo_users.get_user_by_id", return_value=USER), \
         patch("db.repo_users.check_password") as check, \
         patch("db.repo_auth_attempts.perform_rate_limited_attempt", atomic), \
         patch("services.critical_reauthentication._audit") as audit:
        with pytest.raises(CriticalReauthenticationBlocked):
            verify_critical_password(1, "qualquer", ip_address="203.0.113.9")

    check.assert_not_called()
    audit.assert_called_once_with(event="critical_reauth_blocked", user_id=1)


def test_success_is_persisted_atomically_before_authorization_is_returned():
    atomic = _atomic_attempt("success")
    with patch("db.repo_users.get_user_by_id", return_value=USER), \
         patch("db.repo_users.check_password", return_value=True), \
         patch("db.repo_auth_attempts.perform_rate_limited_attempt", atomic):
        assert verify_critical_password(1, "correta", ip_address="203.0.113.9") == USER

    assert atomic.call_count == 1


def test_limiter_storage_failure_fails_closed_before_grant():
    with patch("db.repo_users.get_user_by_id", return_value=USER), \
         patch("db.repo_auth_attempts.perform_rate_limited_attempt", side_effect=RuntimeError("database unavailable")):
        with pytest.raises(RuntimeError, match="database unavailable"):
            verify_critical_password(1, "correta", ip_address="203.0.113.9")


class _FakeCursor:
    def __init__(self, counts):
        self.counts = iter(counts)
        self.executed = []

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchone(self):
        return {"n": next(self.counts)}


class _FakeConnection:
    def __init__(self, counts):
        self.cur = _FakeCursor(counts)
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True


def test_atomic_repository_locks_before_count_and_skips_verify_when_blocked():
    from db.repo_auth_attempts import perform_rate_limited_attempt

    connection = _FakeConnection([5, 0])
    verify = Mock(return_value=True)
    with patch("db.db_schema.db_connect", return_value=connection):
        outcome = perform_rate_limited_attempt(
            "master@example.com",
            "203.0.113.9",
            action=CRITICAL_REAUTH_ACTION,
            max_attempts=5,
            lockout_seconds=900,
            verify=verify,
        )

    assert outcome == "blocked"
    verify.assert_not_called()
    assert "pg_advisory_xact_lock" in connection.cur.executed[0][0]
    assert "pg_advisory_xact_lock" in connection.cur.executed[1][0]
    assert connection.cur.executed[-1][1][1] is False
    assert connection.committed is True
